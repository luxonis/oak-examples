import logging
import sys
from pathlib import Path

from app import App
from arguments import initialize_argparser
from depthai_nodes.runtime import serve_frontend
from util.device_support import UnsupportedDeviceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    _, args = initialize_argparser()
    with serve_frontend(
        args.frontend_dir or Path(__file__).resolve().parents[2] / "frontend" / "dist",
        host=args.frontend_host,
        port=args.frontend_port,
        enabled=not args.no_frontend,
    ):
        try:
            App(device=args.device).run()
        except UnsupportedDeviceError as error:
            logger.error(str(error))
            sys.exit(1)
