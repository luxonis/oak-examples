from __future__ import annotations

import os
import sys
from pathlib import Path


def configure_depthai_path() -> None:
    candidates = []
    explicit_path = os.environ.get("DEPTHAI_PYTHON_BINDINGS")
    if explicit_path:
        candidates.append(explicit_path)
    candidates.extend(os.environ.get("PYTHONPATH", "").split(os.pathsep))

    for candidate in candidates:
        if not candidate:
            continue
        bindings_path = Path(candidate)
        if bindings_path.exists() and str(bindings_path) not in sys.path:
            sys.path.insert(0, str(bindings_path))
