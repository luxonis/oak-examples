#!/usr/bin/env bash
# -----------------------------------------------------------
# EXPECTED ARGUMENTS:
#   $1 = PYTHON_VERSION_ENV
#   $2 = DAI_VERSION
#   $3 = DAI_NODES_VERSION
#   $4 = PLATFORM
#   $5 = STRICT_MODE
#   $6 = ROOT_DIR
#   $7 = LOG_LEVEL
# -----------------------------------------------------------

set -euo pipefail

if [[ "${4:-}" == "" ]]; then
  echo "Usage: ./run_tests.sh PYTHON_VERSION_ENV DAI_VERSION DAI_NODES_VERSION PLATFORM STRICT_MODE ROOT_DIR LOG_LEVEL"
  exit 1
fi

PYTHON_VERSION_ENV="$1"
DAI_VERSION="$2"
DAI_NODES_VERSION="$3"
PLATFORM="$4"
STRICT_MODE="$5"
ROOT_DIR="$6"
LOG_LEVEL="$7"

echo "=========================================="
echo "Running tests with:"
echo "  PYTHON_VERSION_ENV    = ${PYTHON_VERSION_ENV}"
echo "  PLATFORM              = ${PLATFORM}"
echo "  STRICT_MODE           = ${STRICT_MODE}"
echo "  ROOT_DIR              = ${ROOT_DIR}"
echo "  LOG_LEVEL             = ${LOG_LEVEL}"
echo "  DAI_VERSION           = ${DAI_VERSION}"
echo "  DAI_NODES_VERSION     = ${DAI_NODES_VERSION}"
echo "=========================================="

echo "Creating virtual environment..."
python3.12 -m venv .venv

echo "Activating venv..."
# shellcheck disable=SC1091
source .venv/bin/activate

adb root

python -m pip install --upgrade pip
pip install -r tests/requirements.txt

echo "Running tests..."
pytest -v -r a --log-cli-level="${LOG_LEVEL}" --log-file=out.log --color=yes \
  --depthai-version="${DAI_VERSION}" \
  --depthai-nodes-version="${DAI_NODES_VERSION}" \
  --environment-variables="DEPTHAI_PLATFORM=${PLATFORM}" \
  --platform="${PLATFORM}" \
  --python-version="${PYTHON_VERSION_ENV}" \
  --strict-mode="${STRICT_MODE}" \
  --root-dir "${ROOT_DIR}" \
  -q "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/test_examples_peripheral.py"
