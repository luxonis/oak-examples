# AGENTS.md

This repository is a reference corpus for building DepthAI and OAK applications.

## Start Here

1. Read [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md) once for shared vocabulary and platform concepts.

### If Using This Repo As A Reference

Use this path when you are finding an example to read, copy from, adapt in another project, or use as inspiration for a DepthAI/OAK solution.

1. Read [INDEX.md](INDEX.md) and shortlist the closest examples by task, modality, and example shape.
2. Read the guide linked by the selected index entry. Prefer `AGENTS.md`; treat `README.md` as fallback context only when agent guidance does not exist.
3. Inspect the selected example's entrypoint, runtime config, support code, and frontend/backend files as needed.
4. Reuse the closest task and pipeline logic first, then adapt it for your target project.

If the user is likely to customize an example for their own use case, bootstrap a standalone copy with the `bootstrap-example` skill before making changes.

### If Maintaining This Repository

Use this path only when you are adding, removing, moving, or materially changing examples in this repository.

1. Read [EXAMPLE_AUTHORING.md](EXAMPLE_AUTHORING.md).
2. Use [INDEX.md](INDEX.md) to find the closest existing example before creating new code.
3. Update or add example-specific `AGENTS.md` guidance for agent-critical details.
