"""One-shot, idempotent DSP bootstrap for the OAK4 app container.

Everything the QNN EP needs that is not plain Python:
  1. `/dev/fastrpc-cdsp` alias node — the QNN EP factory only synthesizes an
     NPU device if a node with that name exists (soc_utils.cc), but Luxonis OS
     names it `/dev/adsprpc-smd`.
  2. The device-OS `libcdsprpc.so` (FastRPC transport) preloaded with its
     OE dependency chain (liblog, libcutils, ...), which does not exist in the
     Debian-based container. Loading by absolute path with RTLD_GLOBAL makes
     the later `dlopen("libcdsprpc.so")` from the QNN stub resolve to it.
  3. `ADSP_LIBRARY_PATH` pointed at the onnxruntime-qnn wheel dir so the DSP
     side loads the wheel's own skel (stub and skel stay version-matched).

Requires (see the app's oakapp.toml): `/dev/adsprpc-smd` + dma_heap nodes in
`optional_devices`, `allowed_devices` cgroup rule, and the device `/usr/lib`
mounted read-only at `/host_usr_lib`.
"""

import ctypes
import os
import re
import stat
from dataclasses import dataclass, field

HOST_LIB_DIR = os.environ.get("OAK4ORT_HOST_LIB_DIR", "/host_usr_lib")
FASTRPC_ALIAS = "/dev/fastrpc-cdsp"
FASTRPC_NODE = "/dev/adsprpc-smd"

_MISSING_DEP_RE = re.compile(r"(\S+): cannot open shared object file")


@dataclass
class BootstrapStatus:
    ok: bool
    error: str = ""
    details: list = field(default_factory=list)

    def __bool__(self):
        return self.ok


_cached_status = None


def bootstrap(force=False):
    """Prepare the container for QNN/HTP. Idempotent; caches its result."""
    global _cached_status
    if _cached_status is not None and not force:
        return _cached_status
    _cached_status = _bootstrap_impl()
    return _cached_status


def _bootstrap_impl():
    details = []

    if os.uname().machine != "aarch64":
        return BootstrapStatus(
            False, "not an aarch64 device (running locally?)", details
        )

    if not os.path.exists(FASTRPC_NODE) and not os.path.exists(FASTRPC_ALIAS):
        return BootstrapStatus(
            False,
            f"no FastRPC device node ({FASTRPC_NODE}); add it to "
            "optional_devices in oakapp.toml",
            details,
        )

    err = _ensure_fastrpc_alias(details)
    if err:
        return BootstrapStatus(False, err, details)

    err = _set_adsp_library_path(details)
    if err:
        return BootstrapStatus(False, err, details)

    err = _preload_cdsprpc(details)
    if err:
        return BootstrapStatus(False, err, details)

    err = _preload_htp_backend(details)
    if err:
        return BootstrapStatus(False, err, details)

    return BootstrapStatus(True, "", details)


def _ensure_fastrpc_alias(details):
    if os.path.exists(FASTRPC_ALIAS):
        details.append(f"{FASTRPC_ALIAS}: already present")
        return None
    try:
        rdev = os.stat(FASTRPC_NODE).st_rdev
        os.mknod(FASTRPC_ALIAS, 0o600 | stat.S_IFCHR, rdev)
        details.append(f"{FASTRPC_ALIAS}: created (alias of {FASTRPC_NODE})")
        return None
    except OSError as e:
        return (
            f"cannot create {FASTRPC_ALIAS}: {e}; the container needs "
            'allowed_devices = [{ allow = true, access = "rwm" }] in oakapp.toml'
        )


def _set_adsp_library_path(details):
    try:
        import onnxruntime_qnn
    except ImportError:
        return "onnxruntime_qnn is not installed (pip install onnxruntime-qnn)"
    if os.environ.get("ADSP_LIBRARY_PATH"):
        details.append(f"ADSP_LIBRARY_PATH: kept ({os.environ['ADSP_LIBRARY_PATH']})")
        return None
    wheel_dir = getattr(
        onnxruntime_qnn,
        "LIB_DIR_FULL_PATH",
        os.path.dirname(onnxruntime_qnn.get_library_path()),
    )
    os.environ["ADSP_LIBRARY_PATH"] = wheel_dir
    details.append(f"ADSP_LIBRARY_PATH: set to {wheel_dir}")
    return None


def _preload_cdsprpc(details):
    host_lib = os.path.join(HOST_LIB_DIR, "libcdsprpc.so")
    target = host_lib if os.path.exists(host_lib) else "libcdsprpc.so"
    try:
        _load_with_deps(target, [HOST_LIB_DIR], details)
        details.append(f"libcdsprpc: loaded ({target})")
        return None
    except OSError as e:
        return (
            f"cannot load libcdsprpc.so: {e}; mount the device /usr/lib at "
            f"{HOST_LIB_DIR} via optional_mounts in oakapp.toml"
        )


def _preload_htp_backend(details):
    """The wheel's CPU-side QNN libs (libQnnHtp, libQnnSystem, ...) may need
    libs absent from the container (e.g. libatomic.so.1); preload them with
    deps resolved from the device OS."""
    import glob

    import onnxruntime_qnn

    lib_dir = os.path.dirname(onnxruntime_qnn.get_qnn_htp_path())
    required = {"libQnnHtp.so", "libQnnSystem.so"}
    for so_path in sorted(glob.glob(os.path.join(lib_dir, "libQnn*.so"))):
        name = os.path.basename(so_path)
        if "Skel" in name:  # Hexagon-side ELFs, not loadable on the CPU
            continue
        try:
            _load_with_deps(so_path, [HOST_LIB_DIR], details)
            details.append(f"preloaded {name}")
        except OSError as e:
            if name in required:
                return f"cannot load {name}: {e}"
            details.append(f"skipped {name}: {e}")
    return None


def _load_with_deps(target, search_dirs, details, _depth=0):
    """dlopen `target`, recursively pre-loading missing deps by absolute path."""
    if _depth > 25:
        raise OSError(f"dependency chain too deep while loading {target}")
    for _ in range(25):
        try:
            return ctypes.CDLL(target, mode=ctypes.RTLD_GLOBAL)
        except OSError as e:
            m = _MISSING_DEP_RE.search(str(e))
            if not m:
                raise
            dep = m.group(1)
            for d in search_dirs:
                dep_path = os.path.join(d, dep)
                if os.path.exists(dep_path):
                    _load_with_deps(dep_path, search_dirs, details, _depth + 1)
                    details.append(f"preloaded dep: {dep}")
                    break
            else:
                raise OSError(f"{dep} (needed by {target}) not found in {search_dirs}")
    raise OSError(f"too many iterations while loading {target}")
