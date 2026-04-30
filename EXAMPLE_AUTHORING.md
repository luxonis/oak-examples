# EXAMPLE_AUTHORING.md

Guidance for agents that are adding, removing, moving, or materially changing examples in this repository.

## Documentation

- Add or update the example's `AGENTS.md` whenever creating a new example or materially changing an existing one.
- Keep per-example `AGENTS.md` focused on example-specific purpose, architecture, constraints, safe modifications, and validation.
- Do not repeat shared vocabulary from [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md) unless the example has an exception.
- Treat `README.md` as human-facing documentation. Agent-critical details should live in `AGENTS.md`.
- It is OK for `AGENTS.md` to duplicate important details from `README.md`; prefer duplication over forcing agents to read noisy human-facing docs.

## Bootstrap Compatibility

- `oakctl app create` may bootstrap standalone projects from these examples; keep example `AGENTS.md` files usable outside the monorepo.
- Put monorepo-only cross-links under a section named exactly `## Related Examples`; the bootstrapper removes that section deterministically.
- Keep other relative links scoped to files inside the example directory whenever possible.
- See [OAKCTL_CREATE.md](OAKCTL_CREATE.md) for the bootstrap contract.

## Index Maintenance

Regenerate [INDEX.md](INDEX.md) after adding, removing, moving, or materially changing an example:

```bash
python3 scripts/generate_agents_index.py
```

Do not hand-edit generated example entries in [INDEX.md](INDEX.md); update example metadata/docs or the generator instead.

Verify the generated index before finishing:

```bash
python3 scripts/generate_agents_index.py --check
```

CI runs the same check on pull requests.
