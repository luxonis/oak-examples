from typing import Optional, Dict, Tuple, List, Union
from packaging import version
from pathlib import Path
import logging
from contextlib import contextmanager
import os
import platform
import tomlkit

LOCAL_OAKAPP_BASE_TAGS = {
    "1.2.5",
    "1.2.7",
    "1.2.8",
    "1.2.9",
    "1.2.10",
    "1.2.11",
    "1.3.0",
    "1.5.2",
}
logger = logging.getLogger()

OS_MAPPING = {"Windows": "win", "Linux": "linux", "Darwin": "mac"}


def is_valid(
    example_dir: Path,
    known_failing_examples: Dict,
    desired_mode: str,
    desired_platform: str,
    desired_py: str,
    desired_dai: str,
) -> Tuple[bool, str]:
    desired = {
        "mode": desired_mode,
        "platform": desired_platform,
        "python_version": desired_py,
        "depthai_version": desired_dai,
        "os": OS_MAPPING.get(platform.system(), None),
    }

    for exp, cfg in known_failing_examples.items():
        if exp in example_dir.as_posix():
            rules = cfg["rules"]  # We require rules to always exist
            if evaluate_rule(rules, desired):
                return False, cfg.get("reason", "No reason provided")

    return True, ""


def evaluate_rule(rule: dict, desired: dict, log_prefix: str = "") -> bool:
    """
    Recursively evaluates a rule tree.
    Returns True if the rule means the example SHOULD FAIL.
    Also logs detailed information about which rule failed.
    """

    # OR block
    if "or" in rule:
        results = []
        for idx, subrule in enumerate(rule["or"]):
            r = evaluate_rule(subrule, desired, log_prefix + f"OR[{idx}] -> ")
            results.append(r)
        return any(results)

    # AND block
    if "and" in rule:
        results = []
        for idx, subrule in enumerate(rule["and"]):
            r = evaluate_rule(subrule, desired, log_prefix + f"AND[{idx}] -> ")
            results.append(r)
        return all(results)

    # Leaf block
    key, failing_value = next(iter(rule.items()))
    have = desired[key]

    # Run condition checks
    if key in ("mode", "platform", "python_version", "os"):
        failed = not check_general(have, failing_value)

    elif key == "depthai_version":
        failed = not check_dai(have, failing_value)

    else:
        raise ValueError(f"Unknown rule condition: {key}")

    # Logging for leaf nodes
    if failed:
        logger.info(
            f"{log_prefix}Condition failed: `{key}` "
            f"Got `{have}`, should not match `{failing_value}`"
        )

    return failed


def check_general(have: str, failing: Union[str, List[str]]):
    """Returns True if test will pass"""
    if failing == "all":
        return False
    return have not in failing


def check_dai(have: str, failing: str):
    """Returns True if DAI version we have is not failing"""
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
    depthai_version: Optional[str],
    depthai_nodes_version: Optional[str],
) -> List[str]:
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
            requirements.insert(
                0,
                "--extra-index-url https://artifacts.luxonis.com/artifactory/luxonis-python-release-local/\n",
            )
            if parsed_dai_version.is_devrelease:
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


def local_base_image(oakapp_toml_path: Path, local_static_registry: str) -> bool:
    """Redirect mirrored base images to the local registry without changing tags."""
    api_url = local_static_registry.strip().rstrip("/")
    if not api_url:
        return False
    if not api_url.startswith(("http://", "https://")):
        api_url = f"http://{api_url}"

    content = oakapp_toml_path.read_text(encoding="utf-8")
    config = tomlkit.parse(content)
    base_image = config.get("base_image")

    if base_image is None:
        base_image = tomlkit.table()
        base_image["image_name"] = "debian"
        base_image["image_tag"] = "bookworm-slim"
        config["base_image"] = base_image
    else:
        image_name = base_image.get("image_name")
        image_tag = base_image.get("image_tag")
        mirrored = (
            image_name == "luxonis/oakapp-base" and image_tag in LOCAL_OAKAPP_BASE_TAGS
        ) or (image_name == "debian" and image_tag == "bookworm-slim")
        if not mirrored:
            logger.info(
                "Base image %s:%s is not in the local mirror; leaving %s unchanged",
                image_name,
                image_tag,
                oakapp_toml_path,
            )
            return False

    base_image["api_url"] = api_url
    # The local static registry does not use Docker Hub's token service.
    for key in ("service", "oauth_url", "auth_type", "auth_name"):
        base_image.pop(key, None)

    updated_content = tomlkit.dumps(config)
    if updated_content == content:
        return False
    oakapp_toml_path.write_text(updated_content, encoding="utf-8")

    logger.info("✓ configured local [base_image] in %s", oakapp_toml_path)
    return True


@contextmanager
def change_and_restore_dir(target_dir: Path):
    """Runs context in the target dir and then changes bach to the original dir"""
    original_dir = Path.cwd()
    os.chdir(target_dir)
    try:
        yield
    finally:
        os.chdir(original_dir)
