---
name: bootstrap-example
description: Bootstrap an OAK project from an example in oak-examples. Use when the user wants to copy, extract, start, scaffold, or create a host-script or standalone app/project from an existing repository example, especially for oakctl app create handoff or customization.
compatibility: Requires Python 3 and git. Uses an accessible luxonis/oak-examples checkout or shallow-clones the public repository when needed.
---

# Bootstrap Example

Use this skill when the user wants to copy, extract, bootstrap, or start an OAK project from an example in `oak-examples`.

## Workflow

1. Clarify the target app before choosing an example: task, required hardware, host-script vs standalone mode, UI needs, model/inference needs, streaming/output needs, and whether the user wants the smallest scaffold or closest production-shaped app.
2. Before selecting an example, run the helper with `--print-index` to acquire the local checkout path and `INDEX.md` path. This command uses the current checkout when available; otherwise it shallow-clones `https://github.com/luxonis/oak-examples.git` into a local cache with `--depth 1`:

```bash
python3 scripts/bootstrap_from_example.py --print-index
```

3. Read the printed `index:` path and identify candidate examples. The index links are relative to the printed `repo:` path; resolve those paths locally and read the candidate `AGENTS.md` files before choosing. Prefer the closest task and hardware match first, then the closest execution shape.
4. Choose a new output directory for the generated project. For installable-skill usage, default to a new subdirectory under the user's current working directory, such as `./raw-stream-app`; do not write directly into the current directory. The output directory must not already exist.
5. Run this skill's bundled helper.

```bash
python3 scripts/bootstrap_from_example.py <example-path> ./<new-project-dir>
```

6. Use `--repo /path/to/oak-examples` when the user already has a preferred checkout, or when you need to clone into a specific location.

```bash
python3 scripts/bootstrap_from_example.py --repo /tmp/oak-examples <example-path> ./<new-project-dir>
```

7. Inspect the generated project's `AGENTS.md` and `CLAUDE.md`; confirm they link to `ESSENTIAL_KNOWLEDGE.md` and any `## Related Examples` links use GitHub `main` URLs.
8. Tell the user where the project was created, that `oakapp.toml` identifier was changed if present, and that dependencies, hardware compatibility, and runtime validation still need to be handled separately.

## Example

```bash
python3 scripts/bootstrap_from_example.py custom-frontend/raw-stream ./raw-stream-app
```

## Available Scripts

- `scripts/bootstrap_from_example.py`: finds or shallow-clones `oak-examples`, prints the local `INDEX.md` path with `--print-index`, copies an example into a new project, writes `AGENTS.md` and `CLAUDE.md`, copies `ESSENTIAL_KNOWLEDGE.md`, converts cross-example links to GitHub `main` URLs, and rewrites `oakapp.toml` identifiers.

## Selection Checklist

- `Task:` detection, depth, streaming, frontend, ROS, C++, calibration, measurement, or integration.
- `Hardware:` RVC2/RVC4, stereo, ToF, thermal, IMU, autofocus, or multi-device requirements.
- `Mode:` host script, standalone OAK App, or both.
- `Shape:` minimal scaffold, packaged app, frontend/backend app, ROS workspace, C++ app, or evaluation tool.
- `Inputs/outputs:` camera/media input, model choice, visualization, service/API, stream protocol, or dataset/export target.

## Safety

- Never overwrite an existing output directory. Ask the user for a new path instead.
- Do not edit the source example while bootstrapping unless the user separately asked for repository changes.
- Do not claim the generated project is runnable until dependencies and hardware requirements are checked.
