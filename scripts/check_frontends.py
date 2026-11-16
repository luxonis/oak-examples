#!/usr/bin/env python3
"""Check that the custom React frontends share one page shell and the Luxonis design rules.

Every example frontend (a `frontend/` directory that depends on
`@luxonis/depthai-viewer-common`) must:

- carry byte-identical copies of the shared shell files,
- render its page through `AppShell`, with the same title as `index.html`,
- take colors and typography from `@luxonis/ui-components` instead of hard-coding them.

Run `python3 scripts/check_frontends.py --fix` to copy the shared files from their reference
frontends into every other frontend. See docs/design.md for the design decisions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_SPECIFIC_CSS_MARKER = "/* App-specific styles */"


@dataclass(frozen=True)
class SharedFile:
    path: str
    reference: str
    required: bool


SHARED_FILES = [
    SharedFile("src/AppShell.tsx", "custom-frontend/raw-stream/frontend", True),
    SharedFile("src/index.css", "custom-frontend/raw-stream/frontend", True),
    SharedFile("src/Notifications.tsx", "apps/dino-tracking/frontend", False),
    SharedFile("vite.config.ts", "custom-frontend/raw-stream/frontend", True),
]


@dataclass(frozen=True)
class Rule:
    name: str
    suffixes: tuple[str, ...]
    pattern: re.Pattern[str]
    message: str


SOURCE = (".ts", ".tsx", ".css")
TAILWIND_PALETTE = (
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|"
    "sky|blue|indigo|violet|purple|fuchsia|pink|rose"
)
RULES = [
    Rule(
        "hex-color",
        SOURCE,
        re.compile(
            r"(?<=[\s:'\"`(,])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b"
        ),
        "hard-coded hex color; use a --lux-* variable or a component intent",
    ),
    Rule(
        "color-function",
        SOURCE,
        re.compile(r"\b(?:rgba?|hsla?)\("),
        "hard-coded color function; use a --lux-* variable or a component intent",
    ),
    Rule(
        "tailwind-palette",
        (".tsx",),
        re.compile(
            rf"(?<![\w-])(?:text|bg|border|ring|fill|stroke|outline|divide)-"
            rf"(?:(?:{TAILWIND_PALETTE})-\d{{2,3}}|white|black)(?![\w-])"
        ),
        "Tailwind palette color; use a component intent or a semantic token",
    ),
    Rule(
        "typography-utility",
        (".tsx",),
        re.compile(
            r"(?<![\w-])(?:[\w-]+:)*(?:text-(?:xs|sm|base|lg|[2-9]?xl|\[[^\]]+\])|"
            r"font-(?:thin|extralight|light|normal|medium|semibold|bold|extrabold|black))(?![\w-])"
        ),
        "typography utility; use PageTitle, SubHeader, NormalText, Label or SubLabel",
    ),
    Rule(
        "page-heading",
        (".tsx",),
        re.compile(r"<h1\b"),
        "page title outside AppShell; pass the title to AppShell",
    ),
    Rule(
        "native-control",
        (".tsx",),
        re.compile(r"<(?:select|details|meter|progress)\b"),
        "native control; use Select, Accordion or Progress from @luxonis/ui-components",
    ),
    Rule(
        "middle-dot",
        SOURCE + (".html",),
        re.compile("·"),
        "middle dot separator; use words or structure instead",
    ),
]

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
FAVICON = '<link rel="icon" href="data:," />'
APP_SHELL_RE = re.compile(r"<AppShell\b")
APP_SHELL_TITLE_RE = re.compile(
    r"<AppShell\b.*?\btitle=(?:\"([^\"]*)\"|\{'([^']*)'\}|(\S+))", re.S
)
TAILWIND_IMPORTS = ('@import "tailwindcss";', "@source ")


def discover_frontends() -> list[Path]:
    frontends = []
    for package_json in sorted(ROOT.glob("**/frontend/package.json")):
        if "node_modules" in package_json.parts:
            continue
        dependencies = json.loads(package_json.read_text()).get("dependencies", {})
        if "@luxonis/depthai-viewer-common" in dependencies:
            frontends.append(package_json.parent)
    return frontends


def expected_content(shared: SharedFile, target: Path) -> str:
    reference = (ROOT / shared.reference / shared.path).read_text()
    if shared.path != "src/index.css" or not target.exists():
        return reference
    current = target.read_text()
    if APP_SPECIFIC_CSS_MARKER in current:
        return reference + "\n" + current[current.index(APP_SPECIFIC_CSS_MARKER) :]
    app_css = "\n".join(
        line
        for line in current.removeprefix(reference).splitlines()
        if not line.startswith(TAILWIND_IMPORTS)
    ).strip()
    if not app_css:
        return reference
    return f"{reference}\n{APP_SPECIFIC_CSS_MARKER}\n{app_css}\n"


def check_shared(frontend: Path, fix: bool) -> list[str]:
    problems = []
    for shared in SHARED_FILES:
        target = frontend / shared.path
        if not target.exists() and not shared.required:
            continue
        expected = expected_content(shared, target)
        if target.exists() and target.read_text() == expected:
            continue
        if fix:
            target.write_text(expected)
            continue
        state = "missing" if not target.exists() else "differs from"
        problems.append(
            f"{target.relative_to(ROOT)}: {state} {shared.reference}/{shared.path}"
        )
    return problems


def check_rules(frontend: Path) -> list[str]:
    problems = []
    files = sorted(frontend.glob("src/**/*")) + [frontend / "index.html"]
    for path in files:
        if not path.is_file() or path.name.endswith(".d.ts"):
            continue
        for rule in RULES:
            if path.suffix not in rule.suffixes:
                continue
            if rule.name == "page-heading" and path.name == "AppShell.tsx":
                continue
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if rule.pattern.search(line):
                    problems.append(
                        f"{path.relative_to(ROOT)}:{number}: {rule.name}: {rule.message}"
                    )
    return problems


def check_page(frontend: Path) -> list[str]:
    problems = []
    index_html = (frontend / "index.html").read_text()
    if FAVICON not in index_html:
        problems.append(
            f"{(frontend / 'index.html').relative_to(ROOT)}: favicon must be {FAVICON}"
        )
    html_title = TITLE_RE.search(index_html)
    usages = [
        path
        for path in sorted(frontend.glob("src/**/*.tsx"))
        for _ in APP_SHELL_RE.finditer(path.read_text())
    ]
    if len(usages) != 1:
        problems.append(
            f"{frontend.relative_to(ROOT)}: expected one <AppShell>, found {len(usages)}"
        )
        return problems
    match = APP_SHELL_TITLE_RE.search(usages[0].read_text())
    shell_title = match and (match.group(1) or match.group(2))
    if not shell_title:
        problems.append(
            f"{usages[0].relative_to(ROOT)}: pass AppShell a string literal title"
        )
    elif not html_title or html_title.group(1).strip() != shell_title:
        problems.append(
            f"{(frontend / 'index.html').relative_to(ROOT)}: <title> must match AppShell title {shell_title!r}"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fix", action="store_true", help="copy the shared files into every frontend"
    )
    args = parser.parse_args()

    frontends = discover_frontends()
    problems = []
    for frontend in frontends:
        problems += check_shared(frontend, args.fix)
        problems += check_rules(frontend)
        problems += check_page(frontend)

    for problem in problems:
        print(problem)
    print(f"Checked {len(frontends)} frontends: {len(problems)} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
