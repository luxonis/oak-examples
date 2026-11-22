import itertools

import depthai as dai

from typing import List


class DetectionDistance:
    def __init__(
        self,
        det1: dai.SpatialImgDetection,
        det2: dai.SpatialImgDetections,
        distance: float,
    ) -> None:
        self._detection1 = det1
        self._detection2 = det2
        self._distance = distance

    @property
    def detection1(self) -> dai.SpatialImgDetection:
        return self._detection1

    @property
    def detection2(self) -> dai.SpatialImgDetections:
        return self._detection2

    @property
    def distance(self) -> float:
        return self._distance

    @distance.setter
    def distance(self, value: float) -> None:
        self._distance = value

    @detection1.setter
    def detection1(self, value: dai.SpatialImgDetection) -> None:
        self._detection1 = value

    @detection2.setter
    def detection2(self, value: dai.SpatialImgDetections) -> None:
        self._detection2 = value


class ObjectDistances(dai.Buffer):
    def __init__(self) -> None:
        super().__init__(0)
        self._distances: List[DetectionDistance] = []

    @property
    def distances(self) -> List[DetectionDistance]:
        return self._distances

    @distances.setter
    def distances(self, value: List[DetectionDistance]) -> None:
        self._distances = value


class MeasureObjectDistance(dai.node.HostNode):
    def __init__(self):
        super().__init__()

        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.Buffer, True)
            ]
        )

    def build(self, nn: dai.Node.Output) -> "MeasureObjectDistance":
        self.link_args(nn)
        return self

    def process(self, detections: dai.Buffer):
        assert isinstance(detections, dai.SpatialImgDetections)
        distances = []
        for det1, det2 in itertools.combinations(detections.detections, 2):
            dist = DetectionDistance(
                det1,
                det2,
                self._calc_distance(det1.spatialCoordinates, det2.spatialCoordinates),
            )
            distances.append(dist)

        obj_distances = ObjectDistances()
        obj_distances.distances = distances
        obj_distances.setTimestamp(detections.getTimestamp())
        obj_distances.setSequenceNum(detections.getSequenceNum())
        obj_distances.frame_transformation = detections.getTransformation()
        self.output.send(obj_distances)

    def _calc_distance(self, p1: dai.Point3f, p2: dai.Point3f) -> float:
        return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2) ** 0.5
