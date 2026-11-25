from datetime import timedelta

import depthai as dai


class SaveMessage(dai.Buffer):
    def __init__(self, request):
        super().__init__()
        self.request = request


class SaveAck(dai.Buffer):
    def __init__(self, request, error=None):
        super().__init__()
        self.request, self.error = request, error


class StorageHostNode(dai.node.ThreadedHostNode):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.inputJobs = self.createInput("jobs", blocking=False, queueSize=1)
        self.outSaved = self.createOutput("saved")

    def run(self):
        while self.isRunning():
            message = self.inputJobs.get(timedelta(seconds=1))
            if message is None:
                continue
            error = None
            try:
                self.store.save(message.request)
            except Exception as exception:
                error = str(exception)
            if self.isRunning():
                self.outSaved.send(SaveAck(message.request, error))
