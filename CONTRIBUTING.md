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

If you are fixing, adding, removing, moving, or materially changing examples, follow [EXAMPLE_AUTHORING.md](EXAMPLE_AUTHORING.md).

### Testing

For example test discovery, local pytest commands, and known-failing example rules, follow the [Testing](EXAMPLE_AUTHORING.md#testing) section in [EXAMPLE_AUTHORING.md](EXAMPLE_AUTHORING.md).

#### Required startup log for OAK4 standalone tests

Every application used in OAK4 standalone tests must emit the exact message `Pipeline started.` after `pipeline.start()` returns successfully (or after the equivalent pipeline startup call in another language).

The [standalone test runner](tests/test_examples_standalone.py) waits for this application log before starting its run-duration timer. The `App output:` header from `oakctl` does not satisfy this requirement: it indicates log attachment, not successful pipeline startup. Without `Pipeline started.`, the test keeps waiting for startup and cannot begin monitoring the application's required run duration.

For Python applications, print and flush the message immediately after startup:

```python
pipeline.start()
print("Pipeline started.", flush=True)
```

Logging is also supported, for example `logger.info("Pipeline started.")`, provided INFO logging is enabled and the message reaches stdout or stderr in the output captured by `oakctl app run`. Do not emit the message before startup succeeds. Applications using a blocking `pipeline.run()` must use explicit startup followed by their processing loop so they can emit the message while the pipeline is running.

### Making the PR

Before pushing your changes, ensure that:

- Your changes work in a fresh environment
- `pre-commit` passes
- Tests pass locally

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

### CI/CD Requirements Before Merge

A PR targeting `main` must satisfy the CI/CD checks:

- **pre-commit must pass**
  - If it fails, run `pre-commit` locally (see the [Setup](#setup) section), commit the fixes, and push again.
- **Tests must pass**
  - Add the `testable` label to the PR to trigger tests for only the examples modified in the PR.
