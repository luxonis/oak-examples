import pytest
from pathlib import Path
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def pytest_addoption(parser):
    parser.addoption(
        "--root-dir",
        type=Path,
        nargs="+",
        required=True,
        help="One or more paths to directories containing examples (space-separated).",
    )
    parser.addoption(
        "--timeout",
        type=int,
        default=30,
        help="Timeout for script execution (default: 30s).",
    )
    parser.addoption(
        "--depthai-version",
        type=str,
        default="",
        help="Specify a depthai version to override requirements.txt.",
    )
    parser.addoption(
        "--depthai-nodes-version",
        type=str,
        default="",
        help="Specify a depthai-nodes version to override requirements.txt. Can be either released version or branch from GH.",
    )
    parser.addoption(
        "--environment-variables",
        type=str,
        help="List of additional environment variables (format: VAR1=VAL1 VAR2=VAL2).",
    )
    parser.addoption(
        "--virtual-display",
        action="store_true",
        help="Enable virtual display (sets DISPLAY=':99'). Only used for peripheral tests.",
    )
    parser.addoption(
        "--platform",
        default="rvc2",
        type=str,
        choices=["rvc2", "rvc4"],
        help="Specify a platform this is tested on (rvc2 or rvc4). Only used for filtering test examples.",
    )
    parser.addoption(
        "--python-version",
        default="3.10",
        type=str,
        choices=["3.8", "3.10", "3.12"],
        help="Specify a python version this is tested with (3.8, 3.10 or 3.12). Only used for filtering test examples.",
    )
    parser.addoption(
        "--strict-mode",
        default="no",
        type=str,
        choices=["yes", "no"],
        help="If set to 'yes', tests will fail on DepthAI warnings.",
    )
    parser.addoption(
        "--device",
        default="",
        type=str,
        help="Device to perform standalone tests on. If testing just peripheral then not required.",
    )
    parser.addoption(
        "--device-password",
        type=str,
        default="",
        help="Specify device password. If testing just peripheral then not required.",
    )

    parser.addoption(
        "--local-static-registry",
        type=str,
        default="",
        help="Local registry that will mirror used images for easier testing",
    )


@pytest.fixture(scope="session")
def test_args(request):
    args = {
        "root_dir": request.config.getoption("--root-dir"),
        "timeout": request.config.getoption("--timeout"),
        "depthai_version": request.config.getoption("--depthai-version"),
        "depthai_nodes_version": request.config.getoption("--depthai-nodes-version"),
        "environment_variables": request.config.getoption("--environment-variables"),
        "virtual_display": request.config.getoption("--virtual-display"),
        "platform": request.config.getoption("--platform"),
        "python_version": request.config.getoption("--python-version"),
        "device_password": request.config.getoption("--device-password"),
        "local_static_registry": request.config.getoption("--local-static-registry"),
        "strict_mode": True
        if request.config.getoption("--strict-mode") == "yes"
        else False,
        "device": request.config.getoption("--device"),
    }

    logger.info(f"Test arguments: {args}")
    return args


def pytest_generate_tests(metafunc):
    if "example_dir" in metafunc.fixturenames:
        root_dirs = metafunc.config.getoption("--root-dir")
        exp_dirs = set()  # Use a set to avoid duplicates

        for root_dir in root_dirs:
            for dirpath, dirnames, filenames in os.walk(root_dir):
                if "main.py" in filenames and "requirements.txt" in filenames:
                    exp_dirs.add(Path(dirpath))
                elif "main.py" in filenames and "requirements.txt" not in filenames:
                    logger.info(
                        f"Skipping {dirpath} because it has no requirements.txt"
                    )
                elif "main.py" not in filenames and "requirements.txt" in filenames:
                    logger.info(f"Skipping {dirpath} because it has no main.py")

        exp_dirs = sorted(exp_dirs)  # Sort for consistency
        metafunc.parametrize("example_dir", exp_dirs, ids=[str(p) for p in exp_dirs])
