import logging
import time
import threading
from collections import deque
from dataclasses import dataclass

import depthai as dai
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineHealthConfig:
    max_fps: int = 30
    min_fps: int = 5
    poll_interval_sec: float = 0.5
    settle_after_tile_change_sec: float = 2.0
    skip_node_names: tuple = (
        "Script",
        "ImageManip",
        "XLinkOut",
        "XLinkOutHost",
        "XLinkIn",
        "XLinkInHost",
        "Sync",
        "Camera",
        "VideoEncoder",
    )
    per_tile_node_names: tuple = ("NeuralNetwork", "DetectionParser")
    blocked_window_size: int = 4
    blocked_threshold_drop: int = 2
    blocked_threshold_severe_drop: int = 3
    drop_step: int = 1
    severe_drop_step: int = 3
    rise_step: int = 1
    healthy_polls_before_rise: int = 5
    ceiling_stable_trial_polls: int = 10
    post_drop_hold_polls: int = 5
    ceiling_discovery_delay_polls: int = 15
    fps_safety_margin: float = 0.75


@dataclass
class FpsCeilingState:
    """Adaptive FPS ceiling: estimated on tile-increase, refined by feedback.

    Ceiling lifecycle (event-driven):
        - Tile increase: estimate ceiling (unlocked); drop immediately if above it.
        - First drop with no ceiling: discover ceiling (unlocked).
        - Sustained stability at ceiling: raise ceiling by +1 (trial).
        - Drop at/above ceiling: lower ceiling and lock until next tile change.
        - Tile decrease: clear ceiling, allow fps to rise naturally.
    """

    value: int | None = None
    locked: bool = False
    consecutive_stable_polls: int = 0

    def set(self, fps: int) -> None:
        self.value = fps
        self.locked = False
        self.reset_stable()

    def clear(self) -> None:
        self.value = None
        self.locked = False
        self.reset_stable()

    def lock(self) -> None:
        self.locked = True
        self.reset_stable()

    def lower_to(self, fps: int) -> None:
        """Lower ceiling value, preserving locked state."""
        if self.value is not None:
            fps = min(self.value, fps)
        self.value = fps
        self.reset_stable()

    def raise_to(self, fps: int) -> None:
        self.value = fps
        self.reset_stable()

    def reset_stable(self) -> None:
        self.consecutive_stable_polls = 0

    def record_stable_poll(self, threshold: int) -> bool:
        """Record one stable poll; return True if stable threshold reached."""
        self.consecutive_stable_polls += 1
        return self.consecutive_stable_polls >= threshold

    def max_allowed_fps(self, hard_max_fps: int) -> int:
        return min(hard_max_fps, self.value) if self.value is not None else hard_max_fps

    @property
    def active(self) -> bool:
        return self.value is not None


class PipelineHealthMonitor(dai.node.ThreadedHostNode):
    """
    Monitors pipeline health and outputs a target FPS control signal.

    Uses BLOCKED input states as overload feedback and adjusts target FPS.
    """

    def __init__(self) -> None:
        super().__init__()
        self._target_fps_out = self.createOutput()
        self._config = PipelineHealthConfig()
        self._pipeline: dai.Pipeline | None = None
        self._output_fps: int = self._config.max_fps
        self._healthy_count: int = 0
        self._ceiling = FpsCeilingState()
        self._settle_until: float = 0.0
        self._blocked_inputs_history: deque[bool] = deque(
            maxlen=self._config.blocked_window_size
        )
        self._post_drop_cooldown_left: int = 0
        self._ceiling_discovery_polls_left: int = 0
        self._old_tile_count: int = 0
        self._lock = threading.Lock()

    def build(
        self,
        pipeline: dai.Pipeline,
        initial_tile_count: int,
        config: PipelineHealthConfig | None = None,
    ) -> "PipelineHealthMonitor":
        self._pipeline = pipeline
        self._old_tile_count = initial_tile_count
        if config is not None:
            self._config = config
        self._blocked_inputs_history = deque(maxlen=self._config.blocked_window_size)
        self._output_fps = self._config.max_fps
        return self

    def run(self) -> None:
        self._send_fps(self._output_fps)
        logger.info("PipelineHealthMonitor: started, initial_fps=%d", self._output_fps)

        while self.isRunning():
            time.sleep(self._config.poll_interval_sec)
            with self._lock:
                now = time.monotonic()
                if now < self._settle_until:
                    continue
                try:
                    self._poll_and_adjust()
                except Exception:
                    logger.exception("Error polling pipeline state.")

    def adjust_fps_from_tile_count(self, tile_count: int) -> None:
        """Called by TilingConfigService when tile count changes."""
        with self._lock:
            now = time.monotonic()

            if tile_count == self._old_tile_count:
                return

            if tile_count > self._old_tile_count:
                self._handle_tile_increase(tile_count)
            else:
                self._handle_tile_decrease(tile_count)

            self._old_tile_count = tile_count
            self._post_drop_cooldown_left = 0
            self._blocked_inputs_history.clear()
            self._settle_until = now + self._config.settle_after_tile_change_sec

    def _handle_tile_increase(self, tile_count: int) -> None:
        try:
            est_fps = self._estimate_max_fps(tile_count)
        except Exception:
            logger.exception(
                "TILES_INCREASE %d->%d, estimation failed",
                self._old_tile_count,
                tile_count,
            )
            return

        self._ceiling.set(est_fps)
        self._ceiling_discovery_polls_left = 0

        logger.info(
            "TILES_INCREASE %d->%d, est_fps=%d, setting as ceiling",
            self._old_tile_count,
            tile_count,
            est_fps,
        )

        # Never speed up on tile increase
        if est_fps < self._output_fps:
            self._set_fps(est_fps)

    def _handle_tile_decrease(self, tile_count: int) -> None:
        logger.info(
            "TILES_DECREASE %d->%d, keeping fps=%d, ceiling removed",
            self._old_tile_count,
            tile_count,
            self._output_fps,
        )
        self._ceiling.clear()
        self._healthy_count = 0
        self._ceiling_discovery_polls_left = self._config.ceiling_discovery_delay_polls

    def _poll_and_adjust(self) -> None:
        state = self._pipeline.getPipelineState().nodes().detailed()
        blocked_nodes = []
        queue_details = []

        for node_id, node_state in state.nodeStates.items():
            node = self._pipeline.getNode(node_id)
            node_name = node.getName() if node else "unknown"
            if node_name in self._config.skip_node_names:
                continue

            label_prefix = f"{node_name}[{node_id}]"
            for input_name, input_queue in node_state.inputStates.items():
                label = f"{label_prefix}/{input_name}"
                if input_queue.state == input_queue.State.BLOCKED:
                    queue_details.append(
                        f"{label}(queued={input_queue.numQueued}, state={input_queue.state.name})"
                    )
                    blocked_nodes.append(label)

        has_blocked = len(blocked_nodes) > 0
        self._blocked_inputs_history.append(has_blocked)
        blocked_count = sum(self._blocked_inputs_history)
        at_floor = self._output_fps <= self._config.min_fps

        if has_blocked:
            self._healthy_count = 0
            self._ceiling.reset_stable()
            if self._ceiling_discovery_polls_left > 0:
                self._ceiling_discovery_polls_left = (
                    self._config.ceiling_discovery_delay_polls
                )

            blocked_window = "".join(
                "B" if b else "." for b in self._blocked_inputs_history
            )

            if (
                not at_floor
                and blocked_count >= self._config.blocked_threshold_severe_drop
            ):
                logger.info(
                    "SEVERE_DROP: [%s] at [%s] | %s",
                    blocked_window,
                    ", ".join(blocked_nodes),
                    " | ".join(queue_details),
                )
                self._drop_fps(self._config.severe_drop_step)
            elif not at_floor and blocked_count >= self._config.blocked_threshold_drop:
                logger.info(
                    "DROP: [%s] at [%s] | %s",
                    blocked_window,
                    ", ".join(blocked_nodes),
                    " | ".join(queue_details),
                )
                self._drop_fps(self._config.drop_step)
        else:
            if self._post_drop_cooldown_left > 0:
                self._post_drop_cooldown_left -= 1
                return

            if self._ceiling_discovery_polls_left > 0:
                self._ceiling_discovery_polls_left -= 1

            self._healthy_count += 1
            self._try_rise()

    def _drop_fps(self, step: int) -> None:
        new_fps = max(self._config.min_fps, self._output_fps - step)
        self._post_drop_cooldown_left = self._config.post_drop_hold_polls

        if not self._ceiling.active:
            if self._ceiling_discovery_polls_left > 0:
                logger.info(
                    "fps %d->%d ceiling_discovery_delayed",
                    self._output_fps,
                    new_fps,
                )
            else:
                self._ceiling.set(new_fps)
                logger.info(
                    "fps %d->%d ceiling_discovered=%d",
                    self._output_fps,
                    new_fps,
                    self._ceiling.value,
                )
        elif self._output_fps >= self._ceiling.value:
            self._ceiling.lower_to(new_fps)
            self._ceiling.lock()
            logger.info(
                "fps %d->%d ceiling_locked=%d",
                self._output_fps,
                new_fps,
                self._ceiling.value,
            )
        else:
            logger.info(
                "fps %d->%d ceiling_unchanged=%d",
                self._output_fps,
                new_fps,
                self._ceiling.value,
            )

        self._set_fps(new_fps)

    def _try_rise(self) -> None:
        if self._ceiling.active:
            self._try_ceiling_rise()
        else:
            self._try_normal_rise()

    def _try_ceiling_rise(self) -> None:
        """Rise logic when a ceiling is active."""
        effective_max = self._ceiling.max_allowed_fps(self._config.max_fps)

        if self._output_fps >= effective_max:
            if self._ceiling.locked:
                return
            # At ceiling: count stability, then raise ceiling by +1
            if self._ceiling.record_stable_poll(
                self._config.ceiling_stable_trial_polls
            ):
                new_fps = min(self._config.max_fps, self._output_fps + 1)
                if new_fps > self._output_fps:
                    self._ceiling.raise_to(new_fps)
                    logger.info(
                        "CEILING_RAISED %d->%d",
                        self._output_fps,
                        new_fps,
                    )
                    self._set_fps(new_fps)
        else:
            # Below ceiling: normal rise toward it
            self._try_normal_rise()

    def _try_normal_rise(self) -> None:
        """Rise toward ceiling (or max_fps if no ceiling): +1 after N healthy polls"""
        effective_ceiling = self._ceiling.max_allowed_fps(self._config.max_fps)

        if self._healthy_count >= self._config.healthy_polls_before_rise:
            new_fps = min(effective_ceiling, self._output_fps + self._config.rise_step)
            if new_fps > self._output_fps:
                self._healthy_count = 0
                logger.info(
                    "RISE fps %d->%d ceiling=%s",
                    self._output_fps,
                    new_fps,
                    effective_ceiling,
                )
                self._set_fps(new_fps)

    def _estimate_max_fps(self, tile_count: int) -> int:
        """Estimate max safe FPS from per-tile device node timings.

        frame_us = max(per_tile_us) * tile_count
        max_fps = 1_000_000 / frame_us * fps_safety_margin
        """
        pipeline_state = self._pipeline.getPipelineState().nodes().detailed()
        max_frame_us = 0.0
        bottleneck_label = ""
        node_details = []

        for node_id, node_state in pipeline_state.nodeStates.items():
            node = self._pipeline.getNode(node_id)
            if not node:
                continue
            node_name = node.getName()
            if node_name not in self._config.per_tile_node_names:
                continue

            node_us = node_state.mainLoopTiming.durationStats.medianMicrosRecent
            if node_us <= 0:
                continue

            frame_us = node_us * tile_count
            label = f"{node_name}[{node_id}]"
            node_details.append(
                f"{label}: {node_us:.0f}us x{tile_count}={frame_us:.0f}us/frame"
            )

            if frame_us > max_frame_us:
                max_frame_us = frame_us
                bottleneck_label = label

        if max_frame_us <= 0:
            raise RuntimeError("No valid timing data from any monitored node")

        max_fps = 1_000_000 / max_frame_us
        est_fps = max(
            self._config.min_fps, int(max_fps * self._config.fps_safety_margin)
        )

        logger.info(
            "ESTIMATE tiles=%d bottleneck_node=%s target_fps=%d | %s",
            tile_count,
            bottleneck_label,
            est_fps,
            " | ".join(node_details),
        )
        return est_fps

    def _set_fps(self, fps: int) -> None:
        fps = max(self._config.min_fps, min(self._config.max_fps, int(fps)))
        if fps == self._output_fps:
            return
        self._output_fps = fps
        self._blocked_inputs_history.clear()
        self._ceiling.reset_stable()
        self._healthy_count = 0
        self._send_fps(fps)

    def _send_fps(self, fps: int) -> None:
        buff = dai.Buffer()
        buff.setData(np.array([np.uint8(fps)]))
        self._target_fps_out.send(buff)

    @property
    def out(self) -> dai.Node.Output:
        return self._target_fps_out

    @property
    def current_fps(self) -> int:
        with self._lock:
            return self._output_fps
