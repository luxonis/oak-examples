---
name: bootstrap-example
description: Bootstrap an OAK project from an example in oak-examples. Use when the user wants to copy, extract, start, scaffold, or create a host-script or standalone app/project from an existing repository example, especially for oakctl app create handoff or customization.
compatibility: Requires Python 3 and an accessible luxonis/oak-examples checkout; can clone the public repository when needed.
---

# Bootstrap Example

Use this skill when the user wants to copy, extract, bootstrap, or start an OAK project from an example in `oak-examples`.

## Workflow

1. Clarify the target app before choosing an example: task, required hardware, host-script vs standalone mode, UI needs, model/inference needs, streaming/output needs, and whether the user wants the smallest scaffold or closest production-shaped app.
2. Use `<repo-root>/INDEX.md` to identify the source example. Prefer the closest task and hardware match first, then the closest execution shape.
3. Choose a new output directory outside the source example. It must not already exist.
4. If this skill is installed outside an `oak-examples` checkout, locate or clone the repository first:

```bash
git clone https://github.com/luxonis/oak-examples.git /tmp/oak-examples
```

5. Run this skill's bundled helper and pass the repo path:

```bash
python3 scripts/bootstrap_from_example.py --repo /tmp/oak-examples <example-path> <output-dir>
```

6. Inspect the generated project's `AGENTS.md` and `CLAUDE.md`; confirm they link to `ESSENTIAL_KNOWLEDGE.md` and any `## Related Examples` links use GitHub `main` URLs.
6. Tell the user where the project was created, that `oakapp.toml` identifier was changed if present, and that dependencies, hardware compatibility, and runtime validation still need to be handled separately.

## Example

```bash
python3 scripts/bootstrap_from_example.py --repo /tmp/oak-examples custom-frontend/raw-stream /tmp/raw-stream-app
```

## Available Scripts

- `scripts/bootstrap_from_example.py`: copies an example into a new project, writes `AGENTS.md` and `CLAUDE.md`, copies `ESSENTIAL_KNOWLEDGE.md`, preserves portable GitHub `main` related-example links, and rewrites `oakapp.toml` identifiers.

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
