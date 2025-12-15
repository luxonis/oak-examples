import depthai as dai
from typing import List

from messages.messages import PersonData, PeopleMessage, FaceData
from .associator import PersonFaceAssociator
from .reid_manager import ReIdManager

LIVE = (
    dai.Tracklet.TrackingStatus.TRACKED,
    dai.Tracklet.TrackingStatus.LOST,
    dai.Tracklet.TrackingStatus.NEW,
)


class PeopleJoinNode(dai.node.HostNode):
    """
    Fuses face attributes + person tracklets into PersonData messages.

    Inputs:
      - in_faces: FaceFeaturesMessage (faces: List[FaceData])
      - in_tracklets: dai.Tracklets

    Output:
      - out: PeopleMessage (people: List[PersonData])
    """

    def __init__(self) -> None:
        super().__init__()
        self.in_faces = self.createInput()
        self.in_tracklets = self.createInput()

        self._associator = PersonFaceAssociator()
        self._reid_manager = ReIdManager()

    def build(
        self, faces: dai.Node.Output, tracklets: dai.Node.Output
    ) -> "PeopleJoinNode":
        self.link_args(faces, tracklets)
        return self

    def process(self, faces_msg: dai.Buffer, tracklets_msg: dai.Tracklets) -> None:
        faces: List[FaceData] = faces_msg.faces
        tracklets_all = tracklets_msg.tracklets
        tracklets_live = [
            tracklet for tracklet in tracklets_all if tracklet.status in LIVE
        ]

        active_ids = {tracklet.id for tracklet in tracklets_live}
        self._reid_manager.cleanup(active_ids)

        candidates = self._associator.match(faces, tracklets_live)
        people: List[PersonData] = []

        for candidate in candidates:
            rid = None
            status = "TBD"
            face = candidate.face

            if face and face.embedding is not None:
                rid, status = self._reid_manager.update(
                    tracklet_id=candidate.tracklet_id,
                    embedding=face.embedding,
                )

            person = PersonData(
                face=face,
                bbox=candidate.bbox,
                re_id=rid,
                reid_status=status,
                tracking_id=candidate.tracklet_id,
                tracking_status=candidate.tracking_status,
            )
            people.append(person)

        out_msg = PeopleMessage(people)
        out_msg.setTimestamp(tracklets_msg.getTimestamp())
        out_msg.setSequenceNum(tracklets_msg.getSequenceNum())
        self.out.send(out_msg)
