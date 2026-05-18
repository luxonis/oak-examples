# OAKCTL_CREATE.md

Implementation contract for `oakctl app create` when bootstrapping a new project from an example in this repository.

## Goal

A generated project should be useful outside the `oak-examples` monorepo. Agent guidance must keep links that still exist in the generated project and may keep cross-example navigation when those links are portable GitHub `main` URLs.

## Files To Include

- Copy the selected example's source files into the generated project while preserving the example's internal relative layout.
- The output directory must be new. Do not overwrite or merge into an existing directory.
- The output directory must not be inside the selected source example.
- Copy root [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md) into the generated project root.
- Use the selected example's `AGENTS.md` as the generated project's root `AGENTS.md` after applying the deterministic transforms below.
- Write the same transformed content to `CLAUDE.md` for Claude Code compatibility.
- If the example contains `oakapp.toml`, replace its `identifier` with a generated identifier derived from the output project directory name.
- Do not copy [INDEX.md](INDEX.md), [EXAMPLE_AUTHORING.md](EXAMPLE_AUTHORING.md), or this file into generated projects unless the user explicitly asks for repository-maintenance docs.

## Reference Script

[scripts/bootstrap_from_example.py](scripts/bootstrap_from_example.py) simulates this contract for internal testing and handoff. The product path should map the same behavior to `oakctl app create`. Example:

```bash
python3 scripts/bootstrap_from_example.py custom-frontend/raw-stream /tmp/raw-stream-app
```

The helper copies files and applies the documented agent-doc transform. It does not install dependencies, validate hardware compatibility, run the example, or rewrite arbitrary links beyond the rules below.

## Deterministic oakapp.toml Transform

If `oakapp.toml` exists, replace the first top-level `identifier = "..."` line with:

```toml
identifier = "com.example.<output-directory-name-slug>"
```

Use lowercase letters, digits, and `-` in the slug. If no identifier line exists, prepend one. This avoids generated projects keeping built-in/example identifiers that may block later Hub uploads.

## Deterministic AGENTS.md Transform

Apply these text transforms to the selected example's `AGENTS.md` in order:

1. Preserve `## Related Examples` when it uses portable GitHub `main` URLs.
2. Add a short `## Project Origin` section that records the source example path and tells agents to treat the generated directory as an independent project.
3. Add a short `## Start Here` section that links to copied [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md).
4. Validate that remaining relative markdown links stay inside the generated project root. Fail the bootstrap if any relative link escapes the project root.
5. Keep links to files copied into the generated project.
6. Keep absolute documentation links such as `https://docs.luxonis.com/...` and GitHub `main` links to upstream `oak-examples` references.
7. Do not invent new guidance from README content during bootstrap; only transform the selected `AGENTS.md`, add the project origin and shared knowledge link, and copy [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md).

## Expected Generated Agent Flow

The generated project should have:

- `AGENTS.md`: selected example guidance, transformed for independent project context
- `CLAUDE.md`: same transformed guidance for Claude Code
- `ESSENTIAL_KNOWLEDGE.md`: shared Luxonis/OAK vocabulary and docs links
- The example's source/runtime files

The generated `AGENTS.md` should refer to [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md). The link must resolve in the generated project root.

## Authoring Assumptions

Example authors should keep cross-example references under a section named exactly `## Related Examples`. This keeps related upstream navigation easy to preserve in generated projects.

Cross-example links should use GitHub URLs pinned to `main`, for example `https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream`. Example-specific `AGENTS.md` files should keep relative links scoped to files inside the example directory.
