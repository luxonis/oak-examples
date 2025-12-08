import os
import subprocess
import shutil
import pytest
import time
import sys
from pathlib import Path
from collections import deque
import logging
import threading
import queue
import re
import json
from typing import Optional, Dict

from utils import (
    adjust_requirements,
    is_valid,
    change_and_restore_dir,
    local_base_image,
)
from constants import KNOWN_FAILING

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)


APP_ID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture(autouse=True, scope="module")
def skip_if_not_rvc4(test_args):
    if test_args["platform"] != "rvc4":
        pytest.skip("Skipping test_standalone.py: requires RVC4 platform")


def test_example_runs_in_standalone(example_dir, test_args):
    """Tests if the example runs in standalone mode for at least N seconds without errors."""
    # Time that device is waiting before timing out, set for RVC4 tests
    os.environ["DEPTHAI_SEARCH_TIMEOUT"] = "30000"

    example_dir = example_dir.resolve()

    success, reason = is_valid(
        example_dir=example_dir,
        known_failing_examples=KNOWN_FAILING,
        desired_mode="standalone",
        desired_platform=test_args["platform"],
        desired_py=test_args["python_version"],
        desired_dai=test_args["depthai_version"],
    )
    if not success:
        pytest.skip(f"Skipping {example_dir}: {reason}")

    main_script = example_dir / "main.py"
    requirements_path = example_dir / "requirements.txt"
    oakapp_toml = example_dir / "oakapp.toml"
    if not main_script.exists():
        pytest.skip(f"Skipping {example_dir}, no main.py found.")
    if not requirements_path.exists():
        pytest.skip(f"Skipping {example_dir}, no requirements.txt found.")
    if not oakapp_toml.exists():
        pytest.skip(f"Skipping {example_dir}, no oakapp.toml found.")

    setup_env(
        base_dir=example_dir,
        requirements_path=requirements_path,
        depthai_version=test_args["depthai_version"],
        depthai_nodes_version=test_args["depthai_nodes_version"],
        oakapp_toml_path=oakapp_toml,
        local_static_registry=test_args["local_static_registry"],
    )

    with change_and_restore_dir(example_dir):
        time.sleep(10)  # to stabilize device
        success = run_example(example_dir=example_dir, args=test_args)
        teardown()

    assert success, f"Test failed for {example_dir}"


def setup_env(
    base_dir: Path,
    requirements_path: Path,
    depthai_version: Optional[str],
    depthai_nodes_version: Optional[str],
    oakapp_toml_path=str,
    local_static_registry=str,
):
    """Sets up the envrionment with the new requirements"""
    new_requirements = adjust_requirements(
        current_req_path=requirements_path,
        depthai_version=depthai_version,
        depthai_nodes_version=depthai_nodes_version,
    )
    logger.info(
        "If depthai and depthai-nodes versions are not compatible then dependency resolver might fail."
    )
    # Create a copy of the old requirements
    shutil.copyfile(requirements_path, base_dir / "requirements_old.txt")
    # Save new requirements
    new_req_path = base_dir / "requirements.txt"
    with open(new_req_path, "w") as f:
        f.writelines(new_requirements)
    local_base_image(oakapp_toml_path, local_static_registry)


def enqueue_output(out, q):
    try:
        for line in iter(out.readline, ""):
            q.put(line)
    except ValueError:
        # This happens if 'out' is closed while reading.
        pass
    finally:
        try:
            out.close()
        except Exception:
            pass  # Ignore if already closed


def run_example(example_dir: Path, args: Dict) -> bool:
    oakctl_path = shutil.which("oakctl")
    assert oakctl_path is not None, "'oakctl' command is not available in PATH"

    if not connect_to_device(
        device=args["device"], device_password=args["device_password"]
    ):
        return False

    run_duration = args.get("timeout")
    startup_timeout = (
        60 * 5
    )  # if it takes more than 5min to setup the app then fail the test
    try:
        logger.debug(f"Installing {example_dir} app")

        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
        }

        # Windows encoding fixes
        if sys.platform.startswith("win"):
            popen_kwargs["encoding"] = "utf-8"
            popen_kwargs["errors"] = "replace"

        process = subprocess.Popen(["oakctl", "app", "run", "."], **popen_kwargs)
        app_started = False
        start_time = None
        signal_start = time.time()
        recent_lines = deque(maxlen=10)
        for line in process.stdout:
            line = line.strip()
            recent_lines.append(line)
            logger.debug(f"[app output]: {line}")

            # Detect app start trigger
            if "App output:" in line:
                app_started = True
                start_time = time.time()
                logger.info("App start detected. Starting run timer.")
                break

            # Timeout waiting for app to start
            if time.time() - signal_start > startup_timeout:
                process.terminate()
                logger.error(f"Timeout waiting for app start after {startup_timeout}s.")
                return False

        # At this point, either app started, or process.stdout hit EOF
        process.stdout.close()
        process.wait()
        if not app_started:
            logger.error(
                f"Process exited before app started (code: {process.returncode})"
            )
            logger.error("Last 10 log lines from device:")
            for log_line in recent_lines:
                logger.error(f"  {log_line}")
            return False

        # Setup threading to keep reading app outputs
        q = queue.Queue()
        t = threading.Thread(
            target=enqueue_output, args=(process.stdout, q), daemon=True
        )
        t.start()

        passed = True
        recent_lines = deque(maxlen=10)
        while True and app_started:
            try:
                line = q.get_nowait().strip()
                recent_lines.append(line)
                logger.debug(f"[app output]: {line}")
            except queue.Empty:
                pass

            status = get_app_status(APP_ID, args)
            # When app has started, check if it exited early
            if status != "running":
                logger.error(
                    f"App status switched to '{status}' after {time.time() - start_time:.2f}s but should run for {run_duration}s."
                )
                logger.error("Last 10 log lines from device:")
                for log_line in recent_lines:
                    logger.error(f"  {log_line}")
                passed = False
                break

            if time.time() - start_time >= run_duration:
                logger.info(f"App ran for {run_duration} seconds successfully.")
                break

            time.sleep(1)

        # Clean up process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        if passed:
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Error running app: {e}")
        return False


def connect_to_device(device: str, device_password: str):
    """Try to connect to the device by first trying the password method and if that fails trying the direct IP method"""
    connect_timeout = 60
    failed_logs = []

    # First try to connect to device using password
    try:
        result = subprocess.run(
            ["oakctl", "--password", device_password, "device", "info"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=connect_timeout,
        )
        device_info = re.sub(r"\s+", " ", result.stdout.decode().strip())
        logger.debug(f"Connected to device using password: {device_info}")
        return True
    except subprocess.CalledProcessError as e:
        log = "Failed to connect to device using password"
        failed_logs.append(log)
        logger.debug(f"{log}: {e}")
    except subprocess.TimeoutExpired:
        log = f"Timeout ({connect_timeout}s) while trying to connect to device using password."
        failed_logs.append(log)
        logger.debug(log)

    # If this fails then try to connect to specific device ip
    try:
        result = subprocess.run(
            ["oakctl", "--password", device_password, "connect", device],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=connect_timeout,
        )
        device_info = re.sub(r"\s+", " ", result.stdout.decode().strip())
        logger.debug(f"Connected to device using device IP: {device_info}")
        return True
    except subprocess.CalledProcessError as e:
        log = f"Failed to connect to device using IP `{device}`"
        failed_logs.append(log)
        logger.debug(f"{log}: {e}")
    except subprocess.TimeoutExpired:
        log = f"Timeout ({connect_timeout}s) while trying to connect to device using IP `{device}`."
        failed_logs.append(log)
        logger.debug(log)

    logger.error(f"Connection to device failed, logs: {failed_logs}")
    return False


def get_app_status(app_id: str, args: Dict):
    try:
        result = subprocess.run(
            [
                "oakctl",
                "--password",
                args["device_password"],
                "app",
                "list",
                "--format=json",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        apps = json.loads(result.stdout)
        for app in apps:
            if app["container_id"] == app_id:
                return app["status"]
        return None  # App not found
    except Exception as e:
        logger.warning(f"Failed to query app status: {e}")
        return None


def teardown():
    """Cleans up everything after the test"""
    # Clean up requirements.txt
    if os.path.exists("requirements.txt"):
        os.remove("requirements.txt")
        logger.debug("Deleted requirements.txt")
    if os.path.exists("requirements_old.txt"):
        os.rename("requirements_old.txt", "requirements.txt")
        logger.debug("Renamed requirements_old.txt → requirements.txt")

    # Delete app on device
    try:
        result = subprocess.run(
            ["oakctl", "app", "delete", APP_ID],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        logger.debug(f"App deleted:\n{result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to delete app:\n{e.stderr.strip()}")


if __name__ == "__main__":
    pytest.main([__file__])
