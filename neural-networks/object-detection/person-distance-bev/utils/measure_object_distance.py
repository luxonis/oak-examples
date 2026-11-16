import itertools
import math
from typing import List

import depthai as dai


class DetectionDistance:
    def __init__(
        self,
        detection1: dai.SpatialImgDetection,
        detection2: dai.SpatialImgDetection,
        distance: float,
    ) -> None:
        self.detection1 = detection1
        self.detection2 = detection2
        self.distance = distance


class ObjectDistances(dai.Buffer):
    def __init__(self) -> None:
        super().__init__(0)
        self.detections: List[dai.SpatialImgDetection] = []
        self.distances: List[DetectionDistance] = []


def has_valid_coordinates(detection: dai.SpatialImgDetection) -> bool:
    coordinates = detection.spatialCoordinates
    return (
        all(
            math.isfinite(value)
            for value in (coordinates.x, coordinates.y, coordinates.z)
        )
        and coordinates.z > 0
    )


class MeasureObjectDistance(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.Buffer, True)
            ]
        )

    def build(self, detections: dai.Node.Output) -> "MeasureObjectDistance":
        self.link_args(detections)
        return self

    def process(self, detections: dai.SpatialImgDetections) -> None:
        valid_detections = [
            detection
            for detection in detections.detections
            if has_valid_coordinates(detection)
        ]

        result = ObjectDistances()
        result.detections = valid_detections
        result.distances = [
            DetectionDistance(
                first,
                second,
                math.dist(
                    (
                        first.spatialCoordinates.x,
                        first.spatialCoordinates.y,
                        first.spatialCoordinates.z,
                    ),
                    (
                        second.spatialCoordinates.x,
                        second.spatialCoordinates.y,
                        second.spatialCoordinates.z,
                    ),
                ),
            )
            for first, second in itertools.combinations(valid_detections, 2)
        ]
        result.setTimestamp(detections.getTimestamp())
        result.setSequenceNum(detections.getSequenceNum())
        self.output.send(result)
