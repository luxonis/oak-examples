"""A stop signal ends the app through its normal pipeline cleanup."""

import os
import signal
import unittest
from unittest.mock import MagicMock, patch

import main

TOPICS = ("color", "danger")
STOP_MESSAGE = "Application received a stop signal. Stopping the app..."


class UnhandledSignal(Exception):
    pass


def _raise_unhandled(signum, frame):
    raise UnhandledSignal(signal.Signals(signum).name)


class AppStopTest(unittest.TestCase):
    def setUp(self) -> None:
        # Fail the test instead of killing the runner if the app leaves a signal unhandled.
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous = signal.signal(signum, _raise_unhandled)
            self.addCleanup(signal.signal, signum, previous)

        self.visualizer = MagicMock()
        self.visualizer.waitKey.return_value = -1
        self.pipelines: list[MagicMock] = []
        self.on_process_tasks = lambda: None

        for p in (
            patch.object(main.dai, "RemoteConnection", return_value=self.visualizer),
            patch.object(main.dai, "Pipeline", side_effect=self._new_pipeline),
            patch.object(main, "init_pipeline", return_value=TOPICS),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _new_pipeline(self) -> MagicMock:
        pipeline = MagicMock()
        running = [False]
        pipeline.start.side_effect = lambda: running.__setitem__(0, True)
        pipeline.stop.side_effect = lambda: running.__setitem__(0, False)
        pipeline.isRunning.side_effect = lambda: running[0]
        pipeline.processTasks.side_effect = lambda: self.on_process_tasks()
        self.pipelines.append(pipeline)
        return pipeline

    def _service(self, name: str):
        for call in self.visualizer.registerService.call_args_list:
            if call.args[0] == name:
                return call.args[1]
        raise KeyError(name)

    def test_stop_signal_stops_pipeline_and_removes_topics(self) -> None:
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=signum.name):
                self.visualizer.reset_mock()
                self.pipelines.clear()
                app = main.App()
                self.on_process_tasks = lambda: os.kill(os.getpid(), signum)

                with self.assertLogs(main.log, level="INFO") as logs:
                    app.run()

                self.assertIn(STOP_MESSAGE, [r.getMessage() for r in logs.records])
                self.assertEqual(len(self.pipelines), 1)
                self.pipelines[0].stop.assert_called_once()
                removed = [
                    c.args[0] for c in self.visualizer.removeTopic.call_args_list
                ]
                self.assertEqual(removed, list(TOPICS))

    def test_stop_wins_over_pending_settings_change(self) -> None:
        app = main.App()
        update_settings = self._service("updateSettings")
        settings = self._service("getSettings")({})

        def change_settings_then_stop() -> None:
            self.on_process_tasks = lambda: None
            update_settings(settings)
            os.kill(os.getpid(), signal.SIGTERM)

        self.on_process_tasks = change_settings_then_stop

        app.run()

        self.assertEqual(len(self.pipelines), 1)
        self.pipelines[0].stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
