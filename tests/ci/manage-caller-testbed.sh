#!/usr/bin/env bash
set -euo pipefail

init() {
  local private_dir nonce reservation
  private_dir=$(mktemp -d "$GITHUB_WORKSPACE/.caller-artifacts-XXXXXX")
  nonce=${private_dir##*-}
  reservation="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
  reservation+="#examples-$GITHUB_RUN_ATTEMPT-$HOST_OS-$SUITE"
  reservation+="-$PLATFORM-$PYTHON_VERSION-$nonce"
  {
    echo "CALLER_PRIVATE_DIR=$private_dir"
    echo "CALLER_REMOTE_DIR=examples-private-$GITHUB_RUN_ID-$nonce"
    echo "CALLER_HOST_OS=$HOST_OS"
    echo "HOLD_RESERVATION=--hold-reservation"
    echo "EXTERNAL_RESERVATION_NAME=$reservation"
  } >> "$GITHUB_ENV"
  {
    echo "helpers_path=${private_dir#"$GITHUB_WORKSPACE/"}/src"
    echo "artifacts_path=$private_dir/src/.artifacts"
    jq -r 'to_entries[] | "\(.key)=\(.value)"' <<< "$CALLER_ARTIFACTS"
  } >> "$GITHUB_OUTPUT"
}

prepare() {
  local host_args script encoded command
  cp "$GITHUB_WORKSPACE/oak-examples/tests/ci/verify-caller-binaries.py" \
    "$CALLER_PRIVATE_DIR/src/verify-caller-binaries.py"
  echo "CALLER_PREPARATION_STARTED=true" >> "$GITHUB_ENV"
  host_args=(-os "$CALLER_HOST_OS")
  if [[ "$CALLER_HOST_OS" == windows ]]; then
    script="\$ErrorActionPreference = \"Stop\"; "
    script+="Set-Location '$CALLER_REMOTE_DIR'; "
    script+="& pwsh -NoProfile -NonInteractive -File src/ci/hil/prepare-examples.ps1; "
    script+="if (\$LASTEXITCODE) { exit \$LASTEXITCODE }; "
    script+="& python src/verify-caller-binaries.py windows; exit \$LASTEXITCODE"
    encoded=$(printf '%s' "$script" | iconv -t UTF-16LE | base64 -w0)
    command="pwsh -NoProfile -NonInteractive -EncodedCommand $encoded"
    host_args+=(--no-shell)
  else
    command="cd $CALLER_REMOTE_DIR && export HOST_OS=$CALLER_HOST_OS && "
    command+="bash src/ci/hil/prepare-examples.sh && "
    command+="python3 src/verify-caller-binaries.py $CALLER_HOST_OS"
  fi
  hil_runner --models 'oak4_pro or oak4_d' \
    --reservation-name "$EXTERNAL_RESERVATION_NAME" --hold-reservation --wait \
    --os-version 1.47.0 "${host_args[@]}" --sync-workspace \
    --local-path "$CALLER_PRIVATE_DIR/." --remote-path "$CALLER_REMOTE_DIR" \
    --commands "$command"
}

cleanup() {
  local reservations testbed host_args command cleanup_status
  [[ -n "${CALLER_PRIVATE_DIR:-}" ]] || return 0
  [[ "$CALLER_PRIVATE_DIR" == "$GITHUB_WORKSPACE"/.caller-artifacts-* ]]
  trap 'rm -rf -- "$CALLER_PRIVATE_DIR"' EXIT
  [[ "${CALLER_PREPARATION_STARTED:-false}" == true ]] || return 0
  reservations=$(hil_reserve all \
    --reservation-name "$EXTERNAL_RESERVATION_NAME" --json get \
    --server_os "$CALLER_HOST_OS" --models 'oak4_pro or oak4_d')
  testbed=$(jq -r '.[] | select(.reserved_by_me) | .config' <<< "$reservations")
  [[ -n "$testbed" ]] || return 0
  [[ "$CALLER_REMOTE_DIR" =~ ^examples-private-[0-9]+-[a-zA-Z0-9]+$ ]]
  host_args=(-os "$CALLER_HOST_OS")
  if [[ "$CALLER_HOST_OS" == windows ]]; then
    command="pwsh -NoProfile -NonInteractive -Command "
    command+="\"if (Test-Path -LiteralPath '$CALLER_REMOTE_DIR') { "
    command+="Remove-Item -LiteralPath '$CALLER_REMOTE_DIR' -Recurse -Force -ErrorAction Stop }\""
    host_args+=(--no-shell)
  else
    command="rm -rf -- $CALLER_REMOTE_DIR"
  fi
  cleanup_status=0
  hil_runner --testbed "$testbed" \
    --reservation-name "$EXTERNAL_RESERVATION_NAME" --hold-reservation \
    --skip-sanity-check --no-update "${host_args[@]}" \
    --commands "$command" || cleanup_status=$?
  hil_reserve "$testbed" --reservation-name "$EXTERNAL_RESERVATION_NAME" \
    --json free | jq -e '.reserved == false' || cleanup_status=$?
  return "$cleanup_status"
}

case "$1" in
  init) init ;;
  prepare) prepare ;;
  cleanup) cleanup ;;
esac
