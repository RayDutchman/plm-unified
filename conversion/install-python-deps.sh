#!/usr/bin/env bash
set -euo pipefail

REQ_FILE="${1:-/tmp/requirements-converter.txt}"
WHEELHOUSE_URL="${CONVERTER_WHEELHOUSE_URL:-}"

# Optional private index override.
if [[ -n "${CONVERTER_PIP_INDEX_URL:-}" ]]; then
  export PIP_INDEX_URL="${CONVERTER_PIP_INDEX_URL}"
fi
if [[ -n "${CONVERTER_PIP_EXTRA_INDEX_URL:-}" ]]; then
  export PIP_EXTRA_INDEX_URL="${CONVERTER_PIP_EXTRA_INDEX_URL}"
fi

echo "[deps] requirement file: ${REQ_FILE}"

# Prefer internal wheelhouse for reproducibility.
if [[ -n "${WHEELHOUSE_URL}" ]]; then
  echo "[deps] trying internal wheelhouse: ${WHEELHOUSE_URL}"
  if python3 -m pip install --break-system-packages --no-cache-dir --no-index --find-links "${WHEELHOUSE_URL}" -r "${REQ_FILE}"; then
    echo "[deps] installed from internal wheelhouse"
    exit 0
  fi
  echo "[deps] internal wheelhouse install failed, fallback to index"
fi

echo "[deps] installing from package index"
python3 -m pip install --break-system-packages --no-cache-dir -r "${REQ_FILE}"
