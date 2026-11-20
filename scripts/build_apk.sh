#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$project_root/scripts/prepare_sdk.py"
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --env HOME=/tmp --env JAVA_TOOL_OPTIONS=-Duser.home=/tmp \
  --volume "$project_root:/work" \
  --volume "$HOME/.cache/jarvis-tv-sdk:/sdk:ro" \
  --workdir /work \
  eclipse-temurin:17-jdk-jammy@sha256:057a0daec60e87c96571bf5c9c7792065bcb19e804d584cd37d4144038a35717 \
  bash /work/scripts/compile_android.sh
