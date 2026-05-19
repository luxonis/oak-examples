# EXAMPLE_AUTHORING.md

Guidance for agents that are adding, removing, moving, or materially changing examples in this repository.

## Making Changes

- Prefer adapting the closest existing example over creating a new one from scratch.
- Use concise `kebab-case` directory names for new examples.
- New examples on `main` should use DepthAI v3 patterns.
- Keep required runtime dependencies in the example's `requirements.txt`.
- Use the DepthAI Visualizer for visualization unless the example specifically requires another UI or output path.
- Keep media assets small and store demo media in `/media` when adding human-facing README material.
- Update the relevant top-level category README table when adding a new example.

## Agent Documentation

- Add or update the example's `AGENTS.md` whenever creating a new example or materially changing an existing one.
- Keep per-example `AGENTS.md` focused on example-specific purpose, architecture, constraints, safe modifications, and validation.
- Start every per-example guide with `# AGENTS.md` as the only H1 heading in the file.
- Use these required H2 sections exactly once and in this order:
  `## Summary`, `## Use This Example When`, `## Do Not Use This Example When`, `## Quick Facts`, `## Read First`, `## Architecture`, `## Constraints`, `## Related Examples`, `## Validation`
- The following H2 sections are optional, but when present they must appear in these positions:
  `## Data Flow` after `## Architecture`
  `## Modification Guide` after `## Data Flow` or `## Architecture`
  `## Common Adaptations` after `## Modification Guide` or `## Architecture`
  `## Non-Obvious Repo Conventions` after `## Constraints`
- Do not add any other H1 or H2 sections. If you need extra structure, use bullets or H3 headings under the allowed sections.
- Start the body with a `## Summary` section. Its first paragraph is used by the generated [INDEX.md](INDEX.md), so keep it to one or two short sentences.
- Do not repeat shared vocabulary from [ESSENTIAL_KNOWLEDGE.md](ESSENTIAL_KNOWLEDGE.md) unless the example has an exception.
- Treat `README.md` as human-facing documentation. Agent-critical details should live in `AGENTS.md`.
- It is OK for `AGENTS.md` to duplicate important details from `README.md`; prefer duplication over forcing agents to read noisy human-facing docs.

Validate per-example `AGENTS.md` coverage and structure locally from the repository root:

```bash
python3 scripts/validate_agents_docs.py
```

CI runs the same validation on pull requests.

## Testing

The runnability tests discover examples that have `main.py` and `requirements.txt` in the same directory. Detected examples are run as `python3 main.py` with no additional flags after installing their requirements.

Run all example tests locally from the repository root:

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir . -- tests/
```

Run only peripheral tests:

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir . -- tests/test_examples_peripheral.py
```

Run tests for one example:

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir neural-networks/generic-example -- tests/
```

Useful local filters:

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --platform rvc4 --python-version 3.12 --root-dir neural-networks/generic-example -- tests/
```

If an example is intentionally incompatible with a mode, platform, Python version, OS, or DepthAI version, add or update its rule in [tests/constants.py](tests/constants.py). See [tests/README.md](tests/README.md) for the known-failing rule format.

Before finishing, run the most relevant local test command available for the change. If hardware or dependency constraints prevent local testing, state that explicitly in the PR.

## Bootstrap Compatibility

- OAK project bootstrapping may use these examples as host-script or standalone project seeds; keep example `AGENTS.md` files usable outside the monorepo.
- Put cross-example references under a section named exactly `## Related Examples`; bootstrap tooling preserves that section when links are portable GitHub `main` URLs.
- Use GitHub URLs pinned to `main` for cross-example links, for example `https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream`.
- Keep relative links scoped to files inside the example directory. Do not use `../` links to sibling or parent examples.

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
