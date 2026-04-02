import time

import depthai as dai

from depthai_nodes.node.base_threaded_host_node import BaseThreadedHostNode


class CoordinatesMapperTest(BaseThreadedHostNode):
    def __init__(self) -> None:
        super().__init__()
        if self._platform == dai.Platform.RVC2:
            raise RuntimeError(
                "CoordinatesMapper node is currently not supported on RVC2."
            )
        self.input = self.createInput()
        self.out = self.createOutput()

    def build(self, input: dai.Node.Output) -> "CoordinatesMapper":
        input.link(self.input)
        self._logger.debug("CoordinatesMapper built")
        return self

    def run(self) -> None:
        last_report = time.monotonic()
        durations = []
        total_durations = []
        while self.isRunning():
            start_time = time.monotonic()
            remapped_message = self.input.get()
            end_time = time.monotonic()
            durations.append(end_time - start_time)
            self.out.send(remapped_message)
            total_end_time = time.monotonic()
            total_durations.append(total_end_time - start_time)
            if end_time - last_report > 2:
                last_report = end_time
                avg_duration = sum(durations) / len(durations)
                avg_total_duration = sum(total_durations) / len(total_durations)
                print(f"TOOK AVG: {avg_duration} ms FPS: {1 / avg_duration}")
                print(
                    f"TOTA AVG: {avg_total_duration} ms FPS: {1 / avg_total_duration}"
                )
                durations.clear()
