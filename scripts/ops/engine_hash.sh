#!/usr/bin/env bash
# One definition of the engine tree hash, shared by node_sync.sh,
# update_manifest.sh and check_remote_parity.sh (remote side mirrors it).
# Bytecode caches are excluded: importing the engine creates them, and counting
# them made every node look diverged forever.
engine_hash() {
  LC_ALL=C find loci_engine -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -exec sha256sum {} + \
    | LC_ALL=C sort | sha256sum | awk '{print $1}'
}
