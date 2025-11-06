import os
from dotenv import load_dotenv
from config.arguments import initialize_argparser


class CLIEnvLoader:
    """Handles .env loading and CLI argument parsing."""

    def __init__(self):
        self.args = None

    def load(self):
        """Load environment and parse CLI args."""
        load_dotenv(override=True)
        _, self.args = initialize_argparser()

        if self.args.api_key:
            os.environ["DEPTHAI_HUB_API_KEY"] = self.args.api_key

        return self.args
