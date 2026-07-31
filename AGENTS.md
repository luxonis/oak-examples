# AGENTS.md

This repository is a reference corpus for building DepthAI and OAK applications.

## Start Here

1. Read [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md) once for shared vocabulary and platform concepts.

### If Using This Repo As A Reference

Use this path when you are finding an example to read, copy from, adapt in another project, or use as inspiration for a DepthAI/OAK solution.

1. Read [EXAMPLE_SELECTION.md](EXAMPLE_SELECTION.md) and choose the simplest starting point that satisfies the business outcome, hardware, application shape, state, and output requirements.
2. Use [INDEX.md](INDEX.md) to shortlist alternatives by task, modality, and example shape.
3. Read the guide linked by the selected index entry. Prefer `AGENTS.md`; treat `README.md` as fallback context only when agent guidance does not exist.
4. Inspect the selected example's entrypoint, runtime config, support code, and frontend/backend files as needed.
5. Reuse only the task and pipeline logic that maps to the target product; do not preserve educational stages without a product requirement.

If the user is likely to customize an example for their own use case, bootstrap a standalone copy with the `bootstrap-example` skill before making changes.

### If Maintaining This Repository

Use this path only when you are adding, removing, moving, or materially changing examples in this repository.

1. Read [EXAMPLE_AUTHORING.md](EXAMPLE_AUTHORING.md).
2. Use [EXAMPLE_SELECTION.md](EXAMPLE_SELECTION.md) and [INDEX.md](INDEX.md) to find the best product base and the closest related examples before creating new code.
3. Update or add example-specific `AGENTS.md` guidance for agent-critical details, including whether the example is a product starting point or a technique showcase when that distinction is non-obvious.
