import logging
import sys
from pathlib import Path

from app import App
from config import STORAGE_BASE_PATH
from services.application_logging import initialize_application_logging
from util.device_support import UnsupportedDeviceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    application_logging = initialize_application_logging(Path(STORAGE_BASE_PATH))

    try:
        app = App(application_logging)
        app.run()
    except UnsupportedDeviceError as error:
        logger.error(str(error))
        sys.exit(1)
    finally:
        application_logging.close()
