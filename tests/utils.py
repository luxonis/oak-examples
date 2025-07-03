from __future__ import annotations   # importing this so tests work on 3.8
from packaging import version
from pathlib import Path
import logging
from contextlib import contextmanager
import os



logger = logging.getLogger()


def is_valid(
    example_dir: Path,
    known_failing_examples: dict,
    desired_platform: str | None,
    desired_py: str | None,
    desired_dai: str | None,
) -> tuple[bool, str]:
    """Checks if the example is valid or known to fail with this parameters.
    If it is known to fail it returns the reason.
    """
    for exp in known_failing_examples:
        if exp in str(example_dir):
            failing_platform = known_failing_examples[exp].get("platform", None)
            failing_python = known_failing_examples[exp].get("python_version", None)
            failing_dai = known_failing_examples[exp].get("depthai_version", None)

            platform_failed = None
            if failing_platform is not None:
                platform_failed = not check_platform(desired_platform, failing_platform)

            python_failed = None
            if failing_python is not None:
                python_failed = not check_platform(desired_py, failing_python)

            dai_failed = None
            if failing_dai is not None:
                dai_failed = not check_platform(desired_dai, failing_dai)

            # Return False only if all checks failed and exclude non relevant checks
            failed = [
                f for f in [platform_failed, python_failed, dai_failed] if f is not None
            ]
            if all(f is True for f in failed):
                if platform_failed:
                    logger.info(
                        f"Platform check failed: Got `{desired_platform}`, shouldn't be `{known_failing_examples[exp]['platform']}`"
                    )
                if python_failed:
                    logger.info(
                        f"Python version check failed: Got `{desired_py}`, shouldn't be `{known_failing_examples[exp]['python_version']}`"
                    )
                if dai_failed:
                    logger.info(
                        f"DepthAI version check failed: Got `{desired_dai}`, shouldn't be `{known_failing_examples[exp]['depthai_version']}`"
                    )
                return (False, known_failing_examples[exp]["reason"])

    return (True, "")


def check_platform(have, failing):
    if failing == "all":
        return False
    return have not in failing


def check_python(have, failing):
    if failing == "all":
        return False
    return have not in failing


def check_dai(have, failing):
    if have is None or have == "":
        # if not explicitly set we assume it should pass with one specified in requirements
        return True

    if failing == "all":
        return False

    have_version = version.parse(have)

    # Extract operator and version number
    operators = ["<=", ">=", "<", ">"]
    for op in operators:
        if failing.startswith(op):
            version_number = failing[len(op) :]  # Remove operator from string
            failing_version = version.parse(version_number)

            # Perform the appropriate comparison
            if op == "<":
                return not (have_version < failing_version)
            elif op == "<=":
                return not (have_version <= failing_version)
            elif op == ">":
                return not (have_version > failing_version)
            elif op == ">=":
                return not (have_version >= failing_version)

    # If no operator is found, assume exact match
    return not (have_version == version.parse(failing_version))


def adjust_requirements(
    current_req_path: Path,
    depthai_version: str | None,
    depthai_nodes_version: str | None,
) -> list[str]:
    """Adjust the requirements if custom package versions should be used"""
    with open(current_req_path, "r") as f:
        requirements = f.readlines()

    if depthai_version:
        try:
            parsed_dai_version = version.parse(depthai_version)
            requirements = [
                f"depthai=={depthai_version}\n"
                if ("depthai" in line and "depthai-nodes" not in line)
                else line
                for line in requirements
            ]

            if parsed_dai_version.is_devrelease:
                requirements.insert(
                    0,
                    "--extra-index-url https://artifacts.luxonis.com/artifactory/luxonis-python-release-local/\n",
                )
                requirements.insert(
                    0,
                    "--extra-index-url https://artifacts.luxonis.com/artifactory/luxonis-python-snapshot-local/\n",
                )

        except version.InvalidVersion:
            # DAI can't be installed directly from GH repo like e.g. depthai-nodes
            logger.error("Can't parse DepthAI version")

    if depthai_nodes_version:
        try:
            _ = version.parse(depthai_nodes_version)
            requirements = [
                f"depthai-nodes=={depthai_nodes_version}\n"
                if "depthai-nodes" in line
                else line
                for line in requirements
            ]
        except version.InvalidVersion:
            requirements = [
                f"{depthai_nodes_version}\n" if "depthai-nodes" in line else line
                for line in requirements
            ]

    return requirements


@contextmanager
def change_and_restore_dir(target_dir: Path):
    """Runs context in the target dir and then changes bach to the original dir"""
    original_dir = Path.cwd()
    os.chdir(target_dir)
    try:
        yield
    finally:
        os.chdir(original_dir)
