FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    findutils \
    grep \
    sed \
  && mkdir -p /etc/udev/rules.d \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/oak-examples

ENTRYPOINT ["/bin/bash", "/tmp/oak-examples/.github/ci/publish_oakapp/publish_oakapp.sh"]
