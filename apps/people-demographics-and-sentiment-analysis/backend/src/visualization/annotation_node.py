from typing import List, Optional, Tuple
import depthai as dai

from depthai_nodes.utils import AnnotationHelper
from messages.messages import PeopleMessage, PersonData, FaceData

LIVE_TRACKLET_STATUSES = ("TRACKED", "NEW")


RED = (1.0, 0.0, 0.0, 1.0)
GREEN = (0.0, 1.0, 0.0, 1.0)
BLUE = (0.0, 0.0, 1.0, 1.0)
GRAY = (0.7, 0.7, 0.7, 1.0)

RED_TRANSPARENT = (1.0, 0.0, 0.0, 0.1)
GREEN_TRANSPARENT = (0.0, 1.0, 0.0, 0.1)
BLUE_TRANSPARENT = (0.0, 0.0, 1.0, 0.1)
GRAY_TRANSPARENT = (0.7, 0.7, 0.7, 0.1)

TEXT_COLOR = (1.0, 1.0, 1.0, 1.0)
TEXT_BG = (0.0, 0.0, 0.0, 0.35)


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()

    def build(self, joined: dai.Node.Output) -> "AnnotationNode":
        self.link_args(joined)
        return self

    def process(self, msg: dai.Buffer) -> None:
        assert isinstance(msg, PeopleMessage)
        people: List[PersonData] = msg.people

        ann = AnnotationHelper()

        for person in people:
            if person.tracking_status not in LIVE_TRACKLET_STATUSES:
                continue

            face: Optional[FaceData] = person.face
            x1, y1, x2, y2 = person.bbox

            outline_color, fill_color = self._get_style(person)
            label = self._build_label(person, face)

            ann.draw_rectangle(
                (x1, y1), (x2, y2), outline_color=outline_color, fill_color=fill_color
            )
            ann.draw_text(
                label,
                (x1 + 0.005, y2 - 0.025),
                size=18,
                color=TEXT_COLOR,
                background_color=TEXT_BG,
            )

        out = ann.build(timestamp=msg.getTimestamp(), sequence_num=msg.getSequenceNum())
        self.out.send(out)

    def _get_style(self, person: PersonData) -> Tuple[tuple, tuple]:
        """Returns (Outline Color, Fill Color) based on state."""
        face = person.face

        if not face:
            return GRAY, GRAY_TRANSPARENT

        status = person.reid_status

        if status == "TBD":
            return RED, RED_TRANSPARENT

        elif status == "NEW":
            return BLUE, BLUE_TRANSPARENT

        elif status == "REID":
            return GREEN, GREEN_TRANSPARENT

        return GRAY, GRAY_TRANSPARENT

    def _build_label(self, person: PersonData, face: Optional[FaceData]) -> str:
        lines = []

        if person.reid_status == "REID" and person.re_id:
            lines.append(f"reID: {person.re_id} | re-identified")
        elif person.reid_status == "NEW" and person.re_id:
            lines.append(f"reID: {person.re_id} | new person")

        lines.append(f"Track ID: {person.tracking_id}")

        if face and face.age is not None and face.gender:
            features = f"{face.gender}, {face.age}"
            if face.emotion:
                features += f" | {face.emotion}"
            lines.append(features)

        return "\n".join(lines)
