from typing import Tuple, Optional, List
import numpy as np

import depthai as dai


class FaceData(dai.Buffer):
    """Message representing face attributes

    Attributes
    ----------
    bbox : Tuple[float, float, float, float]; face bbox in normalized coords
    age : int
    gender : str
    emotion : str
    embedding : np.ndarray
    crop : dai.ImgFrame
    """

    def __init__(
        self,
        bbox: Tuple[float, float, float, float],
        age: int,
        gender: str,
        emotion: str,
        embedding: Optional[np.ndarray],
        crop: dai.ImgFrame,
    ):
        super().__init__()
        self.bbox = bbox
        self.age = age
        self.gender = gender
        self.emotion = emotion
        self.embedding = embedding
        self.crop = crop


class PersonData(dai.Buffer):
    """Message representing person data

    Attributes
    ----------
    face : Optional[FaceData]; may be None if no face matched
    bbox : Tuple[float, float, float, float]; person bbox (tracklet ROI)
    re_id : str
    reid_status: str; "TBD" | "NEW" | "REID" | None
    tracking_id : int
    tracking_status : str
    """

    def __init__(
        self,
        face: Optional[FaceData],
        bbox: Tuple[float, float, float, float],
        re_id: Optional[str],
        reid_status: Optional[str],
        tracking_id: int,
        tracking_status: str,
    ):
        super().__init__()
        self.face = face
        self.bbox = bbox
        self.re_id = re_id
        self.reid_status = reid_status
        self.tracking_id = tracking_id
        self.tracking_status = tracking_status


class PeopleMessage(dai.Buffer):
    """
    Attributes
    ----------
    people : List[PersonData]
    """

    def __init__(
        self,
        people: List[PersonData],
    ):
        super().__init__()
        self.people = people


class FaceFeaturesMessage(dai.Buffer):
    """
    Attributes
    ----------
    faces : List[FaceData]
    """

    def __init__(
        self,
        faces: List[FaceData],
    ):
        super().__init__()
        self.faces = faces
