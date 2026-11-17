#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
set -a
. .loci/agent.env
set +a
exec .venv/bin/python -m coordination_bus.mcp_server
