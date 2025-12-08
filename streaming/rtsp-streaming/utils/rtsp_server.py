from collections import deque

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
import threading  # noqa: E402

from gi.repository import GLib, Gst, GstRtspServer  # noqa: E402


class RtspSystem(GstRtspServer.RTSPMediaFactory):
    def __init__(self, fps, **properties):
        super(RtspSystem, self).__init__(**properties)
        self.launch_string = (
            "appsrc name=source is-live=true do-timestamp=true format=time "
            f"caps=video/x-h265,stream-format=byte-stream,alignment=au,framerate={fps}/1 ! "
            "h265parse ! rtph265pay name=pay0 pt=96 config-interval=1"
        )
        self.cond = threading.Condition()
        self.queue = deque(maxlen=20)

    def send_data(self, data):
        with self.cond:
            self.queue.append(data)
            self.cond.notify()

    def on_need_data(self, src, length):
        with self.cond:
            while not self.queue:
                self.cond.wait(timeout=1.0)
            data = self.queue.popleft()
        buf = Gst.Buffer.new_allocate(None, len(data.tobytes()), None)
        buf.fill(0, data.tobytes())
        src.emit("push-buffer", buf)

    def do_create_element(self, url):
        return Gst.parse_launch(self.launch_string)

    def do_configure(self, rtsp_media):
        self.number_frames = 0
        appsrc = rtsp_media.get_element().get_child_by_name("source")
        appsrc.connect("need-data", self.on_need_data)


class RTSPServer(GstRtspServer.RTSPServer):
    def __init__(self, fps, **properties):
        super(RTSPServer, self).__init__(**properties)
        Gst.init(None)
        self.rtsp = RtspSystem(fps)
        self.rtsp.set_shared(True)
        self.get_mount_points().add_factory("/preview", self.rtsp)
        self.start()

    def start(self):
        def _run():
            context = GLib.MainContext()
            loop = GLib.MainLoop(context=context)
            self.attach(context)
            loop.run()

        threading.Thread(target=_run, daemon=True).start()

    def send_data(self, data):
        self.rtsp.send_data(data)
