"""Geometry regressions; these run without opening a device."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import depthai as dai
import pytest
from depthai_nodes.message import GatheredData

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.merge_img_detections import MergeImgDetections


def test_tiles_map_to_the_matched_panorama_and_keep_reference_metadata():
    # Two tiles of one virtual camera, each containing a box in local coordinates.
    target = dai.ImgTransformation(1000, 500)
    reference = dai.ImgFrame()
    reference.setTransformation(target)
    reference.setSequenceNum(42)
    reference.setTimestamp(timedelta(seconds=10))
    reference.setTimestampDevice(timedelta(seconds=8))
    reference.setTimestampSystem(datetime(2026, 11, 1, tzinfo=UTC))
    items = []
    for offset in (0, 500):
        source = dai.ImgTransformation(1000, 500).addCrop(offset, 0, 500, 500)
        item = dai.ImgDetections()
        item.setTransformation(source)
        box = dai.ImgDetection()
        box.xmin, box.xmax, box.ymin, box.ymax = 0.2, 0.8, 0.2, 0.8
        box.label, box.confidence = 2, 0.7
        item.detections = [box]
        items.append(item)
    sent = []
    node = SimpleNamespace(out=SimpleNamespace(send=sent.append))
    MergeImgDetections.process(
        node, GatheredData(items=items, reference_data=reference)
    )
    merged = sent[0]
    assert [box.xmin for box in merged.detections] == pytest.approx([0.1, 0.6])
    assert [box.xmax for box in merged.detections] == pytest.approx([0.4, 0.9])
    assert merged.getTransformation().getSize() == (1000, 500)
    assert merged.getSequenceNum() == 42
    assert merged.getTimestamp() == reference.getTimestamp()
    assert merged.getTimestampDevice() == reference.getTimestampDevice()
    assert merged.getTimestampSystem() == reference.getTimestampSystem()
    assert items[1].detections[0].xmin == pytest.approx(0.2)


def test_missing_geometry_is_rejected_instead_of_misplacing_boxes():
    reference = dai.ImgFrame()
    item = dai.ImgDetections()
    node = SimpleNamespace(
        out=SimpleNamespace(send=lambda _: pytest.fail("sent invalid geometry"))
    )
    with pytest.raises(RuntimeError, match="transformations"):
        MergeImgDetections.process(
            node, GatheredData(items=[item], reference_data=reference)
        )
