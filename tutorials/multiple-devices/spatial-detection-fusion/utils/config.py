BEV_WIDTH = 800
BEV_HEIGHT = 800
BEV_SCALE = 100.0  # pixels per meter
# The reference camera sits at this fraction of the canvas height and looks towards the top.
BEV_ORIGIN_Y = 0.85
TRAIL_LENGTH = 150  # Number of historical points to show for object trails

HTTP_PORT = 8082

NN_MODEL_SLUG = "luxonis/yolov6-nano:r2-coco-512x288"

# specific labels to show in the BEV / empty labels to show all
BEV_LABELS = []  # Show all labels by default
# BEV_LABELS = ["bottle"]

DISTANCE_THRESHOLD_M = 0.5  # Distance threshold for grouping detections in meters
