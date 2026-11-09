import json

import depthai as dai


class AutoCalibrationStatus(dai.node.HostNode):
    """Display native automatic calibration results over the depth preview."""

    def __init__(self):
        super().__init__()
        self.in_results = self.createInput(
            types=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.AutoCalibrationResult, True)
            ],
            blocking=False,
            queueSize=8,
            waitForMessage=False,
        )
        self.out_annotations = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self._mode = None
        self._calibration = None
        self._result = None

    def build(self, preview, results, mode, calibration):
        self.link_args(preview)
        results.link(self.in_results)
        self._mode = mode
        self._calibration = calibration
        return self

    def process(self, frame: dai.ImgFrame):
        while True:
            result = self.in_results.tryGet()
            if result is None:
                break
            # The native node already applies accepted results. A pass can also
            # validate the existing parameters; never apply results from this HUD.
            changed = False
            if result.passed:
                changed = (
                    self._calibration.eepromToJson()
                    != result.calibration.eepromToJson()
                )
                self._calibration = result.calibration
            self._result = {
                "passed": result.passed,
                "dataConfidence": result.dataConfidence,
                "calibrationConfidence": result.calibrationConfidence,
                "calibrationChanged": changed,
                "flashCalibration": False,
            }
            print("AutoCalibration: " + json.dumps(self._result), flush=True)

        lines = [
            f"AutoCalibration - {self._mode}",
            "Waiting for validation result",
            "Runtime updates only; EEPROM flashing disabled",
        ]
        if self._result:
            result = self._result
            lines[1] = (
                "Validation passed; runtime calibration active"
                if result["passed"]
                else "Validation failed; calibration unchanged"
            )
            lines += [
                f"Data confidence: {result['dataConfidence']:.3f}",
                f"Calibration confidence: {result['calibrationConfidence']:.3f}",
                f"Calibration parameters changed: {result['calibrationChanged']}",
            ]
        lines.append("[q] Quit")

        annotations = dai.ImgAnnotations()
        annotation = dai.ImgAnnotation()
        for index, line in enumerate(lines):
            text = dai.TextAnnotation()
            text.text = line
            text.position = dai.Point2f(0.04, 0.075 + index * 0.035)
            text.fontSize = 18
            text.textColor = dai.Color(1, 1, 1, 1)
            text.backgroundColor = dai.Color(0, 0, 0, 0.55)
            annotation.texts.append(text)
        annotations.annotations.append(annotation)
        annotations.setTimestamp(frame.getTimestamp())
        self.out_annotations.send(annotations)
