#!/usr/bin/env python3
"""Capture native DepthAI messages on the host, with optional RVC4 cameras."""
import argparse
from collections import deque
from datetime import datetime
import json
import hashlib
import math
import os
from pathlib import Path
import queue
import re
import threading
import time

os.environ.setdefault('DEPTHAI_TELEMETRY', '0')
os.environ.setdefault('DEPTHAI_AUTOCALIBRATION', 'OFF')
import depthai as dai
from control import ControlServer


def positive_int(value):
    n = int(value)
    if n < 1 or n > 10000:
        raise ValueError('Frame count must be between 1 and 10000')
    return n


def positive_float(value):
    n = float(value)
    if not math.isfinite(n) or n <= 0:
        raise argparse.ArgumentTypeError('Must be a finite number greater than zero')
    return n


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device', help='Device IP or ID; required when discovery finds multiple devices')
    p.add_argument('--expected-id', help='Refuse a different device at the supplied address')
    p.add_argument('--output', type=Path, default=Path('captures'))
    p.add_argument('--frames', type=positive_int, default=5)
    p.add_argument('--warmup', type=positive_float, default=5.0, help='Minimum live-stream warmup in seconds')
    p.add_argument('--fps', type=positive_float, default=10.0)
    p.add_argument('--width', type=positive_int, default=1280, help='Maximum image width; preserves sensor aspect ratio')
    p.add_argument('--port', type=int, default=8083, help='Capture control page port')
    p.add_argument('--visualizer-port', type=int, default=8082)
    p.add_argument('--websocket-port', type=int, default=8765)
    p.add_argument('--capture-timeout', type=positive_float, default=60.0)
    p.add_argument('--auto-capture', action='store_true', help='Capture once after warmup and exit (for batch testing)')
    p.add_argument('--no-gui', action='store_true', help='Use with --auto-capture for unattended capture')
    a = p.parse_args()
    if a.width < 2:
        p.error('--width must be at least 2 pixels')
    if a.no_gui and not a.auto_capture:
        p.error('--no-gui requires --auto-capture')
    if len({a.port, a.visualizer_port, a.websocket_port}) != 3 or any(not 1024 <= x <= 65535 for x in (a.port,a.visualizer_port,a.websocket_port)):
        p.error('Use three distinct ports between 1024 and 65535')
    return a


def write_json(path, data):
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def camera_roles(features, calibration):
    """Prefer calibrated stereo roles, then the standard socket/name convention."""
    roles = {}
    left, right = calibration.getStereoLeftCameraId(), calibration.getStereoRightCameraId()
    for f in features:
        if dai.CameraSensorType.TOF in f.supportedTypes:
            role = 'tof'
        elif f.socket == left or f.name.lower() == 'left':
            role = 'left'
        elif f.socket == right or f.name.lower() == 'right':
            role = 'right'
        elif f.socket == dai.CameraBoardSocket.CAM_B:
            role = 'left'
        elif f.socket == dai.CameraBoardSocket.CAM_C:
            role = 'right'
        elif dai.CameraSensorType.COLOR in f.supportedTypes:
            role = 'rgb'
        else:
            role = f.socket.name.lower()
        if role in roles:
            role += '_' + f.socket.name.lower()
        roles[role] = f
    return roles


class FrameMatcher:
    """Bounded timestamp matching, without creating a StereoDepth node."""
    def __init__(self, names, tolerance):
        self.buffers = {name: deque(maxlen=8) for name in names}
        self.tolerance = tolerance

    def add(self, name, frame):
        self.buffers[name].append(frame)

    def clear(self):
        for buf in self.buffers.values():
            buf.clear()

    def take(self):
        while all(self.buffers.values()):
            times = {k: b[0].getTimestampDevice().total_seconds() for k,b in self.buffers.items()}
            oldest = min(times, key=times.get)
            if max(times.values()) - times[oldest] <= self.tolerance:
                return {k: b.popleft() for k,b in self.buffers.items()}
            self.buffers[oldest].popleft()
        return None


class CaptureApp:
    def __init__(self, args, device):
        self.args, self.device = args, device
        self.calibration = device.readCalibration()
        self.features = device.getConnectedCameraFeatures()
        self.roles = camera_roles(self.features, self.calibration)
        self.requests = queue.Queue(maxsize=1)
        self.lock = threading.Lock()
        self.state = dict(state='starting', frames=args.frames, output=str(args.output.resolve()),
                          saved_path=None, completed_frames=0, warmup_remaining=args.warmup,
                          device=dict(id=device.getDeviceId(), name=device.getDeviceName(),
                                      os=device.getOSVersion(), sdk=dai.__version__), streams=[])
        self.active = None
        self.manifest = None
        self.ready_at = None
        self.started = time.monotonic()

    def status(self):
        with self.lock:
            return dict(self.state)

    def update(self, **kwargs):
        with self.lock:
            self.state.update(kwargs)

    def request(self, request):
        value = request.get('frames', self.args.frames)
        if isinstance(value, bool) or str(value) != str(int(value)):
            raise ValueError('Frame count must be an integer')
        frames = positive_int(value)
        output = request.get('output', str(self.args.output))
        if not isinstance(output, str) or not output.strip() or '\x00' in output:
            raise ValueError('Output must be a nonempty host directory path')
        output = str(Path(output).expanduser().resolve())
        with self.lock:
            if self.state['state'] not in ('ready', 'complete', 'error'):
                raise RuntimeError('Wait for warmup or the current capture to finish')
            self.requests.put_nowait((frames, output))
            self.state.update(state='queued', frames=frames, output=output, error=None)
        return {'accepted': True, 'frames': frames, 'output': output}

    def start_capture(self, frames, output):
        stamp = datetime.now().astimezone().strftime('%Y%m%dT%H%M%S_%f%z')
        name = re.sub(r'[^a-zA-Z0-9_-]', '_', self.device.getDeviceName())
        folder = Path(output) / f'{name}_{self.device.getDeviceId()}_{stamp}'
        folder.mkdir(parents=True, exist_ok=False)
        self.active = folder
        self.manifest = None
        self.capture_start = time.monotonic()
        self.manifest = dict(schema_version=1, status='capturing', date=datetime.now().astimezone().isoformat(),
            model_name=self.device.getDeviceName(), mxId=self.device.getDeviceId(),
            platform=self.device.getPlatform().name, os_version=self.device.getOSVersion(), dai_version=dai.__version__,
            settings=dict(fps=self.args.fps, max_width=self.args.width, frames=frames, warmup_seconds=self.args.warmup,
                          synchronization='host device-timestamp matching', sync_tolerance_ms=self.matcher.tolerance*1000,
                          camera_undistortion=False, tof_grid='standard ToF optical grid (SDK default distortion correction)', tof_profile='MID_RANGE'),
            source_sha256={name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                           for name in ('main.py','control.py','index.html')},
            streams=self.streams, cameras=[dict(socket=f.socket.name,sensor=f.sensorName,name=f.name,
                width=f.width,height=f.height,types=[x.name for x in f.supportedTypes]) for f in self.features],
            requested_frames=frames, frames=[], capture_seconds=None)
        write_json(folder/'metadata.json', self.manifest)
        self.calibration.eepromToJsonFile(str(folder / 'calib.json'))
        for stream in self.streams:
            (folder / stream).mkdir()
        self.matcher.clear()
        # Consume only frames whose device-synchronized host timestamp is newer than the trigger.
        self.trigger_timestamp = dai.Clock.now().total_seconds()
        self.update(state='capturing', completed_frames=0, saved_path=str(folder))

    def save_group(self, group):
        times = [f.getTimestampDevice().total_seconds() for f in group.values()]
        # Shared decimal microsecond key keeps existing capture/replay pairing compatible.
        key = str(round(min(times)*1000000))
        record = dict(timestamp=key, skew_ms=(max(times)-min(times))*1000, streams={})
        for name, msg in group.items():
            stem = self.active / name / f'{name}_{key}'
            msg.save(str(stem))
            path = stem.with_suffix('.dai')
            if not path.is_file() or path.stat().st_size == 0:
                raise IOError(f'DepthAI did not save {path}')
            record['streams'][name] = dict(file=str(path.relative_to(self.active)), width=msg.getWidth(),
                height=msg.getHeight(), type=msg.getType().name, sequence=msg.getSequenceNum(),
                timestamp_device_seconds=msg.getTimestampDevice().total_seconds(),
                exposure_us=round(msg.getExposureTime().total_seconds()*1000000),
                sensitivity_iso=msg.getSensitivity(), bytes=path.stat().st_size)
        self.manifest['frames'].append(record)
        write_json(self.active/'metadata.json', self.manifest)
        self.update(completed_frames=len(self.manifest['frames']))
        if len(self.manifest['frames']) == self.manifest['requested_frames']:
            self.finish('complete')

    def finish(self, status, error=None):
        if self.active and self.manifest:
            self.manifest.update(status=status, capture_seconds=time.monotonic()-self.capture_start,
                                 finished=datetime.now().astimezone().isoformat())
            if error:
                self.manifest['error'] = error
            write_json(self.active/'metadata.json', self.manifest)
        print(json.dumps(dict(event=status, path=str(self.active), error=error)), flush=True)
        self.active = None
        self.update(state=status, error=error)

    def run(self):
        a = self.args
        visualizer = None if a.no_gui else dai.RemoteConnection(httpPort=a.visualizer_port, webSocketPort=a.websocket_port)
        server = None
        with dai.Pipeline(self.device) as pipeline:
            outputs, self.streams = {}, {}
            for role,f in self.roles.items():
                if dai.CameraSensorType.TOF in f.supportedTypes:
                    tof = pipeline.create(dai.node.ToF).build(f.socket, dai.ToFConfig.Profile.MID_RANGE, a.fps)
                    for suffix,out in [('depth',tof.depth),('confidence',tof.confidence)]:
                        name = f'{role}_{suffix}'
                        outputs[name] = out
                        self.streams[name] = dict(socket=f.socket.name, kind=name, geometry='native ToF')
                else:
                    cam = pipeline.create(dai.node.Camera).build(f.socket)
                    width = min(a.width, f.width)
                    width -= width % 2
                    height = max(2, round(width*f.height/f.width)//2*2)
                    typ = dai.ImgFrame.Type.GRAY8 if role in ('left','right') or dai.CameraSensorType.COLOR not in f.supportedTypes else dai.ImgFrame.Type.NV12
                    outputs[role] = cam.requestOutput((width,height), typ, dai.ImgResizeMode.STRETCH,
                                                     a.fps, enableUndistortion=False)
                    self.streams[role] = dict(socket=f.socket.name, kind='camera', resolution=[width,height], geometry='unrectified full FOV')
            if not outputs:
                raise RuntimeError('No supported cameras connected')
            queues = {name:out.createOutputQueue(maxSize=8, blocking=False) for name,out in outputs.items()}
            if visualizer:
                for name,out in outputs.items():
                    visualizer.addTopic(name, out, 'Capture streams')
            self.matcher = FrameMatcher(outputs, 0.5/a.fps)
            self.update(streams=list(outputs), state='warming_up')
            pipeline.start()
            print('Pipeline started.', flush=True)
            if visualizer:
                visualizer.registerPipeline(pipeline)
                server = ControlServer('127.0.0.1', a.port, a.visualizer_port, self.status, lambda frames, output: self.request(dict(frames=frames, output=output)))
                server.start()
                print(f'Capture GUI: {server.url}', flush=True)
            first_seen = {}
            last_seen = {}
            auto_requested = False
            try:
                while pipeline.isRunning():
                    now = time.monotonic()
                    for name,q in queues.items():
                        for msg in q.tryGetAll():
                            first_seen.setdefault(name, now)
                            last_seen[name] = now
                            if self.active and msg.getTimestamp().total_seconds() > self.trigger_timestamp:
                                self.matcher.add(name,msg)
                    if self.ready_at is None and len(first_seen) == len(outputs):
                        self.ready_at = max(first_seen.values()) + a.warmup
                    if self.ready_at is not None and self.status()['state'] == 'warming_up':
                        remaining = max(0, self.ready_at-now)
                        self.update(warmup_remaining=round(remaining,1))
                        if remaining == 0:
                            self.update(state='ready')
                    if now-self.started > a.capture_timeout+a.warmup and self.ready_at is None:
                        raise TimeoutError('Not all detected streams produced frames')
                    if last_seen and any(now-last_seen.get(name,self.started)>a.capture_timeout for name in outputs):
                        raise TimeoutError('A detected camera stopped producing frames')
                    if a.auto_capture and not auto_requested and self.status()['state']=='ready':
                        self.request(dict(frames=a.frames, output=str(a.output)))
                        auto_requested = True
                    try:
                        request = self.requests.get_nowait()
                    except queue.Empty:
                        request = None
                    if request:
                        try:
                            self.start_capture(*request)
                        except Exception as exc:
                            self.finish('error', str(exc))
                    if self.active:
                        try:
                            group = self.matcher.take()
                            if group:
                                self.save_group(group)
                            if self.active and now-self.capture_start > a.capture_timeout:
                                raise TimeoutError('Timed out waiting for synchronized frames')
                        except Exception as exc:
                            self.finish('error', str(exc))
                    if a.auto_capture and auto_requested and self.status()['state'] in ('complete','error'):
                        if self.status()['state']=='error':
                            raise RuntimeError(self.status()['error'])
                        return
                    if visualizer and visualizer.waitKey(1)==ord('q'):
                        return
                    time.sleep(.005)
                raise RuntimeError('Pipeline stopped unexpectedly')
            finally:
                if self.active:
                    self.finish('incomplete','Application stopped before capture completed')
                if server:
                    server.close()


def main():
    args = arguments()
    if args.device:
        info = dai.DeviceInfo(args.device)
    else:
        devices = dai.Device.getAllAvailableDevices()
        if len(devices)!=1:
            raise RuntimeError(f'Found {len(devices)} devices. Select one explicitly with --device.')
        info = devices[0]
    with dai.Device(info) as device:
        if device.getPlatform() != dai.Platform.RVC4:
            raise RuntimeError('This example requires an RVC4 device')
        if args.expected_id and device.getDeviceId()!=args.expected_id:
            raise RuntimeError('Device identity does not match --expected-id')
        CaptureApp(args, device).run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped.', flush=True)
