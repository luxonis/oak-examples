FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
  bash \
  ca-certificates \
  findutils \
  grep \
  sed \
  ntpsec-ntpdate \
  sudo \
  udev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/oak-examples

ENTRYPOINT ["/bin/bash", "-c", "set -euo pipefail; \
  echo 'Syncing container clock...'; \
  if command -v ntpdate >/dev/null 2>&1; then \
  ntpdate -u pool.ntp.org || true; \
  elif command -v ntpsec-ntpdate >/dev/null 2>&1; then \
  ntpsec-ntpdate -qu pool.ntp.org || true; \
  else \
  echo 'No ntpdate/ntpsec-ntpdate available; skipping.'; \
  fi; \
  exec /tmp/oak-examples/.github/ci/publish_oakapp/publish_oakapp.sh"]
