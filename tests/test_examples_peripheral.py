import os
import subprocess
import shutil
import sys
import pytest
import time
from collections import deque
from pathlib import Path
from venv import EnvBuilder
import logging
from typing import Optional, Dict, List

from utils import is_valid, change_and_restore_dir
from constants import KNOWN_FAILING, IGNORED_WARNINGS


logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)


def test_example_runs_in_peripheral(example_dir, test_args):
    """Tests if the example runs in peripheral mode for at least N seconds without errors."""
    # Time that device is waiting before timing out, set for RVC4 tests
    os.environ["DEPTHAI_SEARCH_TIMEOUT"] = "30000"

    if test_args["virtual_display"]:
        setup_virtual_display()

    example_dir = example_dir.resolve()

    success, reason = is_valid(
        example_dir=example_dir,
        known_failing_examples=KNOWN_FAILING,
        desired_mode="peripheral",
        desired_platform=test_args["platform"],
        desired_py=test_args["python_version"],
        desired_dai=test_args["depthai_version"],
    )
    if not success:
        pytest.skip(f"Skipping {example_dir}: {reason}")

    main_script = example_dir / "main.py"
    requirements_path = example_dir / "requirements.txt"
    if not main_script.exists():
        pytest.skip(f"Skipping {example_dir}, no main.py found.")
    if not requirements_path.exists():
        pytest.skip(f"Skipping {example_dir}, no requirements.txt found.")

    venv_dir = example_dir / ".test-venv"
    if os.name == "nt":
        # Windows
        env_exe = venv_dir / "Scripts" / "python.exe"
    else:
        # POSIX (Linux/macOS)
        env_exe = venv_dir / "bin" / "python3"

    setup_virtual_env(
        venv_dir=venv_dir,
        requirements_path=requirements_path,
        depthai_version=test_args["depthai_version"],
        depthai_nodes_version=test_args["depthai_nodes_version"],
    )

    with change_and_restore_dir(target_dir=example_dir):
        time.sleep(10)  # to stabilize device
        success = run_example(
            env_exe=env_exe,
            example_dir=example_dir,
            args=test_args,
        )
        shutil.rmtree(venv_dir, ignore_errors=True)

    assert success, f"Test failed for {example_dir}"


def setup_virtual_display():
    logger.debug("Ensuring virtual display is set up...")
    result = subprocess.run(
        ["pgrep", "-f", "Xvfb :99"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        logger.debug("Starting virtual display...")
        result = subprocess.run(
            ["which", "Xvfb"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            logger.error(
                "Xvfb is not installed on this machine. Please install it and try again."
            )
            sys.exit(1)
        subprocess.Popen(
            ["Xvfb", ":99", "-screen", "0", "1920x1080x24"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


def setup_virtual_env(
    venv_dir: Path,
    requirements_path: Path,
    depthai_version: Optional[str],
    depthai_nodes_version: Optional[str],
):
    """Creates and sets up a virtual environment with the required dependencies."""
    logger.debug(f"Setting up virtual environment for {venv_dir.parent}...")
    EnvBuilder(clear=True, with_pip=True).create(venv_dir)

    if os.name == "nt":
        # Windows
        env_exe = venv_dir / "Scripts" / "python.exe"
    else:
        # POSIX (Linux/macOS)
        env_exe = venv_dir / "bin" / "python3"

    # Read original requirements
    with open(requirements_path, "r") as f:
        requirements_text = f.read()

    # Check if depthai or depthai-nodes are in the original requirements
    install_depthai_nodes = "depthai-nodes" in requirements_text
    install_depthai = "depthai" in requirements_text

    try:
        # Step 1: Install all base requirements (ignoring version constraints)
        subprocess.run(
            [
                env_exe,
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements_path),
                "--timeout=300",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Step 2: Conditionally override with specific depthai-nodes version
        if install_depthai_nodes and depthai_nodes_version:
            logger.debug(
                f"Trying to install specific depthai-nodes version: {depthai_nodes_version}"
            )
            subprocess.run(
                [
                    env_exe,
                    "-m",
                    "pip",
                    "install",
                    f"depthai-nodes=={depthai_nodes_version}",
                    "--timeout=300",
                ],
                check=True,
            )

        # Step 3: Conditionally override with specific depthai version
        if install_depthai and depthai_version:
            logger.debug(
                f"Trying to install specific depthai version: {depthai_version}"
            )
            subprocess.run(
                [
                    env_exe,
                    "-m",
                    "pip",
                    "install",
                    "-U",
                    "--prefer-binary",
                    "--extra-index-url",
                    "https://artifacts.luxonis.com/artifactory/luxonis-python-release-local",
                    "--extra-index-url",
                    "https://artifacts.luxonis.com/artifactory/luxonis-python-snapshot-local",
                    f"depthai=={depthai_version}",
                    "--timeout=300",
                ],
                check=True,
            )

        logger.debug(f"Installed packages:\n{get_installed_packages(env_exe)}")

    except subprocess.CalledProcessError as e:
        shutil.rmtree(venv_dir)
        pytest.fail(f"Failed to install dependencies for {venv_dir.parent}: {e.stderr}")


def run_example(env_exe: Path, example_dir: Path, args: Dict, max_retries: int = 3):
    """Runs the main.py script for the given timeout duration."""
    timeout = args["timeout"]
    env_vars = args["environment_variables"]
    virtual_env = args["virtual_display"]
    device = args["device"]
    logger.debug(f"Running {example_dir} with timeout {timeout}s...")

    main_script = "main.py"

    env = os.environ.copy()
    if env_vars:
        env_dict = dict(item.split("=") for item in env_vars.split())
        env.update(env_dict)

    if virtual_env:
        env["DISPLAY"] = ":99"

    if device:
        env["DEPTHAI_DEVICE_NAME_LIST"] = device

    for attempt in range(1, max_retries + 1):
        try:
            # Start subprocess using Popen
            process = subprocess.Popen(
                [env_exe, str(main_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )

            # Use timer to wait for timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                logger.info(f"{example_dir} ran for {timeout} seconds before timeout.")

                if args["strict_mode"]:
                    all_output = stdout.splitlines() + stderr.splitlines()
                    dai_warnings = filter_warnings(all_output, IGNORED_WARNINGS)
                    if len(dai_warnings) > 0:
                        logger.error(f"Unexpected DepthAI warnings: {dai_warnings}")
                        return False

                return True  # Success case — ran full duration

            # If it finishes early (not ideal), check exit code and logs
            if process.returncode == 0:
                last_stdout_lines = deque(stdout.splitlines(), maxlen=10)
                last_stderr_lines = deque(stderr.splitlines(), maxlen=10)

                logger.error(
                    f"{example_dir} ran for less than {timeout} seconds before terminating (exit code 0)."
                )

                if last_stdout_lines:
                    logger.error("Last stdout lines:")
                    for line in last_stdout_lines:
                        logger.error(f"  {line}")

                if last_stderr_lines:
                    logger.error("Last stderr lines:")
                    for line in last_stderr_lines:
                        logger.error(f"  {line}")

                logger.error(
                    f"{example_dir} ran for less than {timeout} seconds before terminating (exit code 0)."
                )
                return False

            if (
                "No internet connection available." in stderr
                or "There was an error while sending a request to the Hub" in stderr
            ):
                logger.warning(f"Retryable error in {example_dir}: {stderr.strip()}")
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                else:
                    logger.error("Max retries reached.")
                    return False

            # Handle other early errors
            logger.error(f"Error in {example_dir}:\n{stderr}")
            return False

        except Exception as e:
            logger.error(f"Unexpected exception in {example_dir}: {e}")
            return False

    return False


def filter_warnings(output: List[str], ignored_warnings: List[str]):
    """Filter out warnings that are from DAI and shouldn't be ignored"""
    dai_warnings = [
        line for line in output if "[warning]" in line or "DeprecationWarning" in line
    ]
    unexpected = []
    for line in dai_warnings:
        if not any(ignored in line for ignored in ignored_warnings):
            unexpected.append(line)

    return unexpected


def get_installed_packages(env_exe: Path):
    """Returns the list of installed packages in the virtual environment."""
    return subprocess.check_output([env_exe, "-m", "pip", "freeze"], text=True)


if __name__ == "__main__":
    pytest.main([__file__])
