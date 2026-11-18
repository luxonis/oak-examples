from typing import Optional, Tuple

import depthai as dai

# Key -> (label, ToF profile, RVC2 host filter preset)
MODES = {
    "1": (
        "Close range",
        dai.ToFConfig.Profile.LOW_RANGE,
        dai.ImageFiltersPresetMode.TOF_LOW_RANGE,
    ),
    "2": (
        "Mid range",
        dai.ToFConfig.Profile.MID_RANGE,
        dai.ImageFiltersPresetMode.TOF_MID_RANGE,
    ),
    "3": (
        "Far range",
        dai.ToFConfig.Profile.HIGH_RANGE,
        dai.ImageFiltersPresetMode.TOF_HIGH_RANGE,
    ),
}
DEFAULT_MODE_KEY = "3"


class ToFModeControl(dai.node.HostNode):
    """Switches ToF range profiles on Visualizer key presses and shows the active mode."""

    def __init__(self) -> None:
        super().__init__()
        self._mode_key = DEFAULT_MODE_KEY
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(
        self,
        frames: dai.Node.Output,
        tof_config_queue: dai.InputQueue,
        filter_config_queue: Optional[dai.InputQueue] = None,
    ) -> "ToFModeControl":
        self.link_args(frames)
        self._tof_config_queue = tof_config_queue
        self._filter_config_queue = filter_config_queue
        return self

    def process(self, frame: dai.ImgFrame) -> None:
        annotations = self._get_annotations()
        annotations.setTimestamp(frame.getTimestamp())
        self.output.send(annotations)

    def handle_key_press(self, key: int) -> None:
        if key == -1:
            return
        key_str = chr(key)
        if key_str not in MODES or key_str == self._mode_key:
            return

        label, profile, preset = MODES[key_str]
        tof_config = dai.ToFConfig()
        tof_config.setProfilePreset(profile)
        self._tof_config_queue.send(tof_config)
        if self._filter_config_queue is not None:
            filter_config = dai.ImageFiltersConfig()
            filter_config.setProfilePreset(preset)
            self._filter_config_queue.send(filter_config)

        self._mode_key = key_str
        print(f"ToF mode: {label}")

    def _get_annotations(self) -> dai.ImgAnnotations:
        img_annotation = dai.ImgAnnotation()
        lines = [("ToF mode (keyboard controls)", False)]
        lines += [
            (f"{label} ({key})", key == self._mode_key)
            for key, (label, _, _) in MODES.items()
        ]
        for i, (text, active) in enumerate(lines):
            img_annotation.texts.append(
                self._get_text_annotation(text, (0.03, 0.06 + i * 0.07), active)
            )

        img_annotations = dai.ImgAnnotations()
        img_annotations.annotations.append(img_annotation)
        return img_annotations

    def _get_text_annotation(
        self, text: str, pos: Tuple[float, float], highlight: bool
    ) -> dai.TextAnnotation:
        annotation = dai.TextAnnotation()
        annotation.fontSize = 20
        annotation.text = text
        annotation.position = dai.Point2f(pos[0], pos[1])
        annotation.backgroundColor = dai.Color(0.0, 0.0, 0.0, 0.4)
        annotation.textColor = (
            dai.Color(0.0, 1.0, 0.0) if highlight else dai.Color(1.0, 1.0, 1.0)
        )
        return annotation
