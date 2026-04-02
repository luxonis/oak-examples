import time

import depthai as dai

from depthai_nodes.node.base_threaded_host_node import BaseThreadedHostNode
from depthai_nodes.node.utils.message_remapping import remap_message


class CoordinatesMapper(BaseThreadedHostNode):
    SCRIPT_CONTENT = """
# Strip ImgFrame image data and send only ImgTransformation
# Reduces the amount of date being sent between host and device

try:
    while True:
        message = node.inputs['message'].get()
        transformation = message.getTransformation()
        empty_frame = ImgFrame()
        empty_frame.setTransformation(transformation)
        empty_frame.setTimestamp(message.getTimestamp())
        empty_frame.setTimestampDevice(message.getTimestampDevice())
        node.outputs['transformation'].send(empty_frame)
except Exception as e:
    node.warn(str(e))
"""

    def __init__(self) -> None:
        super().__init__()
        if self._platform == dai.Platform.RVC2:
            raise RuntimeError(
                "CoordinatesMapper node is currently not supported on RVC2."
            )
        self._to_transformation_input = self.createInput()
        self._from_transformation_input = self.createInput()
        self._out = self.createOutput()
        self._cached_transformation: dai.ImgTransformation | None = None

    @property
    def out(self) -> dai.Node.Output:
        """Return the remapped output stream."""
        return self._out

    def build(
        self,
        toTransformationInput: dai.Node.Output,
        fromTransformationInput: dai.Node.Output,
    ) -> "CoordinatesMapper":
        """Connect the target and source streams used for coordinate remapping.

        Parameters
        ----------
        toTransformationInput
            Stream providing messages whose transformation defines the target
            reference frame.
        fromTransformationInput
            Stream providing messages whose coordinates should be remapped.

        Returns
        -------
        CoordinatesMapper
            The configured node instance.
        """
        script = self._pipeline.create(dai.node.Script)
        script.setScript(self.SCRIPT_CONTENT)
        toTransformationInput.link(script.inputs["message"])
        script.outputs["transformation"].setPossibleDatatypes(
            [(dai.DatatypeEnum.ImgFrame, True)]
        )
        script.outputs["transformation"].link(self._to_transformation_input)
        fromTransformationInput.link(self._from_transformation_input)
        self._logger.debug("CoordinatesMapper built")
        return self

    def run(self) -> None:
        """Cache the latest target transformation and remap incoming messages."""
        first_target_msg = self._to_transformation_input.get()
        self._cached_transformation = self._extract_transformation(first_target_msg)
        last_report = time.monotonic()
        durations = []
        total_durations = []

        while self.isRunning():
            start_time = time.monotonic()
            new_target_msg = self._to_transformation_input.tryGet()
            # if new_target_msg is not None:
            #     self._cached_transformation = self._extract_transformation(
            #         new_target_msg
            #     )
            # from_transformation_msg = self._from_transformation_input.get()
            # remapped_message = self._remap_message(
            #     msg=from_transformation_msg,
            #     to_transformation=self._cached_transformation,
            # )
            remapped_message = self._from_transformation_input.get()

            end_time = time.monotonic()
            durations.append(end_time - start_time)
            self.out.send(remapped_message)
            total_end_time = time.monotonic()
            total_durations.append(total_end_time - start_time)
            if end_time - last_report > 2:
                last_report = end_time
                avg_duration = sum(durations) / len(durations)
                avg_total_duration = sum(total_durations) / len(total_durations)
                print(
                    f"MAPPER AVG BEFORE SEND: {avg_duration} s THEORETICAL MAX FPS: {1 / avg_duration}"
                )
                print(
                    f"MAPPER AVG AFTER SEND: {avg_total_duration} s THEORETICAL MAX FPS: {1 / avg_total_duration}"
                )
                durations.clear()

    def _extract_transformation(
        self, to_transformation_msg: dai.ImgFrame
    ) -> dai.ImgTransformation:
        try:
            to_transformation: dai.ImgTransformation = (
                to_transformation_msg.getTransformation()
            )
        except Exception as e:
            raise RuntimeError(
                "Could not get transformation from `to_transformation_msg` message. Message doesn't have the `getTransformation()` method."
            ) from e
        if to_transformation is None:
            raise RuntimeError(
                "Received `to_transformation_msg` message without transformation. The `getTransformation()` method returns None."
            )
        return to_transformation

    def _remap_message(self, msg: dai.Buffer, to_transformation: dai.ImgTransformation):
        if isinstance(msg, dai.MessageGroup):
            new_msg_group = dai.MessageGroup()
            for name in msg.getMessageNames():
                new_msg = self._remap_message(msg[name], to_transformation)
                new_msg_group[name] = new_msg
            new_msg_group.setTimestamp(msg.getTimestamp())
            new_msg_group.setSequenceNum(msg.getSequenceNum())
            new_msg_group.setTimestampDevice(msg.getTimestampDevice())
            return new_msg_group
        try:
            remapped_msg = remap_message(
                message=msg,
                from_transformation=msg.getTransformation(),
                to_transformation=to_transformation,
            )
        except TypeError as e:
            self._logger.error(e)
            remapped_msg = msg
        remapped_msg.setTransformation(to_transformation)
        remapped_msg.setTimestamp(msg.getTimestamp())
        remapped_msg.setSequenceNum(msg.getSequenceNum())
        remapped_msg.setTimestampDevice(msg.getTimestampDevice())
        return remapped_msg
