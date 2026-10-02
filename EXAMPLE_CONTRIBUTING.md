# Contributing examples

Follow [EXAMPLE_AUTHORING.md](EXAMPLE_AUTHORING.md) for example structure, documentation, and test commands, and [CONTRIBUTING.md](CONTRIBUTING.md) for the pull request workflow.

## Required startup log for OAK4 standalone tests

Every application used in OAK4 standalone tests must emit the exact message `Pipeline started.` after `pipeline.start()` returns successfully (or after the equivalent pipeline startup call in another language).

The [standalone test runner](tests/test_examples_standalone.py) waits for this application log before starting its run-duration timer. The `App output:` header from `oakctl` does not satisfy this requirement: it indicates log attachment, not successful pipeline startup. Without `Pipeline started.`, the test keeps waiting for startup and cannot begin monitoring the application's required run duration.

For Python applications, print and flush the message immediately after startup:

```python
pipeline.start()
print("Pipeline started.", flush=True)
```

Logging is also supported, for example `logger.info("Pipeline started.")`, provided INFO logging is enabled and the message reaches stdout or stderr in the output captured by `oakctl app run`. Do not emit the message before startup succeeds. Applications using a blocking `pipeline.run()` must use explicit startup followed by their processing loop so they can emit the message while the pipeline is running.
