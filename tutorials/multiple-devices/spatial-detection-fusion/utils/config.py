BEV_WIDTH = 800
BEV_HEIGHT = 800
BEV_SCALE = 100.0  # pixels per meter
TRAIL_LENGTH = 150  # Number of historical points to show for object trails

HTTP_PORT = 8082
CALIBRATION_DATA_DIR = "calibration_data"

NN_MODEL_SLUG = "luxonis/yolov6-nano:r2-coco-512x288"

NN_INPUT_SIZE = (512, 288)  # Should match the chosen YOLOv6 model's input size

# specific labels to show in the BEV / empty labels to show all
BEV_LABELS = []  # Show all labels by default
# bev_labels = ["bottle"]

DISTANCE_THRESHOLD_M = 0.5  # Distance threshold for grouping detections in meters
