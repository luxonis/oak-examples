from dataclasses import dataclass
from datetime import timedelta
import json
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory

import depthai as dai


@dataclass(frozen=True)
class ReplayCalibration:
    device_id: str
    calibration: dai.CalibrationHandler


def load_replay_calibration(recording: str | None) -> ReplayCalibration | None:
    if not recording:
        return None
    with TemporaryDirectory(prefix="measure-anything-replay-") as folder:
        directory = Path(folder)
        with tarfile.open(recording) as archive:
            metadata = directory / "CameraCAM_A.mcap"
            metadata.write_bytes(archive.extractfile("CameraCAM_A.mcap").read())
            camera_info = json.load(archive.extractfile("camera_info.json"))
        calibration_file = directory / "calibration.json"
        calibration_file.write_text(json.dumps(camera_info["calibration"]))
        calibration = dai.CalibrationHandler(calibration_file)
        with dai.Pipeline(False) as pipeline:
            replay = pipeline.create(dai.node.ReplayMetadataOnly).setReplayFile(
                metadata
            )
            replay.setLoop(False)
            output = replay.out.createOutputQueue(maxSize=1, blocking=False)
            pipeline.start()
            frame = output.get(timedelta(seconds=3))
            if frame is None:
                raise RuntimeError("The replay contains no RGB camera metadata.")
            device_id = frame.getTransformation().getExtrinsics().toDeviceId
            pipeline.stop()
            pipeline.wait()
        if not device_id:
            raise RuntimeError("The replay RGB metadata has no reference device ID.")
        return ReplayCalibration(device_id, calibration)
