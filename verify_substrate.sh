#!/usr/bin/env bash
set -euo pipefail
TAG="${1:-v0.1.0}"
MANIFEST="loci_manifest_${TAG}.sha256"

# If tracked/present locally, verify directly without re-fetching or deleting
if [ -f "${MANIFEST}" ]; then
    sha256sum -c "${MANIFEST}"
    exit 0
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

if command -v gh >/dev/null 2>&1; then
    gh release download "${TAG}" -p "${MANIFEST}" --dir "${TMP_DIR}" --clobber
else
    TOKEN="${GITHUB_TOKEN:-}"
    AUTH_HEADER=()
    if [ -n "${TOKEN}" ]; then
        AUTH_HEADER=(-H "Authorization: token ${TOKEN}")
    fi
    curl -sSL "${AUTH_HEADER[@]}" \
        -H "Accept: application/octet-stream" \
        -o "${TMP_DIR}/${MANIFEST}" \
        "https://github.com/arko-sanyal2/loci-memory-engine/releases/download/${TAG}/${MANIFEST}"
fi

sha256sum -c "${TMP_DIR}/${MANIFEST}"
