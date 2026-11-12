import os

from dotenv import load_dotenv

load_dotenv()

STORAGE_BASE_PATH = os.environ.get("OAKAGENT_STORAGE_SHARED", "/tmp")

APP_IDENTIFIER = os.environ.get("OAKAGENT_APP_IDENTIFIER", "com.luxonis.box-measurement")
APP_VERSION = os.environ.get("OAKAGENT_APP_VERSION", "0.0.2")

BOX_MODEL_SLUG = "luxonis/box-instance-segmentation:512x320"
NEURAL_DEPTH_MODEL = "NEURAL_DEPTH_768X480"

COLOR_RESOLUTION = (1920, 1080)
MONO_RESOLUTION = (640, 480)
FPS = 20
DEFAULT_DETECTION_CONFIDENCE_THRESHOLD = 0.5
