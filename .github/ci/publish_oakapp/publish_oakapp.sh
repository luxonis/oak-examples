#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${ROOT_DIR:-}"
LUXONIS_OFFICIAL_IDENTIFIER="${LUXONIS_OFFICIAL_IDENTIFIER:-false}"
NEW_IDENTIFIER="${NEW_IDENTIFIER:-}"
OAKCTL_HUB_TOKEN="${OAKCTL_HUB_TOKEN:-}"

if [[ -z "$ROOT_DIR" ]]; then
  echo "ROOT_DIR is required." >&2
  exit 1
fi

if [[ ! -d "$ROOT_DIR" ]]; then
  echo "ROOT_DIR does not exist: $ROOT_DIR" >&2
  exit 1
fi

if [[ ! -f "$ROOT_DIR/oakapp.toml" ]]; then
  echo "oakapp.toml not found in $ROOT_DIR" >&2
  exit 1
fi

if [[ -z "$OAKCTL_HUB_TOKEN" ]]; then
  echo "OAKCTL_HUB_TOKEN is required." >&2
  exit 1
fi

cd "$ROOT_DIR"

OAKAPP_TOML="oakapp.toml"
OAKAPP_BACKUP="$(mktemp)"
OAKAPP_FILE=""

cleanup() {
  set +e
  if [[ -n "$OAKAPP_BACKUP" && -f "$OAKAPP_BACKUP" ]]; then
    cp "$OAKAPP_BACKUP" "$OAKAPP_TOML"
    rm -f "$OAKAPP_BACKUP"
  fi
  if [[ -n "$OAKAPP_FILE" && -f "$OAKAPP_FILE" ]]; then
    rm -f "$OAKAPP_FILE"
  fi
}

trap cleanup EXIT

cp "$OAKAPP_TOML" "$OAKAPP_BACKUP"

if [[ -n "$NEW_IDENTIFIER" ]]; then
  if ! grep -qE '^identifier\s*=' "$OAKAPP_TOML"; then
    echo "identifier not found in $OAKAPP_TOML" >&2
    exit 1
  fi
  sed -i -E "s/^identifier\\s*=.*/identifier = \"${NEW_IDENTIFIER}\"/" "$OAKAPP_TOML"
elif [[ "$LUXONIS_OFFICIAL_IDENTIFIER" == "true" ]]; then
  if ! grep -qE '^identifier\s*=' "$OAKAPP_TOML"; then
    echo "identifier not found in $OAKAPP_TOML" >&2
    exit 1
  fi
  sed -i -E '/^identifier\s*=/{s/com\.example/com.luxonis/}' "$OAKAPP_TOML"
fi

if ! command -v oakctl >/dev/null 2>&1; then
  if [[ -x /root/.local/share/oakctl/oakctl ]]; then
    export PATH="/root/.local/share/oakctl:$PATH"
  fi
fi

if ! command -v oakctl >/dev/null 2>&1; then
  echo "oakctl not found in PATH." >&2
  exit 1
fi

oakctl self-update -c beta # TODO: remove this extra flag when 0.17.3 is mainlined
oakctl app build .

OAKAPP_FILE=$(find . -maxdepth 1 -name "*.oakapp" | head -n 1)
if [[ -z "$OAKAPP_FILE" ]]; then
  echo "No .oakapp file found after build." >&2
  exit 1
fi

OAKCTL_HUB_TOKEN="$OAKCTL_HUB_TOKEN" oakctl hub publish "$OAKAPP_FILE"
