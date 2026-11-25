# Contributing to oak-examples

Thanks for your interest in contributing to `oak-examples`! We welcome contributions of all kinds — from bug fixes and small tweaks to full-featured examples demonstrating new or advanced uses of OAK devices.

## What’s in this repository

`oak-examples` contains a broad collection of demonstrations, tutorials, and application code for running inference, depth measurement, streaming, custom front-ends, integrations, camera control, and more on OAK / DepthAI devices. Generally, each example lives in its own directory, and similar examples are grouped together under higher-level categories (e.g., `apps`, `tutorials`, etc.).

The `main` branch contains examples using `DepthAIv3` (and all the new components that come with it), whereas the `master` branch contains legacy examples built on `DepthAIV2`.

## How to contribute

We follow a standard GitHub workflow: fork the repository, create a new branch for your changes, then submit a pull request. This avoids disrupting stable code and ensures maintainers can review changes before merging.

### Setup

- Clone the repository locally.
  - Consider using the `--depth 1` flag to create a lightweight clone, as the full repo is quite large.\
    Example:
    ```bash
    git clone --depth 1 --branch main https://github.com/luxonis/oak-examples.git
    ```
- Create a new branch describing your change. Common branch prefixes:
  - `feat/...` for new features
  - `fix/...` for fixes
  - `test/...` for tests
- Install development tools, including pre-commit:
  ```bash
  pip install -r requirements-dev.txt
  ```

## Making changes

### Example selection and implementation

- Compare the purpose and output with nearby examples in [INDEX.md](INDEX.md) and the category README. Adapt the closest example when the difference is small; explain any necessary overlap in the PR.
- Check the current DepthAI API and released `depthai-nodes` components before writing a custom node, recorder, synchronizer, filter, or UI. Use an existing component when it covers the example's purpose; explain custom behavior in the PR when it does not.
- Use concise `kebab-case` directory names for new examples.
- New examples on `main` should use DepthAI v3 patterns.
- Keep required runtime dependencies in the example's `requirements.txt`. Pin compatible released versions of DepthAI and depthai-nodes; check nearby examples and the APIs actually used when changing pins. Use a temporary commit dependency only while coordinating an unreleased upstream change, and replace it with a release before merging.
- List packages imported directly by the example explicitly, even if another dependency currently installs them. Prefer headless OpenCV when the example does not use OpenCV's desktop UI, and remove system GUI libraries that are no longer needed.
- Use the DepthAI Visualizer and its controls for visualization and interaction unless the example specifically requires another UI or output path. Use `logging` for operational messages.
- Keep example code and comments focused on the behavior readers need to understand. Remove dead options, unused UI, task-specific TODOs, version-history commentary, and compatibility branches for versions the example does not support.
- Keep media assets small and store demo media in `/media` when adding human-facing README material.
- Update the relevant top-level category README table when adding a new example.

### Example README

- Use nearby examples as loose structure guides: short purpose, optional `## Demo`, `## Usage` with requirements and options, `## Peripheral Mode` when supported, and `## Standalone Mode (RVC4 only)` when supported. Adapt the sections to the actual example and add headings where they help explain its behavior.
- Put run commands and their expected behavior under the appropriate mode. Check CLI options against the entrypoint and standalone settings against `oakapp.toml` or the backend launch script.
- Describe hardware requirements and limitations that affect whether someone can run the example. Add a compact screenshot or GIF when visual output is central and useful to judge.

### Agent documentation

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
- Derive platform support, dependencies, commands, and constraints from current runtime files. Do not repeat pinned package versions or temporary migration notes in `AGENTS.md` unless the exact version changes how an agent should work.

Validate per-example `AGENTS.md` coverage and structure locally from the repository root:

```bash
python3 scripts/validate_agents_docs.py
```

CI runs the same validation on pull requests.

### Testing

The runnability tests discover examples that have `main.py` and `requirements.txt` in the same directory. Detected examples are run as `python3 main.py` with no additional flags after installing their requirements.

#### Required startup log for OAK4 standalone tests

Every application used in OAK4 standalone tests must emit the exact message `Pipeline started.` after `pipeline.start()` returns successfully (or after the equivalent pipeline startup call in another language).

The [standalone test runner](tests/test_examples_standalone.py) waits for this application log before starting its run-duration timer. The `App output:` header from `oakctl` does not satisfy this requirement: it indicates log attachment, not successful pipeline startup. Without `Pipeline started.`, the test keeps waiting for startup and cannot begin monitoring the application's required run duration.

For Python applications, print the message immediately after startup:

```python
pipeline.start()
print("Pipeline started.")
```

Logging is also supported, for example `logger.info("Pipeline started.")`, provided INFO logging is enabled and the message reaches stdout or stderr in the output captured by `oakctl app run`. Do not emit the message before startup succeeds. Applications using a blocking `pipeline.run()` must use explicit startup followed by their processing loop so they can emit the message while the pipeline is running.

#### Running tests

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

Before finishing, verify the example in a fresh environment with its declared requirements and run the most relevant local test command available for the change. If hardware or dependency constraints prevent local testing, state that explicitly in the PR.

### Bootstrap compatibility

- OAK project bootstrapping may use these examples as host-script or standalone project seeds; keep example `AGENTS.md` files usable outside the monorepo.
- Put cross-example references under a section named exactly `## Related Examples`; bootstrap tooling preserves that section when links are portable GitHub `main` URLs.
- Use GitHub URLs pinned to `main` for cross-example links, for example `https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream`.
- Keep relative links scoped to files inside the example directory. Do not use `../` links to sibling or parent examples.

### Index maintenance

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

## Making the PR

When submitting the PR:

- Provide a clear and concise description of the change.
  - For bug reports: include steps to reproduce, environment details, error logs, and device information (e.g., OAK-D, OAK-4).
- Link the related issue if applicable.
- Make sure the PR is focused, atomic, and well-documented.
- Respond to review feedback — maintainers may request adjustments before merging.
- If the PR is not ready for review, mark it as a **Draft** and list your open questions.

Choose appropriate reviewers:

- If the PR relates to an issue, assign the main issue participant.
- If the PR involves Luxonis developers, add your lead or the relevant team member.
- If unsure, assign **`klemen1999 (Klemen Skrlj)`** who will route the review appropriately.

## CI/CD Requirements Before Merge

A PR targeting `main` must satisfy the CI/CD checks:

- **pre-commit must pass**
  - If it fails, run `pre-commit` locally (see the [Setup](#setup) section), commit the fixes, and push again.
- **Tests must pass**
  - Add the `testable` label to the PR to trigger tests for only the examples modified in the PR.
