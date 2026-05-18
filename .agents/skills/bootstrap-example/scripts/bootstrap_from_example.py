#!/usr/bin/env python3
"""Bootstrap an OAK project from an oak-examples example.

This helper is intentionally self-contained so the bootstrap-example skill can be
installed outside the oak-examples repository. Pass --repo when the current
working directory is not inside an oak-examples checkout.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO_URL = "https://github.com/luxonis/oak-examples.git"
DEFAULT_REPO_BRANCH = "main"
DEFAULT_REPO_CACHE = Path.home() / ".cache" / "luxonis" / "oak-examples"
GITHUB_MAIN_BASE_URL = "https://github.com/luxonis/oak-examples"
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


def looks_like_oak_examples(path: Path) -> bool:
    return (
        (path / "INDEX.md").is_file()
        and (path / "ESSENTIAL_KNOWLEDGE.md").is_file()
        and (path / "AGENTS.md").is_file()
    )


def clone_repo(target: Path, repo_url: str, branch: str) -> Path:
    target = target.expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(
            f"Repository path exists but is not an oak-examples checkout: {target}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        branch,
        repo_url,
        str(target),
    ]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("git is required to clone oak-examples") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Could not clone oak-examples from {repo_url}") from exc
    if not looks_like_oak_examples(target):
        raise FileNotFoundError(f"Cloned repository is missing expected files: {target}")
    return target


def find_repo(explicit_repo: Path | None, repo_url: str, branch: str) -> Path:
    if explicit_repo is not None:
        repo = explicit_repo.expanduser().resolve()
        if looks_like_oak_examples(repo):
            return repo
        if not repo.exists():
            return clone_repo(repo, repo_url, branch)
        raise FileNotFoundError(f"Not an oak-examples checkout: {repo}")

    if os.environ.get("OAK_EXAMPLES_REPO"):
        repo = Path(os.environ["OAK_EXAMPLES_REPO"]).expanduser().resolve()
        if looks_like_oak_examples(repo):
            return repo
        raise FileNotFoundError(f"OAK_EXAMPLES_REPO is not an oak-examples checkout: {repo}")

    candidates = [Path.cwd().resolve()]
    candidates.extend(Path.cwd().resolve().parents)

    # When this helper lives in .agents/skills/bootstrap-example inside the repo.
    script_path = Path(__file__).resolve()
    if len(script_path.parents) > 4:
        candidates.append(script_path.parents[4])

    for candidate in candidates:
        repo = candidate.expanduser().resolve()
        if looks_like_oak_examples(repo):
            return repo

    if looks_like_oak_examples(DEFAULT_REPO_CACHE):
        return DEFAULT_REPO_CACHE
    return clone_repo(DEFAULT_REPO_CACHE, repo_url, branch)


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


def rewrite_escaping_relative_links(markdown: str, source_dir: Path, repo: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        href = match.group(1)
        href_path, separator, fragment = href.partition("#")
        if not href_path or href.startswith(("http://", "https://", "#", "mailto:")):
            return match.group(0)

        target = (source_dir / href_path).resolve()
        try:
            target.relative_to(source_dir)
            return match.group(0)
        except ValueError:
            pass

        try:
            repo_relative = target.relative_to(repo)
        except ValueError:
            return match.group(0)

        kind = "tree" if target.is_dir() else "blob"
        url = f"{GITHUB_MAIN_BASE_URL}/{kind}/main/{repo_relative.as_posix()}"
        if separator:
            url += f"#{fragment}"

        label_match = re.match(r"(?<!!)\[([^\]]+)\]", match.group(0))
        label = label_match.group(1) if label_match else repo_relative.as_posix()
        if label.startswith((".", "/")):
            label = repo_relative.as_posix()
        return f"[{label}]({url})"

    return MARKDOWN_LINK_RE.sub(replace, markdown)


def transform_agents(markdown: str, example: Path, source_dir: Path, repo: Path) -> str:
    markdown = rewrite_escaping_relative_links(markdown, source_dir, repo)
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


def resolve_example(repo: Path, example: Path) -> tuple[Path, Path]:
    if example.is_absolute():
        example_dir = example.resolve()
        try:
            example_ref = example_dir.relative_to(repo)
        except ValueError as exc:
            raise ValueError(f"Example path must be inside oak-examples: {example_dir}") from exc
    else:
        example_ref = example
        example_dir = (repo / example).resolve()
        try:
            example_dir.relative_to(repo)
        except ValueError as exc:
            raise ValueError(f"Example path must stay inside oak-examples: {example}") from exc
    return example_dir, example_ref


def bootstrap(repo: Path, example: Path, output: Path) -> None:
    example_dir, example_ref = resolve_example(repo, example)
    output_dir = output.expanduser().resolve()
    essential_knowledge = repo / "ESSENTIAL_KNOWLEDGE.md"

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
    if output_dir == repo:
        raise ValueError(f"Output directory must not be the repository root: {output_dir}")

    output_dir.mkdir(parents=True)
    copy_example(example_dir, output_dir)

    transformed_agents = transform_agents(
        (example_dir / "AGENTS.md").read_text(encoding="utf-8"),
        example_ref,
        example_dir,
        repo,
    )
    validate_standalone_markdown_links(transformed_agents)
    (output_dir / "AGENTS.md").write_text(transformed_agents, encoding="utf-8")
    (output_dir / "CLAUDE.md").write_text(transformed_agents, encoding="utf-8")
    shutil.copy2(essential_knowledge, output_dir / "ESSENTIAL_KNOWLEDGE.md")
    update_oakapp_identifier(output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap an OAK project from an oak-examples example."
    )
    parser.add_argument("example", nargs="?", type=Path, help="Example path relative to oak-examples root.")
    parser.add_argument("output", nargs="?", type=Path, help="New output project directory.")
    parser.add_argument(
        "--repo",
        type=Path,
        help="Path to a luxonis/oak-examples checkout. If missing, the helper clones a shallow checkout there.",
    )
    parser.add_argument(
        "--repo-url",
        default=DEFAULT_REPO_URL,
        help=f"Repository URL to clone when no checkout is found. Default: {DEFAULT_REPO_URL}",
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_REPO_BRANCH,
        help=f"Repository branch to shallow clone. Default: {DEFAULT_REPO_BRANCH}",
    )
    parser.add_argument(
        "--print-index",
        action="store_true",
        help="Find or shallow-clone oak-examples and print the local INDEX.md path for example selection.",
    )
    args = parser.parse_args()

    try:
        repo = find_repo(args.repo, args.repo_url, args.branch)
        if args.print_index:
            print(f"repo: {repo}")
            print(f"index: {repo / 'INDEX.md'}")
            return 0
        if args.example is None or args.output is None:
            parser.error("example and output are required unless --print-index is used")
        bootstrap(repo, args.example, args.output)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
