"""Geometry regressions with real DepthAI metadata and controlled metric inputs."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace, ModuleType

import pytest

dai = pytest.importorskip("depthai", minversion="3.11.0")
np = pytest.importorskip("numpy")
pytest.importorskip("depthai_nodes")
pytest.importorskip("cv2")

ROOT = Path(__file__).resolve().parents[1]


def load_utils(name, example, module):
    directory = ROOT / example / "utils"
    package = ModuleType(name)
    package.__path__ = [str(directory)]
    sys.modules.setdefault(name, package)
    spec = importlib.util.spec_from_file_location(
        f"{name}.{module}", directory / f"{module}.py"
    )
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


spatial = load_utils(
    "spatial_utils", "depth-measurement/calc-spatial-on-host", "measure_distance"
)
distance = load_utils(
    "p2p_utils", "apps/p2p-measurement/backend/src", "distance_calculator"
)
wls = load_utils("wls_utils", "depth-measurement/wls-filter", "host_wls_filter")


def frame(width, height, depth=2000):
    msg = dai.ImgFrame()
    msg.setType(dai.ImgFrame.Type.RAW16)
    msg.setFrame(np.full((height, width), depth, dtype=np.uint16))
    msg.setWidth(width)
    msg.setHeight(height)
    transform = dai.ImgTransformation()
    transform.setSourceSize(width, height)
    transform.setSize(width, height)
    # Deliberately off-center and with unequal focal lengths.
    transform.setIntrinsicMatrix(
        [[400, 0, width * 0.4], [0, 500, height * 0.3], [0, 0, 1]]
    )
    extrinsics = dai.Extrinsics(np.eye(4).tolist(), dai.CameraBoardSocket.CAM_A)
    extrinsics.toDeviceId = "geometry-test"
    transform.setExtrinsics(extrinsics)
    msg.setTransformation(transform)
    return msg


@pytest.mark.parametrize("size", [(640, 400), (576, 360), (320, 240)])
def test_host_roi_uses_frame_optical_geometry(size):
    msg = frame(*size)
    x, y = size[0] // 2, size[1] // 2
    sent = []
    host = SimpleNamespace(
        _update_roi=lambda: None,
        _roi=spatial.RegionOfInterest.from_size(x, y, 5),
        _threshold_low=200,
        _threshold_high=30000,
        _averaging_method=np.mean,
        output=SimpleNamespace(send=sent.append),
    )
    spatial.MeasureDistance.process(host, msg)
    point = sent[0].spatials
    assert (point.x, point.y, point.z) == pytest.approx(
        ((x - size[0] * 0.4) * 2000 / 400, (y - size[1] * 0.3) * 2000 / 500, 2000),
        abs=1e-3,
    )
    # Native projection must land back on the selected ROI pixel.
    pixel = msg.getTransformation().project3DPoint(point)
    assert (pixel.x, pixel.y) == pytest.approx((x, y), abs=1e-4)


def test_p2p_refreshes_intrinsics_on_each_message_and_keeps_meters():
    calc = distance.DistanceCalculator(measurement_history_length=1)
    msg = frame(640, 400)
    assert calc._calculate_3d_distance((100, 100), (200, 100), msg)[0] == pytest.approx(
        0.5
    )
    transform = msg.getTransformation()
    transform.setIntrinsicMatrix([[800, 0, 256], [0, 500, 120], [0, 0, 1]])
    msg.setTransformation(transform)
    assert calc._calculate_3d_distance((100, 100), (200, 100), msg)[0] == pytest.approx(
        0.25
    )


@pytest.mark.parametrize("point", [(-1, 20), (640, 20), (20, 400)])
def test_p2p_rejects_out_of_frame_points(point):
    calc = distance.DistanceCalculator()
    assert calc._calculate_3d_distance(point, (100, 100), frame(640, 400)) == (-1, 0)


def test_p2p_rejects_invalid_depth():
    calc = distance.DistanceCalculator()
    assert calc._calculate_3d_distance((10, 10), (20, 20), frame(640, 400, 0)) == (
        -1,
        0,
    )


@pytest.mark.parametrize("disparity_scale", [1, 8, 32])
def test_wls_metric_depth_is_independent_of_subpixel_scale(disparity_scale):
    filt = wls.Filter(8000, 1.5)
    values = np.array([[10 * disparity_scale, 0, -disparity_scale]], dtype=np.int16)
    filt.wlsFilter = SimpleNamespace(
        setLambda=lambda _: None, setSigmaColor=lambda _: None, filter=lambda *_: values
    )
    _, depth = filt.filter(
        values, np.zeros((1, 3), np.uint8), 75 * 400 * disparity_scale
    )
    assert depth.tolist() == [[3000, 0, 0]]


def test_calibration_uses_intrinsics_of_received_still():
    calibration = load_utils(
        "calibration_utils",
        "tutorials/multiple-devices/multi-cam-calibration",
        "calibration_node",
    )
    still = frame(320, 240)
    # First read drains stale frames; the second receives the captured still.
    reads = iter([None, still])
    seen = []
    host = SimpleNamespace(
        calib=True,
        processing=False,
        mxid="test",
        control_q=SimpleNamespace(send=lambda _: None),
        still_q=SimpleNamespace(tryGet=lambda: next(reads)),
        _estimate_pose_from_image=lambda _: (
            seen.append(host.intrinsic_mat_still) or True
        ),
    )
    assert calibration.CalibrationNode.capture_and_calibrate(host)
    np.testing.assert_allclose(seen[0], still.getTransformation().getIntrinsicMatrix())
    assert (host.still_width, host.still_height) == (320, 240)


def test_volume_projection_uses_current_cloud_transformation():
    pytest.importorskip("open3d")
    pytest.importorskip("scipy")
    module = load_utils(
        "volume_utils",
        "apps/object-volume-measurement-3d/backend/src",
        "measurement_node",
    )
    transform = frame(320, 240).getTransformation()
    host = SimpleNamespace(transformation=transform, imgW=320, imgH=240)
    projected = module.MeasurementNode._proj_cam_to_rgb_norm(
        host, [[100, 200, 2000], [0, 0, -1]]
    )
    assert projected[0] == pytest.approx(
        ((400 * 0.05 + 128) / 320, (500 * 0.1 + 72) / 240)
    )
    assert projected[1] is None


def test_box_overlay_uses_actual_nn_image_size():
    pytest.importorskip("open3d")
    module = load_utils(
        "box_utils",
        "depth-measurement/measurement-3d/box-measurement",
        "box_processing_node",
    )
    transform = frame(320, 240).getTransformation()
    lines = []
    host = SimpleNamespace(
        cloud_transformation=transform,
        image_transformation=transform,
        helper_cuboid=SimpleNamespace(draw_line=lambda *a, **k: lines.append(a)),
    )
    corners = np.tile([100, 200, 2000], (8, 1))
    module.BoxProcessingNode._draw_cuboid_outline(host, corners)
    assert len(lines) == 12
    assert lines[0][0] == pytest.approx(
        ((400 * 0.05 + 128) / 320, (500 * 0.1 + 72) / 240)
    )


def test_kalman_initializes_an_already_tracked_id_with_stereo_noise():
    module = load_utils(
        "kalman_utils", "neural-networks/object-tracking/kalman", "kalman_filter_node"
    )
    track = dai.Tracklet()
    track.id = 1
    track.label = 0
    track.status = dai.Tracklet.TrackingStatus.TRACKED
    track.roi = dai.Rect(0.1, 0.1, 0.2, 0.2)
    track.spatialCoordinates = dai.Point3f(100, 200, 2000)
    tracks = dai.Tracklets()
    tracks.tracklets = [track]
    sent = []
    host = SimpleNamespace(
        _kalman_filters={},
        _focal_length=None,
        input_right=SimpleNamespace(tryGetAll=lambda: [frame(640, 400)]),
        _baseline=75,
        _label_map=["person"],
        out=SimpleNamespace(send=sent.append),
    )
    msg = frame(640, 400)
    module.KalmanFilterNode.process(host, msg, tracks)
    assert host._kalman_filters[1]["space"].meas_std == pytest.approx(
        2000**2 / (75 * 400)
    )
    assert len(sent) == 1
    track.status = dai.Tracklet.TrackingStatus.REMOVED
    tracks.tracklets = [track]
    module.KalmanFilterNode.process(host, msg, tracks)
    assert not host._kalman_filters
