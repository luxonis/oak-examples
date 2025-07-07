import depthai as dai
import datetime


class FrameEditor(dai.node.ThreadedHostNode):
    def __init__(self, instance_num):
        super().__init__()
        self.input = self.createInput()
        self.output = self.createOutput()
        self.timestamp = 0
        self.frame_interval = 33
        self.instance_num = instance_num

    def run(self):
        while self.isRunning():
            buffer: dai.ImgFrame = self.input.get()

            buffer.setInstanceNum(self.instance_num)
            tstamp = datetime.timedelta(
                seconds=self.timestamp // 1000, milliseconds=self.timestamp % 1000
            )
            buffer.setTimestamp(tstamp)
            buffer.setTimestampDevice(tstamp)

            self.output.send(buffer)
            self.timestamp += self.frame_interval
