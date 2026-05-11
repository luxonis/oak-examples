# OAKCTL_CREATE.md

Implementation contract for `oakctl app create` when bootstrapping a new project from an example in this repository.

## Goal

A generated project should be useful outside the `oak-examples` monorepo. Agent guidance must keep links that still exist in the generated project and remove links that only make sense inside the monorepo.

## Files To Include

- Copy the selected example's source files into the generated project while preserving the example's internal relative layout.
- Copy root [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md) into the generated project root.
- Use the selected example's `AGENTS.md` as the generated project's root `AGENTS.md` after applying the deterministic transforms below.
- If the example contains `oakapp.toml`, replace its `identifier` with a generated identifier derived from the output project directory name.
- Do not copy [INDEX.md](INDEX.md), [EXAMPLE_AUTHORING.md](EXAMPLE_AUTHORING.md), or this file into generated projects unless the user explicitly asks for repository-maintenance docs.

## Reference Script

[scripts/bootstrap_from_example.py](scripts/bootstrap_from_example.py) simulates this contract for internal testing and handoff. Example:

```bash
python3 scripts/bootstrap_from_example.py custom-frontend/raw-stream /tmp/raw-stream-app --force
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

1. Remove the entire `## Related Examples` section, including its monorepo-only note, from the heading line through the line before the next `## ` heading or end of file.
2. If the generated project does not preserve the selected example's internal relative layout, rewrite or remove any remaining relative markdown links that no longer resolve.
3. Keep links to files copied into the generated project.
4. Keep absolute documentation links such as `https://docs.luxonis.com/...`.
5. Do not invent new guidance from README content during bootstrap; only transform the selected `AGENTS.md` and copy [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md).

## Expected Generated Agent Flow

The generated project should have:

- `AGENTS.md`: selected example guidance, transformed for standalone project context
- `ESSENTIAL_KNOWLEDGE.md`: shared Luxonis/OAK vocabulary and docs links
- The example's source/runtime files

The generated `AGENTS.md` may still refer to [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md) if the bootstrapper injects that reference. If it does, the link must resolve in the generated project root.

## Authoring Assumptions

Example authors should keep monorepo-only cross-links under a section named exactly `## Related Examples`. This makes the bootstrap transform simple and safe.

Example-specific `AGENTS.md` files should keep local links scoped to files inside the example directory except in `## Related Examples`.
