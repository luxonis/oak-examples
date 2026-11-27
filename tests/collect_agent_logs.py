"""Collect OAK device diagnostics through the reserved testbed's HIL tools."""

import gzip
import json
import subprocess
import sys
import zlib
from pathlib import Path
from uuid import uuid4


def run_camera(camera, *arguments, timeout=60):
    try:
        subprocess.run(
            [*camera, *arguments],
            check=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return f"{arguments[0]} timed out after {timeout}s"
    except subprocess.CalledProcessError as error:
        # The HIL command's output can contain testbed credentials.
        return f"{arguments[0]} exited with status {error.returncode}"
    except OSError as error:
        return str(error)
    return None


def collect_logs(camera, output_dir):
    remote_dir = f"/tmp/oak-examples-agent-logs-{uuid4().hex}"
    error = run_camera(camera, "command", "-c", f"mkdir -m 700 '{remote_dir}'")
    if error is not None:
        return [f"Creating the camera log directory: {error}"]

    logs = (
        (
            "oak-agent.log",
            "journalctl -u oak-agent --no-pager -o short-precise",
            60,
        ),
        (
            "persistent-logs.tar.gz",
            "tar -czf - -C /overlay persistent-logs",
            300,
        ),
    )
    errors = []
    unlock_attempted = False
    try:
        for filename, command, timeout in logs:
            remote_file = f"{remote_dir}/{filename}"
            partial = output_dir / f".{filename}.part"
            error = run_camera(
                camera,
                "command",
                "-c",
                f"{command} > '{remote_file}'",
                timeout=timeout,
            )
            if error is None:
                download = ("scp", "--download", partial.as_posix(), remote_file)
                error = run_camera(camera, *download, timeout=timeout)
                if error is not None and not unlock_attempted:
                    # SCP needs SSH. Try the HIL unlock once if SSH was unavailable.
                    unlock_attempted = True
                    unlock_error = run_camera(camera, "unlock")
                    if unlock_error is not None:
                        errors.append(f"Unlocking camera SSH: {unlock_error}")
                    error = run_camera(camera, *download, timeout=timeout)

            if error is None:
                try:
                    if partial.stat().st_size == 0:
                        raise OSError("SCP downloaded an empty file")
                    if filename.endswith(".tar.gz"):
                        with gzip.open(partial, "rb") as archive:
                            while archive.read(1024 * 1024):
                                pass
                    partial.replace(output_dir / filename)
                except (OSError, EOFError, zlib.error) as download_error:
                    error = str(download_error)

            if error is not None:
                partial.unlink(missing_ok=True)
                errors.append(f"{filename}: {error}")
    finally:
        files = " ".join(f"'{remote_dir}/{filename}'" for filename, _, _ in logs)
        error = run_camera(
            camera, "command", "-c", f"rm -f {files} && rmdir '{remote_dir}'"
        )
        if error is not None:
            errors.append(f"Removing temporary camera files: {error}")

    return errors


def main():
    artifacts_dir = Path(__file__).resolve().parents[1] / ".artifacts"
    output_dir = artifacts_dir / "agent-logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        context = json.loads(
            (artifacts_dir / "hil-context.json").read_text(encoding="utf-8")
        )
        # The HIL CLI accepts "." only for a testbed with exactly one camera.
        camera = [
            "hil_camera",
            "--testbed",
            context["testbed"],
            "--reservation-name",
            context["reservation_name"],
            ".",
        ]
        errors = collect_logs(camera, output_dir)
    except (OSError, ValueError, KeyError):
        errors = ["Could not read the HIL context or save device logs."]

    if errors:
        (output_dir / "log-collection-errors.log").write_text(
            "\n".join(errors) + "\n", encoding="utf-8"
        )
        print("Warning: some OAK device logs could not be collected.", file=sys.stderr)


if __name__ == "__main__":
    main()
