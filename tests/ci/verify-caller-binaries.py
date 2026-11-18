#!/usr/bin/env python3
"""Verify installed caller binaries against the artifacts on the testbed."""

import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys


def output(*args):
    return subprocess.check_output(args, text=True, timeout=60).strip()


def main():
    host = sys.argv[1]
    root = Path("src")
    artifact_dir = {
        "linux": "x86_64/linux",
        "mac": "arm64/darwin",
        "windows": "x86_64/windows",
    }[host]
    source = root / ".artifacts" / artifact_dir
    binary_name = "oakctl.exe" if host == "windows" else "oakctl"
    installed = shutil.which(binary_name)
    if not installed:
        raise RuntimeError("Installed oakctl is missing from PATH")
    expected_hash = hashlib.sha256((source / binary_name).read_bytes()).hexdigest()
    if hashlib.sha256(Path(installed).read_bytes()).hexdigest() != expected_hash:
        raise RuntimeError("Installed oakctl does not match the caller artifact")
    expected_version = output(str(source / binary_name), "version")
    if output(installed, "version") != expected_version:
        raise RuntimeError("Installed oakctl version does not match the artifact")
    agents = list((root / ".artifacts").glob("oak-agent-*-arm-rvc4.tar.lz4"))
    if len(agents) != 1:
        raise RuntimeError("Expected one RVC4 oak-agent archive")
    expected_agent = re.fullmatch(r"oak-agent-(.+)-arm-rvc4.tar.lz4", agents[0].name)[1]
    try:
        # Do not let a Windows daemon inherit the SSH session's output pipes.
        subprocess.run(
            [installed, "adb", "start-server"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=60,
        )
        actual_agent = output(installed, "adb", "shell", "oak-agent", "--version")
        if actual_agent != expected_agent:
            raise RuntimeError(f"Expected agent {expected_agent}, got {actual_agent}")
        print(
            f"Verified oakctl {expected_version} (sha256 {expected_hash})", flush=True
        )
        print(f"Verified oak-agent {actual_agent}", flush=True)
    finally:
        if host == "windows":
            subprocess.run([installed, "adb", "kill-server"], check=True, timeout=60)


if __name__ == "__main__":
    main()
