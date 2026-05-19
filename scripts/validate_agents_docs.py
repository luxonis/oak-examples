#!/usr/bin/env python3
"""Validate per-example AGENTS.md coverage and structure.

This validator intentionally checks only per-example AGENTS.md files for
discovered example roots. The repository-root AGENTS.md follows a different
purpose and is not validated against the per-example template.
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from pathlib import Path

from generate_agents_index import IGNORED_PARTS, ROOT, discover_examples

H1_TITLE = "# AGENTS.md"
REQUIRED_SECTIONS = [
    "Summary",
    "Use This Example When",
    "Do Not Use This Example When",
    "Quick Facts",
    "Read First",
    "Architecture",
    "Constraints",
    "Related Examples",
    "Validation",
]
OPTIONAL_SECTIONS = [
    "Data Flow",
    "Modification Guide",
    "Common Adaptations",
    "Non-Obvious Repo Conventions",
]
CANONICAL_SECTION_ORDER = [
    "Summary",
    "Use This Example When",
    "Do Not Use This Example When",
    "Quick Facts",
    "Read First",
    "Architecture",
    "Data Flow",
    "Modification Guide",
    "Common Adaptations",
    "Constraints",
    "Non-Obvious Repo Conventions",
    "Related Examples",
    "Validation",
]
ALLOWED_SECTIONS = set(REQUIRED_SECTIONS) | set(OPTIONAL_SECTIONS)
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")


def rel(path: Path) -> Path:
    return path.relative_to(ROOT)


def normalize_runnable_example_root(directory: Path) -> Path:
    if (directory / "oakapp.toml").exists():
        return directory

    parents = directory.parents
    if len(parents) < 2:
        return directory

    candidate_root = parents[1]
    fallback_oak = candidate_root / "oakapp.toml"
    fallback_main = candidate_root / "backend" / "src" / "main.py"
    fallback_req = candidate_root / "backend" / "src" / "requirements.txt"
    if fallback_oak.exists() and fallback_main.exists() and fallback_req.exists():
        return candidate_root
    return directory


def discover_runnable_examples() -> set[Path]:
    examples: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(ROOT, topdown=True, followlinks=False):
        dirnames[:] = sorted(
            dirname
            for dirname in dirnames
            if dirname not in IGNORED_PARTS and dirname != ".agents"
        )
        directory = Path(dirpath)
        if "main.py" in filenames and "requirements.txt" in filenames:
            examples.add(normalize_runnable_example_root(directory.resolve()))
    return examples


def discover_example_roots() -> list[Path]:
    from_index = {ROOT / example.path for example in discover_examples()}
    from_runnability = discover_runnable_examples()
    return sorted(from_index | from_runnability, key=lambda path: rel(path).as_posix())


def parse_h2_sections(text: str) -> list[tuple[str, int]]:
    sections: list[tuple[str, int]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = H2_RE.match(line.strip())
        if match:
            sections.append((match.group(1), line_number))
    return sections


def has_non_empty_summary_body(text: str) -> bool:
    lines = text.splitlines()
    summary_start = None
    summary_end = len(lines)
    for index, line in enumerate(lines):
        if line.strip() == "## Summary":
            summary_start = index + 1
            continue
        if summary_start is not None and H2_RE.match(line.strip()):
            summary_end = index
            break
    if summary_start is None:
        return False
    for line in lines[summary_start:summary_end]:
        stripped = line.strip()
        if stripped and not stripped.startswith("<!--"):
            return True
    return False


def validate_agents_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    relative_path = rel(path)
    non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return [f"{relative_path}: file is empty"]
    if non_empty_lines[0] != H1_TITLE:
        errors.append(f"{relative_path}: first non-empty line must be `{H1_TITLE}`")

    h1_lines: list[tuple[str, int]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = H1_RE.match(line.strip())
        if match:
            h1_lines.append((match.group(1), line_number))
    if not h1_lines:
        errors.append(f"{relative_path}: missing top-level `{H1_TITLE}` heading")
    else:
        first_h1_text, first_h1_line = h1_lines[0]
        if first_h1_text != "AGENTS.md" or first_h1_line != 1:
            errors.append(
                f"{relative_path}: only `{H1_TITLE}` is allowed as the single H1 heading"
            )
        for heading, line_number in h1_lines[1:]:
            errors.append(
                f"{relative_path}:{line_number}: unexpected H1 heading `# {heading}`"
            )

    sections = parse_h2_sections(text)
    headings = [heading for heading, _ in sections]
    counts = Counter(headings)

    if not headings:
        errors.append(f"{relative_path}: missing all required H2 sections")
        return errors

    if headings[0] != "Summary":
        errors.append(f"{relative_path}: first H2 section must be `Summary`")
    if not has_non_empty_summary_body(text):
        errors.append(f"{relative_path}: `Summary` section must contain body text")

    for section in REQUIRED_SECTIONS:
        count = counts[section]
        if count == 0:
            errors.append(f"{relative_path}: missing required section `{section}`")
        elif count > 1:
            errors.append(f"{relative_path}: duplicate section `{section}`")

    for section in OPTIONAL_SECTIONS:
        if counts[section] > 1:
            errors.append(f"{relative_path}: duplicate section `{section}`")

    for heading, line_number in sections:
        if heading not in ALLOWED_SECTIONS:
            errors.append(
                f"{relative_path}:{line_number}: unexpected H2 section `{heading}`"
            )

    known_headings = [heading for heading in headings if heading in ALLOWED_SECTIONS]
    expected_known_headings = [
        section for section in CANONICAL_SECTION_ORDER if section in set(known_headings)
    ]
    if known_headings != expected_known_headings:
        errors.append(
            f"{relative_path}: H2 section order must follow: "
            + " -> ".join(CANONICAL_SECTION_ORDER)
        )

    return errors


def main() -> int:
    example_roots = discover_example_roots()

    missing_agents = [
        rel(example_root)
        for example_root in example_roots
        if not (example_root / "AGENTS.md").exists()
    ]

    errors: list[str] = []
    for example_root in example_roots:
        agents_path = example_root / "AGENTS.md"
        if agents_path.exists():
            errors.extend(validate_agents_file(agents_path))

    if missing_agents or errors:
        if missing_agents:
            print("Missing AGENTS.md for discovered examples:", file=sys.stderr)
            for path in missing_agents:
                print(f"- {path.as_posix()}", file=sys.stderr)
            print(file=sys.stderr)
        if errors:
            print("AGENTS.md validation errors:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Validated AGENTS.md coverage and structure for {len(example_roots)} discovered examples."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
