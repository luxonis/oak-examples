#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${ROOT_DIR:-}"
LUXONIS_OFFICIAL_IDENTIFIER="${LUXONIS_OFFICIAL_IDENTIFIER:-true}"
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

ROOT_DIR_FOR_IDENTIFIER="${ROOT_DIR#./}"
TOP_LEVEL_FOLDER="${ROOT_DIR_FOR_IDENTIFIER%%/*}"

OAKAPP_TOML="oakapp.toml"
OAKAPP_BACKUP="$(mktemp)"
OAKAPP_FILE=""
OAKAPP_EDITED_TMP="${OAKAPP_TOML}.tmp"

replace_identifier() {
  local target_identifier="$1"
  sed -E "s|^[[:space:]]*identifier[[:space:]]*=.*|identifier = \"${target_identifier}\"|" "$OAKAPP_TOML" > "$OAKAPP_EDITED_TMP"
  mv "$OAKAPP_EDITED_TMP" "$OAKAPP_TOML"
}

cleanup() {
  set +e
  if [[ -n "$OAKAPP_BACKUP" && -f "$OAKAPP_BACKUP" ]]; then
    cp "$OAKAPP_BACKUP" "$OAKAPP_TOML"
    rm -f "$OAKAPP_BACKUP"
  fi
  if [[ -n "$OAKAPP_FILE" && -f "$OAKAPP_FILE" ]]; then
    rm -f "$OAKAPP_FILE"
  fi
  if [[ -f "$OAKAPP_EDITED_TMP" ]]; then
    rm -f "$OAKAPP_EDITED_TMP"
  fi
}

trap cleanup EXIT

cp "$OAKAPP_TOML" "$OAKAPP_BACKUP"

if [[ -n "$NEW_IDENTIFIER" ]]; then
  if [[ ! "$NEW_IDENTIFIER" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    echo "Invalid identifier: $NEW_IDENTIFIER" >&2
    exit 1
  fi
  if ! grep -qE '^identifier[[:space:]]*=' "$OAKAPP_TOML"; then
    echo "identifier not found in $OAKAPP_TOML" >&2
    exit 1
  fi
  replace_identifier "$NEW_IDENTIFIER"
elif [[ "$LUXONIS_OFFICIAL_IDENTIFIER" == "true" ]]; then
  if ! grep -qE '^identifier[[:space:]]*=' "$OAKAPP_TOML"; then
    echo "identifier not found in $OAKAPP_TOML" >&2
    exit 1
  fi
  CURRENT_IDENTIFIER=$(sed -n -E 's/^[[:space:]]*identifier[[:space:]]*=[[:space:]]*"([^"]*)".*$/\1/p' "$OAKAPP_TOML" | head -n 1)
  IDENTIFIER_PREFIX="com.example.${TOP_LEVEL_FOLDER}."
  if [[ "$CURRENT_IDENTIFIER" == com.luxonis.* ]]; then
    echo "Identifier is already in the com.luxonis namespace; leaving it unchanged: ${CURRENT_IDENTIFIER}"
  elif [[ "$CURRENT_IDENTIFIER" == "$IDENTIFIER_PREFIX"* ]]; then
    TARGET_IDENTIFIER="com.luxonis.${CURRENT_IDENTIFIER#"$IDENTIFIER_PREFIX"}"
    replace_identifier "$TARGET_IDENTIFIER"
  else
    echo "Identifier does not use the expected '${IDENTIFIER_PREFIX}' prefix: ${CURRENT_IDENTIFIER}" >&2
    exit 1
  fi
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

echo "----- Using $OAKAPP_TOML -----"
cat "$OAKAPP_TOML"
echo
echo "----- end of file -----"

oakctl self-update -c beta # TODO: remove this extra flag when 0.17.3 is mainlined
oakctl app build .

OAKAPP_FILE=$(find . -maxdepth 1 -name "*.oakapp" | head -n 1)
if [[ -z "$OAKAPP_FILE" ]]; then
  echo "No .oakapp file found after build." >&2
  exit 1
fi

OAKCTL_HUB_TOKEN="$OAKCTL_HUB_TOKEN" oakctl hub publish "$OAKAPP_FILE"
