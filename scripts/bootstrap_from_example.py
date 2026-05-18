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
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")

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


def insert_after_title(markdown: str, sections: list[str]) -> str:
    lines = markdown.rstrip().splitlines()
    inserted = "\n\n".join(section.strip() for section in sections if section.strip())

    if lines and lines[0].startswith("# "):
        rest = lines[1:]
        while rest and rest[0] == "":
            rest = rest[1:]
        lines = lines[:1] + ["", inserted, ""] + rest
    else:
        lines = [inserted, ""] + lines
    return "\n".join(lines).rstrip() + "\n"


def build_project_origin_section(example: Path) -> str:
    return (
        "## Project Origin\n\n"
        f"This project was bootstrapped from `oak-examples/{example.as_posix()}`. "
        "Treat this directory as an independent project: prefer local files when modifying behavior, "
        "and use the source example only as upstream reference material."
    )


def build_start_here_section() -> str:
    return (
        "## Start Here\n\n"
        "1. Read [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md) for shared Luxonis/OAK vocabulary, platform concepts, and documentation entrypoints.\n"
        "2. Then follow this example-specific guide for local architecture, constraints, and validation."
    )


def transform_agents(markdown: str, example: Path) -> str:
    return insert_after_title(
        markdown,
        [build_project_origin_section(example), build_start_here_section()],
    )


def validate_standalone_markdown_links(markdown: str) -> None:
    errors: list[str] = []
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        for match in MARKDOWN_LINK_RE.finditer(line):
            href = match.group(1).split("#", 1)[0].strip()
            if not href or href.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path = Path(href)
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"line {line_number}: {match.group(1)}")
    if errors:
        details = "\n".join(f"  - {error}" for error in errors)
        raise ValueError(
            "Generated AGENTS.md contains relative links that escape the project root. "
            "Move cross-example links to ## Related Examples and use GitHub main URLs.\n"
            f"{details}"
        )


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


def bootstrap(example: Path, output: Path) -> None:
    example_dir = (
        (ROOT / example).resolve() if not example.is_absolute() else example.resolve()
    )
    output_dir = output.resolve()

    if not example_dir.is_dir():
        raise FileNotFoundError(f"Example directory does not exist: {example_dir}")
    if not (example_dir / "AGENTS.md").is_file():
        raise FileNotFoundError(f"Example must contain AGENTS.md: {example_dir}")
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    try:
        output_dir.relative_to(example_dir)
    except ValueError:
        pass
    else:
        raise ValueError(f"Output directory must not be inside the source example: {output_dir}")
    if output_dir == ROOT:
        raise ValueError(f"Output directory must not be the repository root: {output_dir}")

    output_dir.mkdir(parents=True)
    copy_example(example_dir, output_dir)

    example_ref = example if not example.is_absolute() else example_dir.relative_to(ROOT)
    transformed_agents = transform_agents(
        (example_dir / "AGENTS.md").read_text(encoding="utf-8"), example_ref
    )
    validate_standalone_markdown_links(transformed_agents)
    (output_dir / "AGENTS.md").write_text(transformed_agents, encoding="utf-8")
    (output_dir / "CLAUDE.md").write_text(transformed_agents, encoding="utf-8")
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
    args = parser.parse_args()

    try:
        bootstrap(args.example, args.output)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
