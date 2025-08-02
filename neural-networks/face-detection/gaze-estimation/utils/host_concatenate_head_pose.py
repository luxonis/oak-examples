import depthai as dai
from depthai_nodes.message import Predictions
import numpy as np


class ConcatenateHeadPose(dai.node.HostNode):
    def __init__(self):
        super().__init__()

        self.output = self.createOutput()

    def build(
        self,
        yaw_intput: dai.Node.Output,
        pitch_input: dai.Node.Output,
        roll_input: dai.Node.Output,
    ) -> "ConcatenateHeadPose":
        self.link_args(yaw_intput, pitch_input, roll_input)

        return self

    def process(
        self,
        yaw_msg: dai.Buffer,
        pitch_msg: dai.Buffer,
        roll_msg: dai.Buffer,
    ) -> None:
        assert isinstance(yaw_msg, Predictions)
        assert isinstance(pitch_msg, Predictions)
        assert isinstance(roll_msg, Predictions)

        ts = yaw_msg.getTimestamp()
        seq_num = yaw_msg.getSequenceNum()

        yaw = yaw_msg.predictions[0].prediction
        pitch = pitch_msg.predictions[0].prediction
        roll = roll_msg.predictions[0].prediction
        output = np.array([[yaw, pitch, roll]], dtype=np.float16)

        output_msg = dai.NNData()

        output_msg.addTensor("head_pose_angles_yaw_pitch_roll", output)
        output_msg.setTimestamp(ts)
        output_msg.setSequenceNum(seq_num)

        self.output.send(output_msg)
