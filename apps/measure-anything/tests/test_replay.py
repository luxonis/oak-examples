from datetime import timedelta
import json
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
import threading
import time
import unittest

import depthai as dai
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
from util.replay import load_replay_calibration


class ReplayTests(unittest.TestCase):
    def test_recorded_reference_calibration_produces_a_cloud_without_its_camera(self):
        recorded_id = "recorded-camera"
        intrinsics = [[20, 0, 16], [0, 20, 12], [0, 0, 1]]
        calibration = dai.CalibrationHandler()
        calibration.setCameraIntrinsics(dai.CameraBoardSocket.CAM_A, intrinsics, 32, 24)
        frame = dai.ImgFrame()
        frame.setCvFrame(
            np.full((24, 32), 1000, dtype=np.uint16), dai.ImgFrame.Type.RAW16
        )
        extrinsics = dai.Extrinsics(
            np.eye(4).tolist(), dai.CameraBoardSocket.CAM_A, dai.LengthUnit.MILLIMETER
        )
        extrinsics.toDeviceId = recorded_id
        frame.setTransformation(
            dai.ImgTransformation(
                32, 24, intrinsics, dai.CameraModel.Perspective, [], extrinsics
            )
        )
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            metadata = directory / "CameraCAM_A.mcap"
            with dai.Pipeline(False) as pipeline:
                recorder = pipeline.create(dai.node.RecordMetadataOnly).setRecordFile(
                    metadata
                )
                inputs = recorder.input.createInputQueue(maxSize=1, blocking=True)
                pipeline.start()
                for sequence in range(3):
                    frame.setSequenceNum(sequence)
                    inputs.send(frame)
                deadline = time.monotonic() + 2
                while not metadata.exists() and time.monotonic() < deadline:
                    threading.Event().wait(0.01)
                pipeline.stop()
                pipeline.wait()
            camera_info = directory / "camera_info.json"
            camera_info.write_text(
                json.dumps({"calibration": calibration.eepromToJson()})
            )
            recording = directory / "recording.tar"
            with tarfile.open(recording, "w") as archive:
                archive.add(metadata, arcname=metadata.name)
                archive.add(camera_info, arcname=camera_info.name)
            replay = load_replay_calibration(str(recording))
        self.assertEqual(replay.device_id, recorded_id)
        with dai.Pipeline(False) as pipeline:
            cloud = pipeline.create(dai.node.PointCloud)
            cloud.setRunOnHost(True)
            cloud.sync.setRunOnHost(True)
            cloud.initialConfig.setOrganized(True)
            cloud.initialConfig.setTargetCoordinateSystem(dai.CameraBoardSocket.CAM_A)
            cloud.setDeviceCalibration(replay.device_id, replay.calibration)
            inputs = cloud.inputDepth.createInputQueue()
            output = cloud.outputPointCloud.createOutputQueue()
            pipeline.start()
            try:
                inputs.send(frame)
                result = output.get(timedelta(seconds=2))
                self.assertIsNotNone(result)
                points = result.getPoints()
                self.assertEqual(points.shape, (24 * 32, 3))
                np.testing.assert_allclose(points[12 * 32 + 16], (0, 0, 1000))
                self.assertEqual(
                    result.getTransformation().getExtrinsics().toDeviceId, recorded_id
                )
            finally:
                pipeline.stop()
                pipeline.wait()


if __name__ == "__main__":
    unittest.main()
