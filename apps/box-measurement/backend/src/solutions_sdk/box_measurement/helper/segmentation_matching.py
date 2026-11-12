import depthai as dai


class SegmentationMatcher:
    def match(
        self,
        tracklets: list[dai.Tracklet],
        detections: list[dai.ImgDetection],
    ) -> dict[int, int]:
        """Greedy IoU match: returns {tracklet_index: detection_index}."""
        candidates: list[tuple[float, int, int]] = []
        for track_index, tracklet in enumerate(tracklets):
            t_bbox = self._tracklet_bbox(tracklet)
            for det_index, det in enumerate(detections):
                iou = self._iou(t_bbox, (det.xmin, det.ymin, det.xmax, det.ymax))
                if iou > 0.0:
                    candidates.append((iou, track_index, det_index))

        candidates.sort(reverse=True)

        used_tracks: set[int] = set()
        used_dets: set[int] = set()
        matches: dict[int, int] = {}
        for _iou, track_index, det_index in candidates:
            if track_index in used_tracks or det_index in used_dets:
                continue
            used_tracks.add(track_index)
            used_dets.add(det_index)
            matches[track_index] = det_index
        return matches

    @staticmethod
    def _tracklet_bbox(tracklet: dai.Tracklet) -> tuple[float, float, float, float]:
        roi = tracklet.roi
        tl = roi.topLeft()
        br = roi.bottomRight()
        return tl.x, tl.y, br.x, br.y

    @staticmethod
    def _iou(
        a: tuple[float, float, float, float],
        b: tuple[float, float, float, float],
    ) -> float:
        ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
        ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        if inter <= 0.0:
            return 0.0
        area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
        area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0.0 else 0.0
