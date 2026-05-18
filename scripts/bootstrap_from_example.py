#!/usr/bin/env python3
"""Repo-local wrapper for the installable bootstrap-example skill helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path

HELPER = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "bootstrap-example"
    / "bootstrap_from_example.py"
)

spec = importlib.util.spec_from_file_location("bootstrap_example_helper", HELPER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load bootstrap helper: {HELPER}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == "__main__":
    raise SystemExit(module.main())
