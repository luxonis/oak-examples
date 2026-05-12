#!/usr/bin/env python3
"""Simulate `oakctl app create` by bootstrapping a project from an example.

This is a reference implementation for the deterministic documentation transform
expected from `oakctl app create`; it is not intended to replace oakctl.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ESSENTIAL_KNOWLEDGE = ROOT / "ESSENTIAL_KNOWLEDGE.md"

IGNORED_PARTS = {
    ".git",
    ".cache",
    ".depthai_cached_models",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "env",
    "node_modules",
    "venv",
}


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_PARTS for part in path.parts)


def remove_related_examples(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() == "## Related Examples":
            index += 1
            while index < len(lines) and not lines[index].startswith("## "):
                index += 1
            while output and output[-1] == "":
                output.pop()
            if index < len(lines) and output:
                output.append("")
            continue
        output.append(lines[index])
        index += 1
    return "\n".join(output).rstrip() + "\n"


def slugify_identifier_part(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "app"


def update_oakapp_identifier(output_dir: Path) -> None:
    oakapp = output_dir / "oakapp.toml"
    if not oakapp.exists():
        return

    content = oakapp.read_text(encoding="utf-8")
    new_identifier = f"com.example.{slugify_identifier_part(output_dir.name)}"
    updated, count = re.subn(
        r'(?m)^identifier\s*=\s*["\'][^"\']+["\']\s*$',
        f'identifier = "{new_identifier}"',
        content,
        count=1,
    )
    if count == 0:
        updated = f'identifier = "{new_identifier}"\n' + content
    oakapp.write_text(updated, encoding="utf-8")


def copy_example(example_dir: Path, output_dir: Path) -> None:
    for source in example_dir.rglob("*"):
        relative = source.relative_to(example_dir)
        if is_ignored(relative):
            continue
        target = output_dir / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def bootstrap(example: Path, output: Path, force: bool) -> None:
    example_dir = (
        (ROOT / example).resolve() if not example.is_absolute() else example.resolve()
    )
    output_dir = output.resolve()

    if not example_dir.is_dir():
        raise FileNotFoundError(f"Example directory does not exist: {example_dir}")
    if not (example_dir / "AGENTS.md").is_file():
        raise FileNotFoundError(f"Example must contain AGENTS.md: {example_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        if not force:
            raise FileExistsError(f"Output directory is not empty: {output_dir}")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    copy_example(example_dir, output_dir)

    transformed_agents = remove_related_examples(
        (example_dir / "AGENTS.md").read_text(encoding="utf-8")
    )
    (output_dir / "AGENTS.md").write_text(transformed_agents, encoding="utf-8")
    shutil.copy2(ESSENTIAL_KNOWLEDGE, output_dir / "ESSENTIAL_KNOWLEDGE.md")
    update_oakapp_identifier(output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap a standalone project from an oak-examples example."
    )
    parser.add_argument(
        "example", type=Path, help="Example path relative to repository root."
    )
    parser.add_argument("output", type=Path, help="Output project directory.")
    parser.add_argument(
        "--force", action="store_true", help="Overwrite a non-empty output directory."
    )
    args = parser.parse_args()

    try:
        bootstrap(args.example, args.output, args.force)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
