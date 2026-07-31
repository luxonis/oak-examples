---
name: bootstrap-example
description: Bootstrap an OAK project from an example in oak-examples. Use when 
  the user wants to copy, extract, start, scaffold, or create a host-script or 
  standalone app/project from an existing repository example, especially for 
  oakctl app create handoff or customization.
compatibility: Requires Python 3 and git. Uses an accessible 
  luxonis/oak-examples checkout or shallow-clones the public repository when 
  needed.
---

# Bootstrap Example

Use this skill when the user wants to copy, extract, bootstrap, or start an OAK project from an example in `oak-examples`.

## Workflow

1. Clarify the target app before choosing an example: task, required hardware, host-script vs standalone mode, UI needs, model/inference needs, streaming/output needs, and whether the user wants the smallest scaffold or closest production-shaped app.
2. Before selecting an example, run the helper with `--print-selection-context` to acquire the local checkout path, business-use-case selection guide, and generated index. This command uses the current checkout when available; otherwise it shallow-clones `https://github.com/luxonis/oak-examples.git` into a local cache with `--depth 1` from the default branch `main`:

```bash
python3 scripts/bootstrap_from_example.py --print-selection-context
```

3. Read the printed `selection_guide:` path before the `index:` path. Choose by business outcome, hardware, application shape, state, and output requirements, then use the index to find alternatives with the same modality or execution shape.
4. Resolve guide and index links relative to the printed `repo:` path, then read the candidate `AGENTS.md` files before choosing. Prefer the simplest architecture that satisfies the task, hardware, mode, UI, and output requirements.
5. Choose a new output directory for the generated project. For installable-skill usage, default to a new subdirectory under the user's current working directory, such as `./raw-stream-app`; do not write directly into the current directory. The output directory must not already exist.
6. Run this skill's bundled helper.

```bash
python3 scripts/bootstrap_from_example.py <example-path> ./<new-project-dir>
```

7. Use `--repo /path/to/oak-examples` when the user already has a preferred checkout, or when you need to clone into a specific location.

```bash
python3 scripts/bootstrap_from_example.py --repo /tmp/oak-examples <example-path> ./<new-project-dir>
```

08. Inspect the generated project's `AGENTS.md`, `CLAUDE.md`, and `LICENSE`; confirm they link to `ESSENTIAL_KNOWLEDGE.md`, any `## Related Examples` links use GitHub `main` URLs, and whether bootstrap copied the repo root license or preserved example-specific license files.
09. If the copied example includes its own top-level license files or explicit third-party headers, keep those terms instead of assuming Apache-2.0 applies uniformly.
10. Tell the user where the project was created, that `oakapp.toml` identifier was changed if present, and that dependencies, hardware compatibility, runtime validation, and final license review still need to be handled separately.

## Example

```bash
python3 scripts/bootstrap_from_example.py custom-frontend/raw-stream ./raw-stream-app
```

## Available Scripts

- `scripts/bootstrap_from_example.py`: finds or shallow-clones `oak-examples`, prints the local `EXAMPLE_SELECTION.md` and `INDEX.md` paths with `--print-selection-context`, copies an example into a new project, writes `AGENTS.md` and `CLAUDE.md`, copies `ESSENTIAL_KNOWLEDGE.md`, carries over the repo root `LICENSE` when the example does not already provide a top-level license file, converts cross-example links to GitHub `main` URLs, and rewrites `oakapp.toml` identifiers.

## Selection Checklist

- `Task:` detection, depth, streaming, frontend, ROS, C++, calibration, measurement, or integration.
- `Hardware:` RVC2/RVC4, stereo, ToF, thermal, IMU, autofocus, or multi-device requirements.
- `Mode:` host script, standalone OAK App, or both.
- `Shape:` minimal scaffold, packaged app, frontend/backend app, ROS workspace, C++ app, or evaluation tool.
- `Processing:` single or staged inference, tracking, tiling, calibration, fusion, or host processing.
- `Inputs/outputs:` camera/media input, model choice, visualization, service/API, stream protocol, or dataset/export target.

## Safety

- Never overwrite an existing output directory. Ask the user for a new path instead.
- Do not edit the source example while bootstrapping unless the user separately asked for repository changes.
- Do not claim the generated project is runnable until dependencies and hardware requirements are checked.
