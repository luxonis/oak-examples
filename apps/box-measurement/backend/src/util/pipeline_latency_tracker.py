import logging
import time

import depthai as dai

from depthai_pipeline.node.latency_meter import LatencyMeter


logger = logging.getLogger(__name__)


class PipelineLatencyTracker:
    """Periodically logs stream latency/FPS and slow pipeline nodes."""

    def __init__(
        self,
        pipeline: dai.Pipeline,
        latency_meters: list[LatencyMeter],
        report_interval_seconds: float = 10.0,
        show_top_n_nodes: int = 10,
    ) -> None:
        self._pipeline = pipeline
        self._latency_meters = latency_meters
        self._interval = report_interval_seconds
        self._top_n = show_top_n_nodes
        self._last_report = time.monotonic()
        self._node_names: dict[int, str] | None = None
        self._enabled = True

    def check(self) -> None:
        if not self._enabled:
            return

        now = time.monotonic()
        if now - self._last_report < self._interval:
            return

        self._last_report = now
        try:
            self._report()
        except BaseException as exc:
            logger.warning("Disabling latency tracker: pipeline state unavailable (%s)", exc)
            self._enabled = False

    def _build_node_name_map(self, node_ids: list[int]) -> dict[int, str]:
        mapping: dict[int, str] = {}
        for node_id in node_ids:
            node = self._pipeline.getNode(node_id)
            mapping[node_id] = node.getName() if node is not None else f"Node({node_id})"
        return mapping

    @staticmethod
    def _format_micros(micros: int) -> str:
        if micros == 0xFFFFFFFFFFFFFFFF:
            return "0"
        return f"{micros / 1000.0:.1f}"

    def _report(self) -> None:
        state = self._pipeline.getPipelineState().nodes().detailed()

        if self._node_names is None:
            self._node_names = self._build_node_name_map(list(state.nodeStates.keys()))

        node_latencies = []
        for node_id, node_state in state.nodeStates.items():
            main_loop_timing = node_state.mainLoopTiming
            inputs_timing = node_state.inputsGetTiming
            outputs_timing = node_state.outputsSendTiming
            if not main_loop_timing.isValid() or main_loop_timing.fps == 0:
                continue

            name = self._node_names.get(node_id, f"Node({node_id})")
            if "XLink" in name:
                continue

            node_latencies.append(
                (name, node_id, main_loop_timing, inputs_timing, outputs_timing)
            )

        node_latencies.sort(
            key=lambda item: item[2].durationStats.maxMicrosRecent,
            reverse=True,
        )

        logger.info("=== Box Measurement Latency Report ===")
        for latency_meter in self._latency_meters:
            stats = latency_meter.get_and_reset_stats()
            if stats is None:
                logger.info("%s: no messages", latency_meter.name)
                continue

            logger.info(
                "%s: median=%.1fms, avg=%.1fms, min=%.1fms, max=%.1fms, "
                "fps=%.1f, count=%d",
                latency_meter.name,
                stats["median"],
                stats["avg"],
                stats["min"],
                stats["max"],
                stats["fps"],
                int(stats["count"]),
            )

        logger.info("=== Top %d Slow Nodes ===", self._top_n)
        for name, node_id, main_loop_timing, inputs_timing, outputs_timing in node_latencies[
            : self._top_n
        ]:
            main_stats = main_loop_timing.durationStats
            input_stats = inputs_timing.durationStats
            output_stats = outputs_timing.durationStats
            logger.info(
                "[%s(%d)]: total avg=%sms min=%sms max=%sms; "
                "inputs avg=%sms min=%sms max=%sms; "
                "outputs avg=%sms min=%sms max=%sms; fps=%.1f",
                name,
                node_id,
                self._format_micros(main_stats.averageMicrosRecent),
                self._format_micros(main_stats.minMicrosRecent),
                self._format_micros(main_stats.maxMicrosRecent),
                self._format_micros(input_stats.averageMicrosRecent),
                self._format_micros(input_stats.minMicrosRecent),
                self._format_micros(input_stats.maxMicrosRecent),
                self._format_micros(output_stats.averageMicrosRecent),
                self._format_micros(output_stats.minMicrosRecent),
                self._format_micros(output_stats.maxMicrosRecent),
                main_loop_timing.fps,
            )
        logger.info("--- End of Latency Report ---")
