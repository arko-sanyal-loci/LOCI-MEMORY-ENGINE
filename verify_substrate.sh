#!/usr/bin/env bash
set -euo pipefail
TAG="${1:-v0.1.0}"
curl -sSL -O "https://github.com/arko-sanyal2/loci-memory-engine/releases/download/${TAG}/loci_manifest_${TAG}.sha256"
sha256sum -c "loci_manifest_${TAG}.sha256"
rm -f "loci_manifest_${TAG}.sha256"
