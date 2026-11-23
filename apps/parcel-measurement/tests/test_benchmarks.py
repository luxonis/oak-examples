from importlib import import_module
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
BenchmarkWindow = import_module("benchmarks").BenchmarkWindow


class BenchmarkTests(unittest.TestCase):
    def test_reports_throughput_and_weighted_latency_after_ten_seconds(self):
        window = BenchmarkWindow(started_at=5)
        for index in range(5):
            window.record_message(failed=index == 4)
        window.add_report(1, 0.2)
        window.add_report(3, 0.6)
        self.assertIsNone(window.report(14.9))
        result = window.report(15)
        self.assertEqual(result["messages"], 5)
        self.assertEqual(result["failed_messages"], 1)
        self.assertEqual(result["fps"], 0.5)
        self.assertEqual(result["latency_samples"], 4)
        self.assertAlmostEqual(result["source_to_output_latency_ms"], 500)
        self.assertEqual(result["window_seconds"], 10)

    def test_late_poll_uses_actual_elapsed_time_and_resets_the_window(self):
        window = BenchmarkWindow(started_at=0)
        for _ in range(5):
            window.record_message()
        window.add_report(2, 0.2)
        self.assertEqual(window.report(12.5)["fps"], 0.4)
        window.record_message()
        window.record_message()
        window.add_report(1, 0.1)
        self.assertIsNone(window.report(20))
        result = window.report(22.5)
        self.assertEqual(result["messages"], 2)
        self.assertEqual(result["failed_messages"], 0)
        self.assertEqual(result["fps"], 0.2)
        self.assertEqual(result["latency_samples"], 1)
        self.assertEqual(result["source_to_output_latency_ms"], 100)

    def test_idle_windows_report_zero_throughput_without_a_latency(self):
        window = BenchmarkWindow(started_at=0)
        for now in (10, 20):
            result = window.report(now)
            self.assertEqual(result["messages"], 0)
            self.assertEqual(result["failed_messages"], 0)
            self.assertEqual(result["fps"], 0)
            self.assertEqual(result["latency_samples"], 0)
            self.assertIsNone(result["source_to_output_latency_ms"])

    def test_first_output_counts_before_a_native_latency_report_arrives(self):
        window = BenchmarkWindow(started_at=0)
        window.record_message()
        result = window.report(10)
        self.assertEqual(result["messages"], 1)
        self.assertEqual(result["fps"], 0.1)
        self.assertEqual(result["latency_samples"], 0)
        self.assertIsNone(result["source_to_output_latency_ms"])


if __name__ == "__main__":
    unittest.main()
