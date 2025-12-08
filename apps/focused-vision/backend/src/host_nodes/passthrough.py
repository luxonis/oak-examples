import depthai as dai
import time


class Passthrough(dai.node.ThreadedHostNode):
    def __init__(self):
        super().__init__()  # Call the base class constructor
        self.out = (
            self.createOutput()
        )  # Create an output queue - this will send ImgFrame messages
        self.input_1 = self.createInput()
        self.input_2 = self.createInput()

    def build(self, input_1: dai.Node.Output, input_2: dai.Node.Output):
        input_1.link(self.input_1)
        input_2.link(self.input_2)
        return self

    def run(self):
        while self.isRunning():
            message = self.input_1.tryGet()
            if message is not None:
                self.out.send(message)
            message = self.input_2.tryGet()
            if message is not None:
                self.out.send(message)
            time.sleep(0.01)
