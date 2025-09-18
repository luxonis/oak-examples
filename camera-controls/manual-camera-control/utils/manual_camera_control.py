from datetime import timedelta
from enum import Enum
from typing import Tuple
import cv2
import depthai as dai

EXP_STEP = 500
ISO_STEP = 50
LENS_STEP = 1
WB_STEP = 100

# Limits for manual controls
LENS_MIN = 0
LENS_MAX = 255
EXP_MIN = 1
# EXP_MAX is determined based on FPS
SENS_MIN = 100
SENS_MAX = 1600
WB_MIN = 1000
WB_MAX = 12000


class OtherControls(Enum):
    EXPOSURE_TIME = "1"
    SENSITIVITY_ISO = "2"
    AWB_MODE = "3"
    AE_COMPENSATION = "4"
    ANTI_BANDING_MODE = "5"
    EFFECT_MODE = "6"
    BRIGHTNESS = "7"
    CONTRAST = "8"
    SATURATION = "9"
    SHARPNESS = "0"
    LUMA_DENOISE = "]"
    CHROMA_DENOISE = "["
    WHITE_BALANCE = "o"
    LENS_POSITION = "p"


def clamp(num, v0, v1):
    return max(v0, min(num, v1))


class ManualCameraControl(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._lens_pos = 130
        self._exp_time = 20000
        self._sens_iso = 800
        self._wb_manual = 4000
        self._awb_mode_idx = 1
        self._anti_banding_mode_idx = 0
        self._effect_mode_idx = 0
        self._ae_comp = 0
        self._ae_lock = False
        self._ae_enabled = True
        self._awb_lock = False
        self._saturation = 0
        self._contrast = 0
        self._brightness = 0
        self._sharpness = 1
        self._luma_denoise = 1
        self._chroma_denoise = 1
        self._af_mode: dai.CameraControl.AutoFocusMode = (
            dai.CameraControl.AutoFocusMode.CONTINUOUS_VIDEO
        )
        self._selected_control: OtherControls | None = None
        self._capture = False

        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(
        self,
        color_cam: dai.Node.Output,
        control_queue: dai.Node.Input,
        fps: int,
    ) -> "ManualCameraControl":
        self.link_args(color_cam)
        self.control_queue = control_queue
        # Need to reduce camera FPS (see .setFps) to be able to set higher exposure time
        self._exp_max = int(0.99 * 1000000 / fps)

        return self

    def process(self, frame: dai.ImgFrame) -> None:
        annot = self._get_annotations(frame.getTimestamp())
        if self._capture:
            self._capture_frame(frame)
            self._capture = False
        self.output.send(annot)

    def handle_key_press(self, key: int) -> None:
        if key == -1:
            return
        key_str = chr(key)

        ctrl = dai.CameraControl()
        if key_str == "c":
            self._capture = True
        elif key_str == "t":
            ctrl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.AUTO)
            self._af_mode = dai.CameraControl.AutoFocusMode.AUTO
            ctrl.setAutoFocusTrigger()
            print("Autofocus trigger (and disable continuous)")
        elif key_str == "f":
            ctrl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.CONTINUOUS_VIDEO)
            self._af_mode = dai.CameraControl.AutoFocusMode.CONTINUOUS_VIDEO
            print("Autofocus enable, continuous")
        elif key_str == "e":
            ctrl.setAutoExposureEnable()
            print("Autoexposure enable")
            self._ae_enabled = True
        elif key_str == "w":
            self._awb_lock = not self._awb_lock
            ctrl.setAutoWhiteBalanceLock(self._awb_lock)
            print("Auto white balance lock:", self._awb_lock)
        elif key_str == "r":
            self._ae_lock = not self._ae_lock
            ctrl.setAutoExposureLock(self._ae_lock)
            print("Auto exposure lock:", self._ae_lock)
        elif key_str in [i.value for i in OtherControls]:
            self._selected_control = OtherControls(key_str)
            print("Selected control:", self._selected_control.name)
        elif key_str in ["-", "_"]:
            ctrl = self._change_selected_control(ctrl, -1)
        elif key_str in ["+", "="]:
            ctrl = self._change_selected_control(ctrl, 1)

        self.control_queue.send(ctrl)

    def _change_selected_control(self, ctrl: dai.CameraControl, change: int) -> None:
        if self._selected_control is None:
            print("Please select a control first using keys 3..9, 0, [ ]")
            return ctrl
        elif self._selected_control == OtherControls.EXPOSURE_TIME:
            self._ae_enabled = False
            self._exp_time = clamp(
                self._exp_time + change * EXP_STEP, EXP_MIN, self._exp_max
            )
            ctrl.setManualExposure(self._exp_time, self._sens_iso)
            print(
                "Setting manual exposure, time:",
                self._exp_time,
                "iso:",
                self._sens_iso,
            )
        elif self._selected_control == OtherControls.SENSITIVITY_ISO:
            self._ae_enabled = False
            self._sens_iso = clamp(
                self._sens_iso + change * ISO_STEP, SENS_MIN, SENS_MAX
            )
            ctrl.setManualExposure(self._exp_time, self._sens_iso)
            print(
                "Setting manual exposure, time:",
                self._exp_time,
                "iso:",
                self._sens_iso,
            )
        elif self._selected_control == OtherControls.AWB_MODE:
            count = len(list(dai.CameraControl.AutoWhiteBalanceMode.__members__))
            self._awb_mode_idx = (self._awb_mode_idx + change) % count
            awb_mode = dai.CameraControl.AutoWhiteBalanceMode(self._awb_mode_idx)
            ctrl.setAutoWhiteBalanceMode(awb_mode)
            print("Auto white balance mode:", awb_mode)
        elif self._selected_control == OtherControls.AE_COMPENSATION:
            self._ae_comp = clamp(self._ae_comp + change, -9, 9)
            ctrl.setAutoExposureCompensation(self._ae_comp)
            print("Auto exposure compensation:", self._ae_comp)
        elif self._selected_control == OtherControls.ANTI_BANDING_MODE:
            count = len(list(dai.CameraControl.AntiBandingMode.__members__))
            self._anti_banding_mode_idx = (self._anti_banding_mode_idx + change) % count
            anti_banding_mode = dai.CameraControl.AntiBandingMode(
                self._anti_banding_mode_idx
            )
            ctrl.setAntiBandingMode(anti_banding_mode)
            print("Anti-banding mode:", anti_banding_mode)
        elif self._selected_control == OtherControls.EFFECT_MODE:
            count = len(list(dai.CameraControl.EffectMode.__members__))
            self._effect_mode_idx = (self._effect_mode_idx + change) % count
            effect_mode = dai.CameraControl.EffectMode(self._effect_mode_idx)
            ctrl.setEffectMode(effect_mode)
            print("Effect mode:", effect_mode)
        elif self._selected_control == OtherControls.BRIGHTNESS:
            self._brightness = clamp(self._brightness + change, -10, 10)
            ctrl.setBrightness(self._brightness)
            print("Brightness:", self._brightness)
        elif self._selected_control == OtherControls.CONTRAST:
            self._contrast = clamp(self._contrast + change, -10, 10)
            ctrl.setContrast(self._contrast)
            print("Contrast:", self._contrast)
        elif self._selected_control == OtherControls.SATURATION:
            self._saturation = clamp(self._saturation + change, -10, 10)
            ctrl.setSaturation(self._saturation)
            print("Saturation:", self._saturation)
        elif self._selected_control == OtherControls.SHARPNESS:
            self._sharpness = clamp(self._sharpness + change, 0, 4)
            ctrl.setSharpness(self._sharpness)
            print("Sharpness:", self._sharpness)
        elif self._selected_control == OtherControls.WHITE_BALANCE:
            self._wb_manual = clamp(self._wb_manual + change * WB_STEP, WB_MIN, WB_MAX)
            ctrl.setManualWhiteBalance(self._wb_manual)

            if self._awb_lock:
                self._awb_lock = False
                ctrl.setAutoWhiteBalanceLock(False)
            print("Setting manual white balance, temperature: ", self._wb_manual, "K")
        elif self._selected_control == OtherControls.LENS_POSITION:
            self._lens_pos = clamp(
                self._lens_pos + change * LENS_STEP, LENS_MIN, LENS_MAX
            )
            ctrl.setManualFocus(self._lens_pos)
            print("Setting manual focus, lens position:", self._lens_pos)
        elif self._selected_control == OtherControls.LUMA_DENOISE:
            self._luma_denoise = clamp(self._luma_denoise + change, 0, 4)
            ctrl.setLumaDenoise(self._luma_denoise)
            print("Luma denoise:", self._luma_denoise)
        elif self._selected_control == OtherControls.CHROMA_DENOISE:
            self._chroma_denoise = clamp(self._chroma_denoise + change, 0, 4)
            ctrl.setChromaDenoise(self._chroma_denoise)
            print("Chroma denoise:", self._chroma_denoise)

        return ctrl

    def _get_annotations(self, timestamp: timedelta) -> dai.ImgAnnotations:
        img_annotations = dai.ImgAnnotations()
        img_annotation = dai.ImgAnnotation()
        txts = [
            ("Camera Configuration (Keyboard controls)", False),
            (f"Autoexposure (e): {self._ae_enabled}", False),
            (f"Autofocus (t, f): {self._af_mode.name}", False),
            (f"AWB lock (w): {self._awb_lock}", False),
            (f"AE lock (r): {self._ae_lock}", False),
            ("", False),
            ("Manual controls:", False),
            (
                f"Exposure time (1): {self._exp_time}",
                self._selected_control == OtherControls.EXPOSURE_TIME,
            ),
            (
                f"Sensitivity ISO (2): {self._sens_iso}",
                self._selected_control == OtherControls.SENSITIVITY_ISO,
            ),
            (
                f"AWB mode (3): {dai.CameraControl.AutoWhiteBalanceMode(self._awb_mode_idx).name}",
                self._selected_control == OtherControls.AWB_MODE,
            ),
            (
                f"AE compensation (4): {self._ae_comp}",
                self._selected_control == OtherControls.AE_COMPENSATION,
            ),
            (
                f"Anti-banding mode (5): {dai.CameraControl.AntiBandingMode(self._anti_banding_mode_idx).name}",
                self._selected_control == OtherControls.ANTI_BANDING_MODE,
            ),
            (
                f"Effect mode (6): {dai.CameraControl.EffectMode(self._effect_mode_idx).name}",
                self._selected_control == OtherControls.EFFECT_MODE,
            ),
            (
                f"Brightness (7): {self._brightness}",
                self._selected_control == OtherControls.BRIGHTNESS,
            ),
            (
                f"Contrast (8): {self._contrast}",
                self._selected_control == OtherControls.CONTRAST,
            ),
            (
                f"Saturation (9): {self._saturation}",
                self._selected_control == OtherControls.SATURATION,
            ),
            (
                f"Sharpness (0): {self._sharpness}",
                self._selected_control == OtherControls.SHARPNESS,
            ),
            (
                f"White balance (o): {self._wb_manual}",
                self._selected_control == OtherControls.WHITE_BALANCE,
            ),
            (
                f"Lens position (p): {self._lens_pos}",
                self._selected_control == OtherControls.LENS_POSITION,
            ),
            (
                f"Chroma denoise ([): {self._chroma_denoise}",
                self._selected_control == OtherControls.CHROMA_DENOISE,
            ),
            (
                f"Luma denoise (]): {self._luma_denoise}",
                self._selected_control == OtherControls.LUMA_DENOISE,
            ),
        ]
        for i, (txt, highlight) in enumerate(txts):
            if highlight:
                txt += " (use + / - keys to change)"
            txt_annot = self._get_text_annotation(
                txt, (0.05, 0.05 + i * 0.03), highlight
            )
            img_annotation.texts.append(txt_annot)

        img_annotation.texts.append(
            self._get_text_annotation("Capture image (c)", (0.8, 0.05))
        )
        img_annotations.annotations.append(img_annotation)
        img_annotations.setTimestamp(timestamp)
        return img_annotations

    def _get_text_annotation(
        self, txt: str, pos: Tuple[float, float], highlight: bool = False
    ) -> dai.TextAnnotation:
        txt_annot = dai.TextAnnotation()
        txt_annot.fontSize = 25
        txt_annot.text = txt
        txt_annot.position = dai.Point2f(pos[0], pos[1])
        txt_annot.backgroundColor = dai.Color(0.0, 0.0, 0.0, 0.2)
        if highlight:
            txt_annot.textColor = dai.Color(0.0, 1.0, 0.0)
        else:
            txt_annot.textColor = dai.Color(1.0, 1.0, 1.0)
        return txt_annot

    def _capture_frame(self, frame: dai.ImgFrame) -> None:
        img_frame = frame.getCvFrame()
        h, w, _ = img_frame.shape
        capture_file_name = f"capture_{w}x{h}_{frame.getSequenceNum()}.jpg"
        cv2.imwrite(capture_file_name, img_frame)
