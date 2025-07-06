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
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir=. tests/
```

This will run all the examples (i.e. folders that have `main.py` and `requirements.txt` present). The outputs will be seen in the CLI and will also be logged into the `out.log` file.

You can also pass other custom options to the pytest command. Here is a list of all the custom ones:

```
  --root-dir=ROOT_DIR   Path to the directory with projects or a single project.
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
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir=. tests/test_examples_peripheral.py
```

If you for example want to run the test on a single example you can do it like this which will run it only on the `generic example`.

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir=neural-networks/generic-example tests/
```
