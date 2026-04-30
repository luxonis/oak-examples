# Bootstrap Example

Use this skill when the user wants to copy, extract, bootstrap, or start a standalone project from an example in `oak-examples`.

## Workflow

1. Use `<repo-root>/INDEX.md` to identify the source example.
2. Choose an output directory outside the source example.
3. Run the helper from the repository root:

```bash
python3 scripts/bootstrap_from_example.py <example-path> <output-dir>
```

4. Use `--force` only when the user explicitly wants to overwrite a non-empty output directory.
5. Inspect the generated project's `AGENTS.md` and confirm it no longer contains `## Related Examples`.
6. Tell the user where the project was created, that `oakapp.toml` identifier was changed if present, and that dependencies, hardware compatibility, and runtime validation still need to be handled separately.

## Example

```bash
python3 scripts/bootstrap_from_example.py custom-frontend/raw-stream /tmp/raw-stream-app
```

## Safety

- Do not overwrite a non-empty output directory unless the user requested it or approved `--force`.
- Do not edit the source example while bootstrapping unless the user separately asked for repository changes.
- Do not claim the generated project is runnable until dependencies and hardware requirements are checked.
