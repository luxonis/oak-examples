import logging
import sys

from app import App
from util.device_support import UnsupportedDeviceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        App().run()
    except UnsupportedDeviceError as error:
        logger.error(str(error))
        sys.exit(1)
