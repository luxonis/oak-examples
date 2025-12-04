#!/usr/bin/env bash

set -euo pipefail

if [[ "${4:-}" == "" ]]; then
  echo "Usage: ./run_tests.sh PYTHON_VERSION_ENV PLATFORM STRICT_MODE ROOT_DIR LOG_LEVEL DAI_VERSION DAI_NODES_VERSION"
  exit 1
fi

PYTHON_VERSION_ENV="$1"
PLATFORM="$2"
STRICT_MODE="$3"
ROOT_DIR="$4"
LOG_LEVEL="$5"
DAI_VERSION="${6:-}"
DAI_NODES_VERSION="${7:-}"
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
  -q tests/test_examples_peripheral.py
