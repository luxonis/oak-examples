import depthai as dai


class ManualCameraControl(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.control_queue = None
        self.current_config = dai.NeuralDepthConfig()

    def build(
        self, frame: dai.Node.Output, control_queue: dai.Node.Input
    ) -> "ManualCameraControl":
        self.link_args(frame)
        self.control_queue = control_queue
        return self

    def process(self, frame):
        img_annotations = dai.ImgAnnotations()
        img_annotation = dai.ImgAnnotation()
        txts = [
            f"Curr conf thr: {self.current_config.getConfidenceThreshold()} (Use W / S to change)",
            f"Curr edge thr: {self.current_config.getEdgeThreshold()} (Use A / D to change)",
        ]

        for i, txt in enumerate(txts):
            txt_annot = self._get_text_annotation(txt, (0.05, 0.05 + i * 0.03))
            img_annotation.texts.append(txt_annot)

        img_annotations.annotations.append(img_annotation)
        img_annotations.setTimestamp(frame.getTimestamp())

        self.out.send(img_annotations)

    def handle_key_press(self, key: int) -> None:
        if key == ord("w"):
            currentThreshold = self.current_config.getConfidenceThreshold()
            self.current_config.setConfidenceThreshold((currentThreshold + 5) % 255)
            print(
                "Setting confidence threshold to:",
                self.current_config.getConfidenceThreshold(),
            )
            self.control_queue.send(self.current_config)
        if key == ord("s"):
            currentThreshold = self.current_config.getConfidenceThreshold()
            self.current_config.setConfidenceThreshold((currentThreshold - 5) % 255)
            print(
                "Setting confidence threshold to:",
                self.current_config.getConfidenceThreshold(),
            )
            self.control_queue.send(self.current_config)
        if key == ord("d"):
            currentThreshold = self.current_config.getEdgeThreshold()
            self.current_config.setEdgeThreshold((currentThreshold + 1) % 255)
            print("Setting edge threshold to:", self.current_config.getEdgeThreshold())
            self.control_queue.send(self.current_config)
        if key == ord("a"):
            currentThreshold = self.current_config.getEdgeThreshold()
            self.current_config.setEdgeThreshold((currentThreshold - 1) % 255)
            print("Setting edge threshold to:", self.current_config.getEdgeThreshold())
            self.control_queue.send(self.current_config)

    def _get_text_annotation(
        self, txt: str, pos: tuple[float, float]
    ) -> dai.TextAnnotation:
        txt_annot = dai.TextAnnotation()
        txt_annot.fontSize = 15
        txt_annot.text = txt
        txt_annot.position = dai.Point2f(pos[0], pos[1])
        txt_annot.backgroundColor = dai.Color(0.0, 0.0, 0.0, 0.2)
        txt_annot.textColor = dai.Color(1.0, 1.0, 1.0)
        return txt_annot
