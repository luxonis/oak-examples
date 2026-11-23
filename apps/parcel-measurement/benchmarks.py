from dataclasses import dataclass


@dataclass
class BenchmarkWindow:
    started_at: float
    interval_seconds: float = 10.0
    messages: int = 0
    failed_messages: int = 0
    latency_samples: int = 0
    latency_seconds: float = 0.0

    def record_message(self, failed=False):
        self.messages += 1
        self.failed_messages += int(failed)

    def add_report(self, samples, average_latency_seconds):
        self.latency_samples += samples
        self.latency_seconds += samples * average_latency_seconds

    def report(self, now):
        elapsed = now - self.started_at
        if elapsed < self.interval_seconds:
            return None
        result = {
            "window_seconds": elapsed,
            "messages": self.messages,
            "failed_messages": self.failed_messages,
            "fps": self.messages / elapsed,
            "latency_samples": self.latency_samples,
            "source_to_output_latency_ms": (
                1000 * self.latency_seconds / self.latency_samples
                if self.latency_samples
                else None
            ),
        }
        self.started_at = now
        self.messages = 0
        self.failed_messages = 0
        self.latency_samples = 0
        self.latency_seconds = 0.0
        return result
