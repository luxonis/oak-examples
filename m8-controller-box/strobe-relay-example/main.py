"""
Main Application
----------------
• Video stream from DepthAI (HTTP MJPEG)
• Barcode detection pipeline with optional temporal smoothing
• Conveyor + FSYNC control
"""

import time
import cv2
import threading
import numpy as np
import depthai as dai
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from utils.barcode_processor import BarcodeProcessor
from utils.box_config import BoxConfig

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------
HTTP_SERVER_PORT = 8083        # MJPEG server port
TEMPORAL_SMOOTHING = True      # Enable/disable bounding box smoothing
SMOOTHING_ALPHA = 0.5          # 0.0 = max smoothing, 1.0 = no smoothing
FONT = cv2.FONT_HERSHEY_SIMPLEX
COLOR_VALID = (0, 255, 0)
COLOR_INVALID = (0, 0, 255)


# ------------------------------------------------------------
# MJPEG streaming server
# ------------------------------------------------------------
class VideoStreamHandler(BaseHTTPRequestHandler):
    """HTTP server to stream frames as MJPEG"""
    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-type", "multipart/x-mixed-replace; boundary=--jpgboundary"
        )
        self.end_headers()
        while True:
            time.sleep(0.03)
            if hasattr(self.server, "frametosend"):
                ok, encoded = cv2.imencode(".jpg", self.server.frametosend)
                self.wfile.write(b"--jpgboundary\r\n")
                self.send_header("Content-type", "image/jpeg")
                self.send_header("Content-length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded.tobytes())
                self.wfile.write(b"\r\n")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle MJPEG requests in a separate thread."""
    pass


# ------------------------------------------------------------
# Host node: Barcode detection + conveyor control + frame output
# ------------------------------------------------------------
class BarcodeHostNode(dai.node.ThreadedHostNode):
    def __init__(self, box: BoxConfig, server: ThreadedHTTPServer):
        super().__init__()
        self.input = self.createInput()
        self.input.setBlocking(False)
        self.output = self.createOutput()
        self.processor = BarcodeProcessor()
        self.box = box
        self.server = server

        # State machine for conveyor
        self.STATE_RUNNING = 0
        self.STATE_STOPPED = 1
        self.STATE_COOLDOWN = 2
        self.state = self.STATE_RUNNING
        self.state_timestamp = time.time()
        self.STOP_DURATION = 1.5
        self.COOLDOWN_TIME = 2.0

        # Temporal smoothing storage
        self.last_rects = {}  # barcode_data -> (x, y, w, h)

    def run(self):
        while self.isRunning():
            in_msg = self.input.tryGet()
            if in_msg is None:
                time.sleep(0.001)
                continue

            frame = in_msg.getCvFrame()

            # Detect barcodes
            barcodes = self.processor.decode_barcodes(frame)
            valid = self.processor.filter_valid_barcodes(barcodes)

            # Print all valid barcodes to console
            for data, _ in valid:
                print(f"[INFO] Barcode detected: {data}")

            # Draw all detected barcodes with optional temporal smoothing
            for bc in barcodes:
                data = bc.data.decode("utf-8")
                x, y, w, h = bc.rect

                if TEMPORAL_SMOOTHING:
                    if data in self.last_rects:
                        lx, ly, lw, lh = self.last_rects[data]
                        # Weighted average for smooth motion
                        x = int(lx * (1 - SMOOTHING_ALPHA) + x * SMOOTHING_ALPHA)
                        y = int(ly * (1 - SMOOTHING_ALPHA) + y * SMOOTHING_ALPHA)
                        w = int(lw * (1 - SMOOTHING_ALPHA) + w * SMOOTHING_ALPHA)
                        h = int(lh * (1 - SMOOTHING_ALPHA) + h * SMOOTHING_ALPHA)
                    self.last_rects[data] = (x, y, w, h)

                # Color green for valid, red for detected but not valid
                color = COLOR_VALID if any(v[0] == data for v in valid) else COLOR_INVALID
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, data, (x, y - 10), FONT, 0.5, color, 2)

            # Conveyor state machine
            now = time.time()
            if self.state == self.STATE_RUNNING and valid:
                self.box.stop_conveyor()
                self.state = self.STATE_STOPPED
                self.state_timestamp = now

            elif self.state == self.STATE_STOPPED:
                if now - self.state_timestamp >= self.STOP_DURATION:
                    print("[INFO] Restarting conveyor")
                    self.box.start_conveyor()
                    self.state = self.STATE_COOLDOWN
                    self.state_timestamp = now

            elif self.state == self.STATE_COOLDOWN:
                if now - self.state_timestamp >= self.COOLDOWN_TIME:
                    self.state = self.STATE_RUNNING

            # Update MJPEG server frame
            self.server.frametosend = frame

            # Optionally send frame forward
            out = dai.ImgFrame()
            out.setData(frame)
            out.setWidth(frame.shape[1])
            out.setHeight(frame.shape[0])
            self.output.send(out)


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    # Initialize DepthAI device
    device = dai.Device()
    box = BoxConfig()
    box.init_fsync()
    platform = device.getPlatform().name
    print(f"[INFO] Platform: {platform}")

    # Choose frame type based on platform
    frame_type = dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p

    # Start MJPEG server
    server = ThreadedHTTPServer(("0.0.0.0", HTTP_SERVER_PORT), VideoStreamHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[INFO] MJPEG stream available at http://<device_ip>:{HTTP_SERVER_PORT}")

    with dai.Pipeline(device) as pipeline:
        # Camera node
        cam = pipeline.create(dai.node.Camera).build()
        cam.initialControl.setManualExposure(3000, 200)
        device.setExternalFrameSyncRole(dai.ExternalFrameSyncRole.MASTER)

        # Request full sensor resolution for best FOV
        cam_out = cam.requestOutput((1920, 1080), frame_type, fps=30)

        # Host node for barcode processing + conveyor
        barcode_node = pipeline.create(BarcodeHostNode, box, server)
        cam_out.link(barcode_node.input)

        # Run the pipeline
        pipeline.run()
        print("[INFO] Pipeline running...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[INFO] Exiting...")