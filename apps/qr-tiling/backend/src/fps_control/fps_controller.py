import depthai as dai


class FPSController(dai.node.ThreadedHostNode):
    """Throttles two synchronized streams to a target FPS using a Script node."""

    SCRIPT_TEMPLATE = """
    msg = node.inputs['target_fps'].get()
    target_fps = msg.getData()[0]
    max_fps = {max_fps}
    frame_budget = 0

    while True:
        while node.inputs['target_fps'].has():
            msg = node.inputs['target_fps'].get()
            target_fps = msg.getData()[0]

        nn_frame = node.inputs['nn_frames'].get()
        display_frame = node.inputs['display_frames'].get()

        frame_budget += target_fps

        if frame_budget >= max_fps:
            frame_budget -= max_fps
            node.outputs['rgb_nn'].send(nn_frame)
            node.outputs['rgb_display'].send(display_frame)
    """

    def __init__(self) -> None:
        super().__init__()
        self._pipeline = self.getParentPipeline()
        self._script = self._pipeline.create(dai.node.Script)

    def build(
        self,
        nn_frames: dai.Node.Output,
        display_frames: dai.Node.Output,
        max_fps: int = 30,
    ) -> "FPSController":
        self._script.setScript(self.SCRIPT_TEMPLATE.format(max_fps=max_fps))

        nn_frames.link(self._script.inputs["nn_frames"])
        display_frames.link(self._script.inputs["display_frames"])

        self._script.inputs["target_fps"].setBlocking(False)

        return self

    def run(self) -> None:
        pass

    @property
    def rgb_nn(self) -> dai.Node.Output:
        return self._script.outputs["rgb_nn"]

    @property
    def rgb_display(self) -> dai.Node.Output:
        return self._script.outputs["rgb_display"]

    @property
    def target_fps(self) -> dai.Node.Input:
        return self._script.inputs["target_fps"]
