from dataclasses import dataclass
import depthai as dai


@dataclass
class VideoConfig:
    fps: int
    frame_type: dai.ImgFrame.Type
    width: int
    height: int


@dataclass
class ModelNames:
    face: str
    emotions: str
    age_gender: str
    people: str
    reid: str
