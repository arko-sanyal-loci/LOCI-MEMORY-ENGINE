# shellcheck shell=bash
# Shared prelude for scripts/ops/*.sh and scripts/*.sh.
# Resolves the repository root and loads node addresses from config/nodes.env
# (git-ignored; copy config/nodes.env.example and fill it in). Host names,
# IPs and users are never hard-coded in tracked scripts.
LOCI_REPO_DIR="${LOCI_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
LOCI_NODES_ENV="${LOCI_NODES_ENV:-$LOCI_REPO_DIR/config/nodes.env}"
if [ -f "$LOCI_NODES_ENV" ]; then
    # shellcheck disable=SC1090
    source "$LOCI_NODES_ENV"
fi
require_nodes_var() {
    local missing=0
    for v in "$@"; do
        if [ -z "${!v:-}" ]; then
            echo "ERROR: $v is not set. Copy config/nodes.env.example to config/nodes.env and fill it in." >&2
            missing=1
        fi
    done
    [ "$missing" -eq 0 ] || exit 1
}
