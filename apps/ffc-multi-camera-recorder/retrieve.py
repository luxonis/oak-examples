#!/usr/bin/env python3
"""List, retrieve, or delete complete OAK camera recording sessions."""

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


MARKER = "__OAK_RECORDER_DATA__"
END_MARKER = "__OAK_RECORDER_END__"
CHUNK_SIZE = 32 * 1024 * 1024
SESSION_NAME = re.compile(
    r"^(\d{8}T\d{6}\.\d{6}Z(?:_offline)?)_cam([a-z]+)\.(mkv|h264)$"
)
SESSION_FILE = re.compile(
    r"^(\d{8}T\d{6}\.\d{6}Z(?:_offline)?)_cam[a-z]+\.(?:mkv|h264|raw10|jsonl)$"
)
REMOTE_LIST = """import json,os
root=os.path.join(os.environ["OAKAGENT_STORAGE_SHARED"],"recordings")
print("__OAK_RECORDER_DATA__")
print(json.dumps(sorted((p.name,p.stat().st_size) for p in os.scandir(root) if p.is_file())))
print("__OAK_RECORDER_END__")"""
REMOTE_READ = """import base64,os,sys
name,offset,count=sys.argv[1],int(sys.argv[2]),int(sys.argv[3])
if name!=os.path.basename(name) or name in (".",".."):
 raise ValueError("Expected a recording file name")
path=os.path.join(os.environ["OAKAGENT_STORAGE_SHARED"],"recordings",name)
with open(path,"rb") as f:
 f.seek(offset)
 data=f.read(count)
print("__OAK_RECORDER_DATA__")
print(base64.b64encode(data).decode("ascii"))
print("__OAK_RECORDER_END__")"""
REMOTE_MANAGE = """import json,os,re,sys
root=os.path.join(os.environ["OAKAGENT_STORAGE_SHARED"],"recordings")
stamp,expected_json,action=sys.argv[1:4]
if not re.fullmatch(r"\\d{8}T\\d{6}\\.\\d{6}Z(?:_offline)?",stamp) or action not in ("check","delete"):
 raise ValueError("Invalid session request")
pattern=re.compile(re.escape(stamp)+r"_cam[a-z]+\\.(?:mkv|h264|raw10|jsonl)")
entries={e.name:e for e in os.scandir(root) if pattern.fullmatch(e.name)}
names=sorted(entries)
result={"files":names,"bytes":0,"active":[],"deleted":[]}
if names!=sorted(json.loads(expected_json)):
 result["error"]="Session files changed; list sessions again before deleting"
else:
 inodes={}
 for name,e in entries.items():
  if not e.is_file(follow_symlinks=False):
   result["error"]="Session contains a non-regular file; refusing deletion"
   break
  st=e.stat(follow_symlinks=False)
  inodes[(st.st_dev,st.st_ino)]=name
  result["bytes"]+=st.st_size
 if "error" not in result:
  active=set()
  for pid in os.listdir("/proc"):
   if not pid.isdecimal(): continue
   fd_dir=os.path.join("/proc",pid,"fd")
   try: fds=os.listdir(fd_dir)
   except FileNotFoundError: continue
   except PermissionError:
    result["error"]="Cannot inspect every open file; refusing deletion"
    break
   for fd in fds:
    try: st=os.stat(os.path.join(fd_dir,fd))
    except FileNotFoundError: continue
    except PermissionError:
     result["error"]="Cannot inspect every open file; refusing deletion"
     break
    except OSError: continue
    name=inodes.get((st.st_dev,st.st_ino))
    if name: active.add(name)
   if "error" in result: break
  result["active"]=sorted(active)
  if action=="delete" and "error" not in result:
   if active:
    result["error"]="Session is still open for recording; refusing deletion"
   else:
    for name in names:
     try: os.unlink(entries[name].path)
     except OSError as e:
      result["error"]=f"Deletion stopped after {len(result['deleted'])} files: {e}"
      break
     result["deleted"].append(name)
print("__OAK_RECORDER_DATA__")
print(json.dumps(result))
print("__OAK_RECORDER_END__")"""


def oakctl_path():
    return (
        os.environ.get("OAKCTL")
        or shutil.which("oakctl")
        or str(Path.home() / ".local/share/oakctl/oakctl")
    )


def detect_running_app(device):
    command = [oakctl_path(), "app", "list", "--format", "json"]
    if device:
        command += ["-d", device]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(
            f"Could not list OAK Apps: {(result.stderr or result.stdout)[-500:]}"
        )
    running = [
        app for app in json.loads(result.stdout) if app.get("status") == "running"
    ]
    if len(running) != 1:
        raise ValueError(
            f"Expected one running app; found {len(running)}. "
            "Pass its app ID explicitly if needed."
        )
    return running[0]["app_id"]


def remote(app_id, device, script, *args):
    command = [oakctl_path(), "app", "exec"]
    if device:
        command += ["-d", device]
    command += [app_id, "python3.12", "--", "-c", script, *map(str, args)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(
            f"OAK App command failed: {(result.stderr or result.stdout)[-500:]}"
        )
    match = re.search(rf"{MARKER}\s*\n([^\n]*)\n{END_MARKER}", result.stdout)
    if not match:
        raise RuntimeError(f"Unexpected oakctl response: {result.stdout[-500:]}")
    return match.group(1)


def copy_file(app_id, device, filename, size, output):
    if output.exists():
        raise FileExistsError(f"Local file already exists: {output}")
    partial = output.with_name(output.name + ".partial")
    print(f"Copying {filename} ({size} bytes) -> {output}", flush=True)
    with partial.open("xb") as target:
        for offset in range(0, size, CHUNK_SIZE):
            encoded = remote(
                app_id,
                device,
                REMOTE_READ,
                filename,
                offset,
                min(CHUNK_SIZE, size - offset),
            )
            data = base64.b64decode(encoded, validate=True)
            if len(data) != min(CHUNK_SIZE, size - offset):
                raise RuntimeError(f"Short read of {filename} at offset {offset}")
            target.write(data)
        target.flush()
        os.fsync(target.fileno())
    os.link(partial, output)  # Fails if a local file appeared during the copy.
    partial.unlink()
    print(f"Copied {filename}", flush=True)


def recording_sessions(listing):
    """Group nonempty videos by start time, with one preferred file per camera."""
    sessions = {}
    for name, size in listing:
        match = SESSION_NAME.fullmatch(name)
        if not match or size <= 0:
            continue
        stamp, camera, extension = match.groups()
        cameras = sessions.setdefault(stamp, {})
        previous = cameras.get(camera)
        if previous is None or (extension == "mkv" and previous[0].endswith(".h264")):
            cameras[camera] = (name, size)
    return {stamp: sessions[stamp] for stamp in sorted(sessions, reverse=True)}


def session_summary(stamp, cameras):
    offline = stamp.endswith("_offline")
    clock_stamp = stamp.removesuffix("_offline")
    started = datetime.strptime(clock_stamp, "%Y%m%dT%H%M%S.%fZ").replace(
        tzinfo=timezone.utc
    )
    names = ", ".join(name.upper() for name in sorted(cameras))
    total = sum(size for _, size in cameras.values())
    amount = (
        f"{total / 1024**3:.2f} GiB"
        if total >= 1024**3
        else f"{total / 1024**2:.1f} MiB"
    )
    label = started.strftime("%Y-%m-%d %H:%M:%S UTC")
    if offline:
        label += " (estimated)"
    elif started.year < 2024:
        label += " (clock reset)"
    return label, names, amount


def select_stamp(parser, selector, sessions):
    stamps = list(sessions)
    if selector.isdecimal():
        number = int(selector)
        if not 1 <= number <= len(stamps):
            parser.error(f"session number must be between 1 and {len(stamps)}")
        return stamps[number - 1]
    if selector in sessions:
        return selector
    matches = [
        stamp
        for stamp, cameras in sessions.items()
        if session_summary(stamp, cameras)[0] == selector
    ]
    if len(matches) != 1:
        parser.error(
            "session time not found or ambiguous; list sessions to choose a row"
        )
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "app_id",
        nargs="?",
        help="Optional app ID; auto-detected when one app is running",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--latest",
        action="store_true",
        help="Download every camera from the newest session",
    )
    selection.add_argument(
        "--session",
        metavar="NUMBER_OR_TIME",
        help="Download every camera from a listed row or its UTC start time",
    )
    selection.add_argument(
        "--delete-session",
        metavar="NUMBER_OR_TIME",
        help="Delete every recording file from a listed session",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview a selected download or deletion"
    )
    parser.add_argument(
        "--device", help="Device IP or serial; omit for the selected device"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Download destination (default: downloads/TIMESTAMP)",
    )
    args = parser.parse_args()
    if not (args.latest or args.session or args.delete_session) and (
        args.dry_run or args.output_dir
    ):
        parser.error("--dry-run and --output-dir require a session selection")
    if args.delete_session and args.output_dir:
        parser.error("--output-dir cannot be used with --delete-session")

    try:
        app_id = args.app_id or detect_running_app(args.device)
        listing = json.loads(remote(app_id, args.device, REMOTE_LIST))
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    sessions = recording_sessions(listing)
    if not sessions:
        print("No recordings found")
        return
    if args.latest:
        stamp = next(iter(sessions))
    elif args.session or args.delete_session:
        stamp = select_stamp(parser, args.session or args.delete_session, sessions)
    else:
        print("Recording sessions (newest first):")
        print(f"{'#':>3}  {'Started':<38}  {'Cameras':<22}  {'Total':>10}")
        for number, (stamp, cameras) in enumerate(sessions.items(), start=1):
            started, names, amount = session_summary(stamp, cameras)
            print(f"{number:>3}  {started:<38}  {names:<22}  {amount:>10}")
        print(
            "\nUse --session NUMBER to download or --delete-session NUMBER to delete a row."
        )
        return

    cameras = sessions[stamp]
    started, names, amount = session_summary(stamp, cameras)
    if args.delete_session:
        expected = sorted(
            name
            for name, _ in listing
            if (match := SESSION_FILE.fullmatch(name)) and match.group(1) == stamp
        )
        try:
            status = json.loads(
                remote(
                    app_id,
                    args.device,
                    REMOTE_MANAGE,
                    stamp,
                    json.dumps(expected),
                    "check",
                )
            )
        except RuntimeError as error:
            parser.exit(1, f"Cannot inspect session: {error}\n")
        if error := status.get("error"):
            parser.exit(1, f"Cannot delete session: {error}\n")
        total = status["bytes"]
        size = (
            f"{total / 1024**3:.2f} GiB"
            if total >= 1024**3
            else f"{total / 1024**2:.1f} MiB"
        )
        print(
            f"Session {started}: {names}; {len(status['files'])} files, {size} on device"
        )
        if status["active"]:
            parser.exit(
                1, "This session is currently being recorded; wait until it closes.\n"
            )
        if args.dry_run:
            print("Dry run: no files deleted")
            return
        try:
            answer = input("Delete this entire session from the device? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() != "y":
            print("Deletion cancelled")
            return
        try:
            result = json.loads(
                remote(
                    app_id,
                    args.device,
                    REMOTE_MANAGE,
                    stamp,
                    json.dumps(expected),
                    "delete",
                )
            )
        except RuntimeError as error:
            parser.exit(1, f"Deletion failed: {error}\n")
        if error := result.get("error"):
            parser.exit(1, f"Deletion failed: {error}\n")
        print(f"Deleted {len(result['deleted'])} files from session {started}")
        return

    target_dir = args.output_dir or Path("downloads") / stamp
    print(f"Session {started}: {names} ({amount}) -> {target_dir}")
    if args.dry_run:
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    for name, size in (cameras[camera] for camera in sorted(cameras)):
        copy_file(app_id, args.device, name, size, target_dir / name)
    print(f"Retrieved {len(cameras)} camera videos to {target_dir}")


if __name__ == "__main__":
    main()
