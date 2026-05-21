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
from dataclasses import dataclass
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

LICENSE_FILENAMES = {
    "LICENSE",
    "LICENSE.txt",
    "LICENSE.md",
    "COPYING",
    "COPYING.txt",
    "COPYING.md",
    "NOTICE",
    "NOTICE.txt",
    "NOTICE.md",
}


@dataclass(frozen=True)
class LicenseBootstrapResult:
    """How bootstrap initialized licensing for the generated project.

    There are three mutually exclusive outcomes:
    - `preserved_top_level_files` is non-empty:
      the copied example already had project-root license files, so bootstrap
      keeps those and does not add the repo default license.
    - `copied_default_license` is true:
      the example had no project-root license file, so bootstrap copied the
      oak-examples repo root `LICENSE*` file as a starting point.
    - neither of the above:
      no project-root license file existed in the example or repo, so bootstrap
      leaves licensing for the generated project unresolved.
    """

    copied_default_license: bool
    copied_license_name: str | None
    preserved_top_level_files: tuple[str, ...]


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_PARTS for part in path.parts)


def looks_like_oak_examples(path: Path) -> bool:
    return (
        (path / "INDEX.md").is_file()
        and (path / "ESSENTIAL_KNOWLEDGE.md").is_file()
        and (path / "AGENTS.md").is_file()
    )


def clone_repo_once(target: Path, repo_url: str, branch: str) -> Path:
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
        raise RuntimeError(
            f"Could not clone oak-examples branch {branch} from {repo_url}"
        ) from exc
    if not looks_like_oak_examples(target):
        raise FileNotFoundError(
            f"Cloned branch {branch} is missing expected bootstrap files: {target}"
        )
    return target


def clone_repo(
    target: Path, repo_url: str, branch: str, replace_invalid: bool = False
) -> Path:
    target = target.expanduser().resolve()
    if target.exists():
        if any(target.iterdir()):
            if not replace_invalid:
                raise FileExistsError(
                    f"Repository path exists but is not an oak-examples checkout: {target}"
                )
            shutil.rmtree(target)
        else:
            target.rmdir()
    return clone_repo_once(target, repo_url, branch)


def find_repo(explicit_repo: Path | None, repo_url: str, branch: str) -> Path:
    if explicit_repo is not None:
        repo = explicit_repo.expanduser().resolve()
        if looks_like_oak_examples(repo):
            return repo
        if not repo.exists():
            return clone_repo(repo, repo_url, branch, replace_invalid=True)
        raise FileNotFoundError(f"Not an oak-examples checkout: {repo}")

    if os.environ.get("OAK_EXAMPLES_REPO"):
        repo = Path(os.environ["OAK_EXAMPLES_REPO"]).expanduser().resolve()
        if looks_like_oak_examples(repo):
            return repo
        raise FileNotFoundError(
            f"OAK_EXAMPLES_REPO is not an oak-examples checkout: {repo}"
        )

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
    return clone_repo(DEFAULT_REPO_CACHE, repo_url, branch, replace_invalid=True)


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


def build_licensing_section(result: LicenseBootstrapResult) -> str:
    """Describe which license bootstrap path was used for the generated project.

    The message has three modes:
    - example-specific top-level license files were preserved;
    - the repo root default license was copied in;
    - no top-level license file was copied.
    """

    if result.preserved_top_level_files:
        preserved = ", ".join(f"`{name}`" for name in result.preserved_top_level_files)
        return (
            "## Licensing\n\n"
            "This project preserved example-specific licensing files during bootstrap: "
            f"{preserved}. Do not assume the default `oak-examples` Apache-2.0 license "
            "applies uniformly. Review those files, any copied SPDX identifiers, and any "
            "vendored third-party file headers before redistributing or relicensing this project."
        )

    if result.copied_default_license and result.copied_license_name is not None:
        return (
            "## Licensing\n\n"
            f"This project starts with the `oak-examples` root `{result.copied_license_name}` "
            "copied into this directory as a default starting point. If the copied example "
            "includes files with explicit SPDX identifiers, third-party copyright/license "
            "headers, vendored dependencies, or submodules under different terms, update this "
            "project's licensing files and package metadata before publishing or relicensing it."
        )

    return (
        "## Licensing\n\n"
        "No top-level license file was copied during bootstrap. Before publishing or relicensing "
        "this project, add an explicit project license and review copied files for SPDX "
        "identifiers, third-party copyright/license headers, vendored dependencies, and submodules."
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


def transform_agents(
    markdown: str,
    example: Path,
    source_dir: Path,
    repo: Path,
    license_result: LicenseBootstrapResult,
) -> str:
    markdown = rewrite_escaping_relative_links(markdown, source_dir, repo)
    return insert_after_title(
        markdown,
        [
            build_project_origin_section(example),
            build_start_here_section(),
            build_licensing_section(license_result),
        ],
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


def top_level_license_files(directory: Path) -> tuple[str, ...]:
    """Return project-root license files from a single directory."""

    files = [
        child.name
        for child in directory.iterdir()
        if child.is_file() and child.name in LICENSE_FILENAMES
    ]
    return tuple(sorted(files))


def carry_over_root_license(repo: Path, output_dir: Path) -> LicenseBootstrapResult:
    """Initialize licensing for the generated project root."""

    example_license_files = top_level_license_files(output_dir)
    if example_license_files:
        return LicenseBootstrapResult(
            copied_default_license=False,
            copied_license_name=None,
            preserved_top_level_files=example_license_files,
        )

    # No example-level project-root license file was copied, so use the repo
    # root license as the default starting point when one exists.
    for candidate_name in ("LICENSE", "LICENSE.txt", "LICENSE.md"):
        candidate = repo / candidate_name
        if candidate.is_file():
            shutil.copy2(candidate, output_dir / candidate_name)
            return LicenseBootstrapResult(
                copied_default_license=True,
                copied_license_name=candidate_name,
                preserved_top_level_files=(),
            )

    return LicenseBootstrapResult(
        copied_default_license=False,
        copied_license_name=None,
        preserved_top_level_files=(),
    )


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
            raise ValueError(
                f"Example path must be inside oak-examples: {example_dir}"
            ) from exc
    else:
        example_ref = example
        example_dir = (repo / example).resolve()
        try:
            example_dir.relative_to(repo)
        except ValueError as exc:
            raise ValueError(
                f"Example path must stay inside oak-examples: {example}"
            ) from exc
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
        raise ValueError(
            f"Output directory must not be inside the source example: {output_dir}"
        )
    if output_dir == repo:
        raise ValueError(
            f"Output directory must not be the repository root: {output_dir}"
        )

    output_dir.mkdir(parents=True)
    copy_example(example_dir, output_dir)
    # License detection runs after the example copy so `output_dir` represents
    # the generated project's root, including any example-provided license files.
    license_result = carry_over_root_license(repo, output_dir)

    transformed_agents = transform_agents(
        (example_dir / "AGENTS.md").read_text(encoding="utf-8"),
        example_ref,
        example_dir,
        repo,
        license_result,
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
    parser.add_argument(
        "example",
        nargs="?",
        type=Path,
        help="Example path relative to oak-examples root.",
    )
    parser.add_argument(
        "output", nargs="?", type=Path, help="New output project directory."
    )
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
