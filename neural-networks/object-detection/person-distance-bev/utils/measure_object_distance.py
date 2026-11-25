import itertools
import math

import depthai as dai


class DetectionDistance:
    def __init__(
        self,
        detection1: dai.Tracklet,
        detection2: dai.Tracklet,
        distance: float,
    ) -> None:
        self.detection1 = detection1
        self.detection2 = detection2
        self.distance = distance


class ObjectDistances(dai.Buffer):
    def __init__(self) -> None:
        super().__init__(0)
        self.tracklets: list[dai.Tracklet] = []
        self.spatial_tracklets: list[dai.Tracklet] = []
        self.distances: list[DetectionDistance] = []


def has_valid_coordinates(tracklet: dai.Tracklet) -> bool:
    coordinates = tracklet.spatialCoordinates
    return (
        all(
            math.isfinite(value)
            for value in (coordinates.x, coordinates.y, coordinates.z)
        )
        and coordinates.z > 0
    )


def measure_tracklets(tracklets: dai.Tracklets) -> ObjectDistances:
    active = [
        tracklet
        for tracklet in tracklets.tracklets
        if tracklet.status
        in (dai.Tracklet.TrackingStatus.NEW, dai.Tracklet.TrackingStatus.TRACKED)
    ]
    spatial = [tracklet for tracklet in active if has_valid_coordinates(tracklet)]

    result = ObjectDistances()
    result.tracklets = active
    result.spatial_tracklets = spatial
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
        for first, second in itertools.combinations(spatial, 2)
    ]
    result.setTimestamp(tracklets.getTimestamp())
    result.setSequenceNum(tracklets.getSequenceNum())
    return result


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

    def process(self, tracklets: dai.Tracklets) -> None:
        self.output.send(measure_tracklets(tracklets))
