#!/usr/bin/env bash

set -euo pipefail

if [[ "${4:-}" == "" ]]; then
  echo "Usage:"
  echo "  ./run_tests_standalone.sh PYTHON_VERSION_ENV PLATFORM DEVICE_PASSWORD LOCAL_STATIC_REGISTRY ROOT_DIR LOG_LEVEL DAI_VERSION DAI_NODES_VERSION "
  exit 1
fi

PYTHON_VERSION_ENV="$1"
PLATFORM="$2"
DEVICE_PASSWORD="${3}"
LOCAL_STATIC_REGISTRY="${4}"
ROOT_DIR="${5:-.}"
LOG_LEVEL="${6:-INFO}"
DAI_VERSION="${7:-}"
DAI_NODES_VERSION="${8:-}"
echo "=========================================="
echo "Running standalone tests with:"
echo "  PYTHON_VERSION_ENV    = ${PYTHON_VERSION_ENV}"
echo "  PLATFORM              = ${PLATFORM}"
echo "  DEVICE_PASSWORD       = ${DEVICE_PASSWORD}"
echo "  LOCAL_STATIC_REG      = ${LOCAL_STATIC_REGISTRY}"
echo "  ROOT_DIR              = ${ROOT_DIR}"
echo "  LOG_LEVEL             = ${LOG_LEVEL}"
echo "  DAI_VERSION           = ${DAI_VERSION}"
echo "  DAI_NODES_VERSION     = ${DAI_NODES_VERSION}"
echo "=========================================="

# ==============================================================================
# oakctl self-update (best-effort)
# ==============================================================================
echo "Updating oakctl if available..."
if command -v oakctl >/dev/null 2>&1; then
  OAK_VER="$(oakctl version 2>/dev/null || true)"
  if [[ -n "${OAK_VER}" ]]; then
    oakctl self-update -v "${OAK_VER}" || true
  else
    echo "Could not determine oakctl version, skipping self-update."
  fi
else
  echo "oakctl not found, skipping self-update."
fi

echo "Creating virtual environment..."
python3.12 -m venv .venv

echo "Activating venv..."
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r tests/requirements.txt

# NOTE: adb root only works on rooted / userdebug builds; ignore failure on mac setups where it isn't available/allowed.
adb root

# ==============================================================================
# Run tests
# ==============================================================================
echo "Running tests..."

pytest -v -r a --log-cli-level="${LOG_LEVEL}" --log-file=out.log --color=yes \
  --depthai-version="${DAI_VERSION}" \
  --depthai-nodes-version="${DAI_NODES_VERSION}" \
  --environment-variables="DEPTHAI_PLATFORM=${PLATFORM}" \
  --platform="${PLATFORM}" \
  --python-version="${PYTHON_VERSION_ENV}" \
  --device-password="${DEVICE_PASSWORD}" \
  --local-static-registry="${LOCAL_STATIC_REGISTRY}" \
  --root-dir "${ROOT_DIR}" \
  -q tests/test_examples_standalone.py
