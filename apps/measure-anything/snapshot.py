import numpy as np

from history import SaveRequest


def measurement_snapshot(
    detected_object, detected, measured, frame, profile, next_track_id
):
    item = next(
        item
        for item in measured.items
        if item.candidate_id == detected_object["candidate_id"]
    )
    cuboid = item.cuboid
    up = np.asarray(measured.plane.normal)
    length = np.asarray(cuboid.length_axis)
    width = np.cross(up, length)
    base = np.asarray(cuboid.base_center_mm)
    dimensions = [cuboid.length_mm, cuboid.width_mm, cuboid.height_mm]
    bottom = [
        base + lx * length * dimensions[0] / 2 + wy * width * dimensions[1] / 2
        for lx, wy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    metadata = {
        "track_id": detected_object["track_id"],
        "sequence": frame.sequence,
        "video_sequence": frame.color.getSequenceNum(),
        "captured_at": frame.captured_at,
        "candidate_id": item.candidate_id,
        "status": item.status.value,
        "dimensions_mm": dimensions,
        "volume_mm3": float(np.prod(dimensions)),
        "algorithm_id": measured.algorithm_id,
        "reference_frame": measured.frame,
        "source_timing": [
            {
                "stream": source.stream,
                "sequence": source.sequence_num,
                "timestamp_s": source.timestamp.total_seconds(),
                "timestamp_device_s": source.timestamp_device.total_seconds(),
            }
            for source in measured.sources
        ],
        "capture_profile": profile,
        "depth_correction": frame.axial_correction,
        "bbox_rgb": detected_object["bbox"],
        "calibration_generation": frame.generation,
        "support_plane": measured.plane.toJson(),
        "cuboid": {
            "base_center_mm": list(cuboid.base_center_mm),
            "length_axis": list(cuboid.length_axis),
            "width_axis": width.tolist(),
            "up_axis": up.tolist(),
            "dimensions_mm": dimensions,
            "corners_mm": [point.tolist() for point in bottom]
            + [(point + up * dimensions[2]).tolist() for point in bottom],
        },
    }
    points = next(
        detection.xyz_mm
        for detection in detected.items
        if detection.candidate_id == item.candidate_id
    )
    return SaveRequest(
        track_id=detected_object["track_id"],
        sequence=frame.sequence,
        request_revision=None,
        points=points,
        metadata=metadata,
        next_track_id=next_track_id,
        color=frame.color,
    )
