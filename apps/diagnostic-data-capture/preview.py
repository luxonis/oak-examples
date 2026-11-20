"""Create a representative image from the first saved frame set."""

from pathlib import Path

import cv2
import depthai as dai
import numpy as np


def write_capture_preview(folder, metadata):
    folder = Path(folder)
    streams = metadata["frames"][0]["streams"]
    tiles = []
    labels = {
        "rgb": "RGB",
        "left": "Left",
        "right": "Right",
        "tof_depth": "ToF depth (0-10 m)",
        "tof_confidence": "ToF confidence",
    }
    for name in sorted(
        streams,
        key=lambda x: (
            ["rgb", "left", "right", "tof_depth", "tof_confidence"].index(x)
            if x in labels
            else 99,
            x,
        ),
    ):
        frame = dai.ImgFrame()
        frame.load(str(folder / streams[name]["file"]))
        if name.endswith("_depth"):
            depth = frame.getFrame()
            pixels = cv2.applyColorMap(
                np.uint8(np.clip(depth.astype(float) / 10000, 0, 1) * 255),
                cv2.COLORMAP_TURBO,
            )
            pixels[depth == 0] = 0
        else:
            pixels = frame.getCvFrame()
            if pixels.ndim == 2:
                pixels = cv2.cvtColor(pixels, cv2.COLOR_GRAY2BGR)
        h, w = pixels.shape[:2]
        scale = min(320 / w, 224 / h)
        pixels = cv2.resize(
            pixels,
            (max(1, round(w * scale)), max(1, round(h * scale))),
            interpolation=cv2.INTER_AREA,
        )
        tile = np.full((260, 336, 3), (27, 20, 15), dtype=np.uint8)
        y, x = 32 + (224 - pixels.shape[0]) // 2, (336 - pixels.shape[1]) // 2
        tile[y : y + pixels.shape[0], x : x + pixels.shape[1]] = pixels
        cv2.putText(
            tile,
            labels.get(name, name),
            (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )
        tiles.append(tile)
    columns = min(3, len(tiles))
    while len(tiles) % columns:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack(
        [np.hstack(tiles[i : i + columns]) for i in range(0, len(tiles), columns)]
    )
    if not cv2.imwrite(
        str(folder / "preview.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90]
    ):
        raise OSError("Could not write capture preview.jpg")
    return "preview.jpg"
