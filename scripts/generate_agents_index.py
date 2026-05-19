#!/usr/bin/env python3
"""Generate the agent-facing example catalog.

The generated index is intentionally lightweight: it discovers runnable example
roots from the repository layout and pulls short summaries from example
AGENTS.md files when available, falling back to README files while coverage is
incomplete.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "INDEX.md"
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

CATEGORY_ORDER = [
    "apps",
    "camera-controls",
    "cpp",
    "custom-frontend",
    "depth-measurement",
    "integrations",
    "neural-networks",
    "streaming",
    "tutorials",
]

CATEGORY_TITLES = {
    "apps": "Apps",
    "camera-controls": "Camera Controls",
    "cpp": "C++ Examples",
    "custom-frontend": "Custom Frontend",
    "depth-measurement": "Depth Measurement",
    "integrations": "Integrations",
    "neural-networks": "Neural Networks",
    "streaming": "Streaming",
    "tutorials": "Tutorials",
}

TAG_PATTERNS = [
    (r"\b3d\b", "3d"),
    (r"\bage[- ]gender\b", "age-gender"),
    (r"\bbarcode\b", "barcode"),
    (r"\bblur\b", "blur"),
    (r"\bcalibration\b", "calibration"),
    (r"\bclassification\b", "classification"),
    (r"\bcount(?:ing)?\b", "counting"),
    (r"\bdepth\b", "depth"),
    (r"\bdetect(?:ion|ions)?\b", "detections"),
    (r"\bdisparity\b", "disparity"),
    (r"\bface\b", "face"),
    (r"\bfrontend\b", "frontend"),
    (r"\bhost\b", "host-processing"),
    (r"\bimu\b", "imu"),
    (r"\bmqtt\b", "mqtt"),
    (r"\bmulti[- ]device\b", "multi-device"),
    (r"\bocr\b", "ocr"),
    (r"\bopen[- ]vocab(?:ulary)?\b", "open-vocab"),
    (r"\bpoint[- ]?cloud\b", "pointcloud"),
    (r"\bpose\b", "pose"),
    (r"\bqr\b", "qr"),
    (r"\bros\b", "ros"),
    (r"\brtsp\b", "rtsp"),
    (r"\bsegmentation\b", "segmentation"),
    (r"\bspatial\b", "spatial"),
    (r"\bstereo\b", "stereo"),
    (r"\bstream(?:ing)?\b", "streaming"),
    (r"\bthermal\b", "thermal"),
    (r"\btof\b", "tof"),
    (r"\btrack(?:ing)?\b", "tracking"),
    (r"\buvc\b", "uvc"),
    (r"\bwebrtc\b", "webrtc"),
    (r"\byolo\b", "yolo"),
]


@dataclass(frozen=True)
class Example:
    path: Path
    title: str
    summary: str
    shape: str
    mode: str
    tags: tuple[str, ...]
    has_agents: bool


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_PARTS for part in path.parts)


def rel(path: Path) -> Path:
    return path.relative_to(ROOT)


def validate_agents_links() -> list[str]:
    errors: list[str] = []
    for path in sorted(ROOT.rglob("AGENTS.md")):
        relative_path = rel(path)
        if is_ignored(relative_path) or relative_path.parts[:1] == (".agents",):
            continue
        base = path.parent.resolve()
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1
        ):
            for match in MARKDOWN_LINK_RE.finditer(line):
                href = match.group(1).split("#", 1)[0].strip()
                if not href or href.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                target = (base / href).resolve()
                try:
                    target.relative_to(base)
                except ValueError:
                    errors.append(f"{relative_path}:{line_number}: {match.group(1)}")
    return errors


def clean_inline(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("|", " ").replace("\\", "")
    return re.sub(r"\s+", " ", text).strip(" -")


def truncate_summary(summary: str, limit: int = 220) -> str:
    if len(summary) <= limit:
        return summary
    truncated = summary[: limit + 1]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated.rstrip(".,;:- ") + "..."


def read_title_and_summary(markdown: Path, fallback: Path) -> tuple[str, str]:
    title = fallback.name.replace("-", " ").replace("_", " ").title()
    paragraphs: list[str] = []
    current: list[str] = []
    in_code = False
    in_summary = False
    found_summary = False

    def flush_paragraph() -> None:
        if current:
            paragraphs.append(clean_inline(" ".join(current)))
            current.clear()

    for raw in markdown.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or line.startswith("<!--"):
            continue
        if line.startswith("#"):
            flush_paragraph()
            heading = clean_inline(line.lstrip("#").strip())
            if heading and not in_summary:
                title = heading
            if heading.lower() == "summary":
                in_summary = True
                found_summary = True
                continue
            if found_summary:
                break
            continue
        if not line:
            flush_paragraph()
            if found_summary and paragraphs:
                break
            continue
        if line.startswith(("[!", "<img", "<p", "</p", "<div", "</div")):
            continue
        if line.startswith(("- ", "* ", "|")):
            continue
        if in_summary or not found_summary:
            current.append(line)
    flush_paragraph()

    summary = " ".join(p for p in paragraphs if p)
    if not summary:
        summary = f"Runnable/reference example under `{fallback.as_posix()}`."
    return title, truncate_summary(summary)


def infer_shape(path: Path) -> str:
    if (path / "frontend" / "package.json").exists() or (
        path / "frontend" / "src"
    ).exists():
        return "frontend"
    if "ros" in path.parts or any(
        (path / child).exists() for child in ("package.xml", "colcon.meta")
    ):
        return "ros"
    if (path / "CMakeLists.txt").exists() or (path / "src" / "main.cpp").exists():
        return "cpp"
    if "host_eval" in path.parts or "eval" in path.parts:
        return "eval"
    if (path / "oakapp.toml").exists():
        return "script+standalone"
    return "script"


def infer_mode(path: Path, shape: str) -> str:
    text = " ".join(part.lower() for part in path.parts)
    if "multiple-devices" in text or "multi-device" in text:
        return "multi-device host"
    if shape in {"frontend", "ros"} and (path / "oakapp.toml").exists():
        readme = (
            (path / "README.md").read_text(encoding="utf-8", errors="ignore").lower()
        )
        if "standalone" in readme and "peripheral" not in readme:
            return "standalone-only"
    if (path / "oakapp.toml").exists():
        return "host + standalone"
    return "host"


def infer_tags(path: Path, title: str, summary: str, shape: str) -> tuple[str, ...]:
    haystack = " ".join([path.as_posix(), title, summary]).lower()
    tags: list[str] = []
    if shape not in {"script", "script+standalone"}:
        tags.append(shape)
    for pattern, tag in TAG_PATTERNS:
        if re.search(pattern, haystack) and tag not in tags:
            tags.append(tag)
    if not tags:
        tags.append("reference")
    return tuple(tags[:6])


def iter_readmes() -> list[Path]:
    readmes: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT, topdown=True, followlinks=False):
        dirnames[:] = sorted(
            dirname for dirname in dirnames if dirname not in IGNORED_PARTS
        )
        if "README.md" in filenames:
            readmes.append(Path(dirpath) / "README.md")
    return readmes


def candidate_example_dirs() -> list[Path]:
    dirs: set[Path] = set()
    for readme in iter_readmes():
        directory = readme.parent
        relative_directory = rel(directory)
        if (
            directory == ROOT
            or directory.parent == ROOT
            or is_ignored(relative_directory)
        ):
            continue
        direct_markers = [
            directory / "main.py",
            directory / "oakapp.toml",
            directory / "CMakeLists.txt",
            directory / "src" / "main.cpp",
            directory / "host.py",
            directory / "oak.py",
        ]
        frontend_backend = (directory / "frontend" / "package.json").exists() and (
            directory / "backend" / "src" / "main.py"
        ).exists()
        ros_workspace = (
            "ros" in relative_directory.parts and (directory / "oakapp.toml").exists()
        )
        if (
            any(marker.exists() for marker in direct_markers)
            or frontend_backend
            or ros_workspace
        ):
            dirs.add(directory)
    return sorted(dirs, key=lambda p: rel(p).as_posix())


def discover_examples() -> list[Example]:
    examples: list[Example] = []
    for directory in candidate_example_dirs():
        guide = (
            directory / "AGENTS.md"
            if (directory / "AGENTS.md").exists()
            else directory / "README.md"
        )
        title, summary = read_title_and_summary(guide, rel(directory))
        shape = infer_shape(directory)
        examples.append(
            Example(
                path=rel(directory),
                title=title,
                summary=summary,
                shape=shape,
                mode=infer_mode(directory, shape),
                tags=infer_tags(rel(directory), title, summary, shape),
                has_agents=(directory / "AGENTS.md").exists(),
            )
        )
    return examples


def category_key(example: Example) -> str:
    return example.path.parts[0]


def category_heading(category: str) -> str:
    return CATEGORY_TITLES.get(category, category.replace("-", " ").title())


def render_index(examples: list[Example]) -> str:
    categories = sorted(
        {category_key(example) for example in examples},
        key=lambda c: (CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99, c),
    )
    lines = [
        "# INDEX.md",
        "",
        "Agent-focused catalog of runnable/reference examples in this repository.",
        "",
        "## How To Use This Index",
        "",
        "- Match the user task to the summary and `Tags`.",
        "- Use `Shape` to filter for script, standalone-packaged, frontend/backend, ROS, C++, or evaluation references.",
        "",
        "For shared vocabulary such as shapes, modes, platforms, and runtime files, read [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md).",
        "",
        "## Examples",
        "",
    ]
    by_category: dict[str, list[Example]] = {category: [] for category in categories}
    for example in examples:
        by_category[category_key(example)].append(example)
    for category in categories:
        lines.extend([f"### {category_heading(category)}", ""])
        for example in by_category[category]:
            guide_name = "AGENTS.md" if example.has_agents else "README.md"
            guide_path = example.path / guide_name
            tags = ", ".join(f"`{tag}`" for tag in example.tags)
            lines.append(
                f"- [{example.path.as_posix()}]({guide_path.as_posix()}): {example.summary} "
                f"Shape: `{example.shape}`. Mode: `{example.mode}`. Guide: `{guide_name}`. Tags: {tags}."
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate INDEX.md for agent-facing example navigation."
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail if INDEX.md is not up to date."
    )
    args = parser.parse_args()

    generated = render_index(discover_examples())
    if args.check:
        link_errors = validate_agents_links()
        if link_errors:
            print(
                "AGENTS.md contains relative links that escape the example directory. "
                "Use GitHub main URLs for cross-example links:",
                file=sys.stderr,
            )
            print("\n".join(link_errors), file=sys.stderr)
            return 1
        current = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
        if current != generated:
            print(
                "INDEX.md is out of date. Run: python3 scripts/generate_agents_index.py",
                file=sys.stderr,
            )
            return 1
        return 0
    INDEX.write_text(generated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
