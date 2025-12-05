# Examples Testing

We can test every example in a way where we verify that it is running for a certain period on a specific platform, python, and depthai version.

## Installation

To install the requirements you can do:

```bash
pip install -r requirements.txt
```

## Usage

If you want to run the tests locally we recommend you navigate to the root directory and then run the same command that is running in the Dockerfile:

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir . -- tests/
```

This will run all the examples (i.e. folders that have `main.py` and `requirements.txt` present). The outputs will be seen in the CLI and will also be logged into the `out.log` file.

**Note:** Because `root-dir` can also accept list of arguments always specify it last, don't use `=` after it and when list is complete use `--` to mark the end (as see in the examples).

You can also pass other custom options to the pytest command. Here is a list of all the custom ones:

```
  --root-dir=ROOT_DIR   One or more paths to directories containing examples (space-separated)..
  --timeout=TIMEOUT     Timeout for script execution (default: 30s).
  --depthai-version=DEPTHAI_VERSION
                        Specify a depthai version to override requirements.txt.
  --depthai-nodes-version=DEPTHAI_NODES_VERSION
                        Specify a depthai-nodes version to override requirements.txt. Can be either released version or branch from GH.
  --environment-variables=ENVIRONMENT_VARIABLES
                        List of additional environment variables (format: VAR1=VAL1 VAR2=VAL2).
  --virtual-display     Enable virtual display (sets DISPLAY=':99'). Only used for peripheral tests.
  --platform={rvc2,rvc4}
                        Specify a platform this is tested on (rvc2 or rvc4). Only used for filtering test examples.
  --python-version={3.8,3.10,3.12}
                        Specify a python version this is tested with (3.8, 3.10 or 3.12). Only used for filtering test examples.
  --strict-mode={yes,no}
                        If set to 'yes', tests will fail on DepthAI warnings.
  --device=DEVICE       Device to perform standalone tests on. If testing just peripheral then not required.
  --device_password=DEVICE_PASSWORD
                        Specify device password. If testing just peripheral then not required.
```

**Note:** The platform and Python values are only used for filtering examples that are known to fail on some combinations when run locally. When run through GitHub workflow on a HIL setup these are taken into account (we build an image with a specific Python version and take a device from the specified platform).

**Note:** If you want to run only peripheral or only standalone tests then set full path to those tests in pytest command. Eg. to only test peripheral:

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir . -- tests/test_examples_peripheral.py
```

If you for example want to run the test on a single example you can do it like this which will run it only on the `generic example`.

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir neural-networks/generic-example -- tests/
```

## Known Failing Examples (Rule System)

Some examples are known to fail under specific conditions (platform, OS, mode, Python
version, DepthAI version, etc.). These are defined in [`constants.py`](./constants.py) inside the
`KNOWN_FAILING` dictionary. During test execution, these rules are evaluated and any
example that matches a failing rule is skipped with the provided reason.

### Rule System Overview

Each failing example contains:

- `reason` – A human-readable explanation of why the example is expected to fail.
- `rules` – A tree of logical conditions describing under which environments the
  example should be treated as failing.

### Rule Tree Structure

A rule tree is composed of logical groups:

```json
{ "and": [ <rules> ] }
{ "or":  [ <rules> ] }
```

- `"and"` — All rules inside must match for the example to be considered failing.
- `"or"`  — Any rule inside may match for the example to be considered failing.

**Every rule block must contain either an `"and"` or `"or"` group**, even when there
is only a single condition.

### Leaf Rules

Leaf rules describe a single condition and take the form:

```json
{ "<condition_name>": <failing_value> }
```

Leaf rules **must contain exactly one condition**.

Supported condition names and values:

| Field             | Allowed Values Example                             | Meaning                                    |
| ----------------- | -------------------------------------------------- | ------------------------------------------ |
| `mode`            | `"all"` or `["peripheral"]`, `["standalone"]`      | Test mode fails under these values         |
| `platform`        | `"all"` or `["rvc2"]`, `["rvc4"]`                  | Hardware platform conditions               |
| `python_version`  | `"all"` or `["3.8"]`, `["3.10"]`, `["3.12"]`       | Python versions that are failing           |
| `depthai_version` | `"all"` or version spec: `">3.0.0rc1"`, `"<3.1.0"` | Fails if DepthAI version matches condition |
| `os`              | `"all"` or `["mac"]`, `["win"]`, `["linux"]`       | Operating system where this fails          |

**A leaf returns True (→ failing) when the current environment matches its
condition.**

### Examples

#### 1. Fail only when running in peripheral mode

```json
"rules": {
    "and": [
        { "mode": ["peripheral"] }
    ]
}
```

#### 2. Fail only on RVC4 devices

```json
"rules": {
    "and": [
        { "platform": ["rvc4"] }
    ]
}
```

#### 3. Fail when platform is RVC2 **or** OS is mac

```json
"rules": {
    "or": [
        { "platform": ["rvc2"] },
        { "os": ["mac"] }
    ]
}
```

#### 4. Fail under both conditions (mode=all AND platform=all)

```json
"rules": {
    "and": [
        { "mode": "all" },
        { "platform": "all" }
    ]
}
```

#### 5. Mixed logic:

Fail when **(mode=all AND platform=rvc2)** OR **(platform=all)**

```json
"rules": {
    "or": [
        {
            "and": [
                { "mode": "all" },
                { "platform": ["rvc2"] }
            ]
        },
        { "platform": "all" }
    ]
}
```

### How Tests Use These Rules

During test collection and filtering:

1. The current environment (mode, platform, python, os, DepthAI version) is collected.
2. Each example’s rule tree is evaluated recursively.
3. If the rules evaluate to `True`, the example is marked as a known failing case and is
   skipped with the associated reason.
4. Otherwise, the example is tested normally.

This system makes it easy to describe complex skip logic without hard-coding behavior
inside the test runner.
