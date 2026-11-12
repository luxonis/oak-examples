import statistics
import time

import depthai as dai


class LatencyMeter(dai.node.HostNode):
    """Collects message age and observed FPS for one pipeline output."""

    def __init__(self) -> None:
        super().__init__()
        self._name = "LatencyMeter"
        self._reset_stats()

    def build(
        self,
        benchmark_input: dai.Node.Output,
        name: str = "LatencyMeter",
    ) -> "LatencyMeter":
        self._name = name
        self.link_args(benchmark_input)
        self._reset_stats()
        return self

    def process(self, msg: dai.Buffer) -> None:
        now = time.monotonic()
        latency = dai.Clock.now() - msg.getTimestamp()      # type: ignore
        self._latencies_ms.append(latency.total_seconds() * 1000.0)
        self._timestamps.append(now)

    def get_and_reset_stats(self) -> dict[str, float] | None:
        if not self._latencies_ms:
            return None

        elapsed = self._timestamps[-1] - self._timestamps[0]
        fps = (len(self._timestamps) - 1) / elapsed if elapsed > 0 else 0.0
        stats = {
            "avg": statistics.mean(self._latencies_ms),
            "median": statistics.median(self._latencies_ms),
            "min": min(self._latencies_ms),
            "max": max(self._latencies_ms),
            "count": len(self._latencies_ms),
            "fps": fps,
        }
        self._reset_stats()
        return stats

    def _reset_stats(self) -> None:
        self._latencies_ms: list[float] = []
        self._timestamps: list[float] = []

    @property
    def name(self) -> str:
        return self._name
