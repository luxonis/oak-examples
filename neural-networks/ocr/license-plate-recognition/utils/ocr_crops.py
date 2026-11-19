import logging
from time import monotonic, sleep

import depthai as dai

LOGGER = logging.getLogger(__name__)


class OcrCrops(dai.node.ThreadedHostNode):
    """Identify OCR inputs and carry their crops through result matching."""

    TIMEOUT_SECONDS = 2.0
    MAX_PENDING_CROPS = 64

    def __init__(self):
        super().__init__()
        self.crops = self.createInput(blocking=True)
        self.results = self.createInput(blocking=True)
        self.inference = self.createOutput()
        self.out = self.createOutput()

    def run(self) -> None:
        pending = {}
        completed = {}
        crop_id = 0
        while self.isRunning():
            try:
                result = self.results.tryGet()
                if result is not None:
                    result_id = result.getSequenceNum()
                    if result_id in pending and result_id not in completed:
                        completed[result_id] = result
                    else:
                        LOGGER.warning(
                            "Ignoring unknown or duplicate OCR crop ID %s", result_id
                        )

                crop = self.crops.tryGet()
                if crop is not None:
                    # Only the OCR input uses this ID; output groups retain the
                    # source sequence and timestamps for frame-level gathering.
                    pending[crop_id] = (crop, crop.getSequenceNum(), monotonic())
                    crop.setSequenceNum(crop_id)
                    self.inference.send(crop)
                    crop_id += 1

                now = monotonic()
                while pending:
                    oldest_id = next(iter(pending))
                    crop, source_sequence, arrived_at = pending[oldest_id]
                    result = completed.get(oldest_id)
                    if (
                        result is None
                        and now - arrived_at < self.TIMEOUT_SECONDS
                        and len(pending) <= self.MAX_PENDING_CROPS
                    ):
                        break
                    del pending[oldest_id]
                    completed.pop(oldest_id, None)
                    if result is None:
                        LOGGER.warning(
                            "Dropping OCR crop ID %s from sequence %s",
                            oldest_id,
                            source_sequence,
                        )
                        continue
                    group = dai.MessageGroup()
                    group["ocr"] = result
                    group["crop"] = crop
                    group.setTimestamp(crop.getTimestamp())
                    group.setTimestampDevice(crop.getTimestampDevice())
                    group.setSequenceNum(source_sequence)
                    self.out.send(group)
            except dai.MessageQueue.QueueException:
                break
            sleep(0.001)
