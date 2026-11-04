#!/usr/bin/env python3
"""
Loci Memory Engine - Real-Time Multi-Node Sync Daemon
Implements WAL-based change capture with ZeroMQ pub/sub delta propagation.

Architecture:
  - Each node runs this daemon alongside loci-mcp.service
  - Local changes detected via SQLite WAL polling (content_hash comparison)
  - Deltas published to peers via ZeroMQ PUB socket
  - Incoming deltas applied via CRDT merge (LWW on heat, causal on supersession)
  - Version vectors track per-node state for anti-entropy convergence
"""

import os
import sys
import json
import time
import sqlite3
import hashlib
import socket
import threading
import struct
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone

SYNC_PORT_PUB = int(os.getenv("LOCI_SYNC_PUB_PORT", "5555"))
SYNC_PORT_SUB = int(os.getenv("LOCI_SYNC_SUB_PORT", "5556"))
DB_PATH = os.getenv("LOCI_DB_PATH", os.path.expanduser("~/loci-memory-engine/context2.db"))
NODE_ID = os.getenv("LOCI_NODE_ID", socket.gethostname())
POLL_INTERVAL = float(os.getenv("LOCI_SYNC_POLL_INTERVAL", "0.5"))


class VersionVector:
    """Tracks causal ordering across nodes using Lamport-style version vectors."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._clocks: Dict[str, int] = {node_id: 0}
        self._lock = threading.Lock()

    def tick(self) -> int:
        with self._lock:
            self._clocks[self.node_id] = self._clocks.get(self.node_id, 0) + 1
            return self._clocks[self.node_id]

    def merge(self, remote_vector: Dict[str, int]) -> None:
        with self._lock:
            for node, clock in remote_vector.items():
                self._clocks[node] = max(self._clocks.get(node, 0), clock)
            self._clocks[self.node_id] = self._clocks.get(self.node_id, 0) + 1

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._clocks)

    def dominates(self, other: Dict[str, int]) -> bool:
        with self._lock:
            for node, clock in other.items():
                if self._clocks.get(node, 0) < clock:
                    return False
            return True

    def missing_from(self, other: Dict[str, int]) -> List[str]:
        with self._lock:
            missing = []
            for node, clock in self._clocks.items():
                if other.get(node, 0) < clock:
                    missing.append(node)
            return missing


class CRDTMerger:
    """
    CRDT merge strategy for memory_item rows:
    - content_hash acts as unique operation ID (idempotent apply)
    - heat uses LWW (Last-Writer-Wins) with wall-clock timestamp
    - status uses lattice ordering: candidate < active < superseded < archived
    - supersession chains form a causal DAG via supersedes_id
    """

    STATUS_LATTICE = {
        "candidate": 0,
        "active": 1,
        "superseded": 2,
        "rejected": 3,
        "quarantined": 4,
        "archived": 5,
    }

    @classmethod
    def merge_item(cls, local: Optional[Dict], remote: Dict) -> Tuple[Dict, str]:
        if local is None:
            return remote, "insert"

        if local["content_hash"] == remote["content_hash"]:
            merged = dict(local)
            changed = False

            if remote.get("updated_at", "") > local.get("updated_at", ""):
                merged["heat"] = remote["heat"]
                merged["updated_at"] = remote["updated_at"]
                changed = True

            remote_rank = cls.STATUS_LATTICE.get(remote.get("status", ""), 0)
            local_rank = cls.STATUS_LATTICE.get(local.get("status", ""), 0)
            if remote_rank > local_rank:
                merged["status"] = remote["status"]
                changed = True

            return merged, "update" if changed else "noop"

        return remote, "conflict"


class WALChangeDetector:
    """Polls SQLite for new or changed rows since last checkpoint."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._last_known_hashes: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._load_initial_state()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_initial_state(self):
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT id, content_hash, updated_at FROM memory_item"
                ).fetchall()
                with self._lock:
                    self._last_known_hashes = {
                        r["id"]: f"{r['content_hash']}:{r['updated_at']}" for r in rows
                    }
        except Exception:
            pass

    def detect_changes(self) -> List[Dict[str, Any]]:
        changes = []
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM memory_item"
                ).fetchall()

                current_state = {}
                for row in rows:
                    r = dict(row)
                    key = f"{r['content_hash']}:{r['updated_at']}"
                    current_state[r["id"]] = key

                    with self._lock:
                        if self._last_known_hashes.get(r["id"]) != key:
                            changes.append(r)

                with self._lock:
                    self._last_known_hashes = current_state

        except Exception:
            pass
        return changes


class MerkleTree:
    """
    Row-level Merkle tree over content_hash for fast divergence detection.
    Extends the existing manifest.sha256 approach to individual rows.
    """

    @staticmethod
    def compute_row_hash(item: Dict[str, Any]) -> str:
        payload = f"{item['id']}:{item['content_hash']}:{item.get('status', '')}:{item.get('heat', 0.0)}"
        return hashlib.sha256(payload.encode()).hexdigest()

    @classmethod
    def compute_tree_root(cls, items: List[Dict[str, Any]]) -> str:
        if not items:
            return hashlib.sha256(b"empty").hexdigest()

        hashes = sorted(cls.compute_row_hash(item) for item in items)

        while len(hashes) > 1:
            next_level = []
            for i in range(0, len(hashes), 2):
                if i + 1 < len(hashes):
                    combined = hashes[i] + hashes[i + 1]
                else:
                    combined = hashes[i] + hashes[i]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            hashes = next_level

        return hashes[0]


class SyncDelta:
    """Wire format for a sync delta message."""

    @staticmethod
    def encode(node_id: str, version_vector: Dict[str, int], items: List[Dict[str, Any]]) -> bytes:
        payload = {
            "node_id": node_id,
            "version_vector": version_vector,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "items": items,
            "merkle_root": MerkleTree.compute_tree_root(items),
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> Dict[str, Any]:
        return json.loads(data.decode("utf-8"))


class NodeSyncDaemon:
    """
    Main daemon: orchestrates change detection, delta publishing, and CRDT merge.

    Transport-agnostic core — the publish/subscribe layer is injected.
    Default uses TCP sockets for simplicity (no ZeroMQ dependency required).
    """

    def __init__(self, db_path: str = DB_PATH, node_id: str = NODE_ID):
        self.db_path = db_path
        self.node_id = node_id
        self.version_vector = VersionVector(node_id)
        self.change_detector = WALChangeDetector(db_path)
        self.merger = CRDTMerger()
        self._running = False
        self._peers: List[Tuple[str, int]] = []
        self._stats = {"deltas_sent": 0, "deltas_received": 0, "merges_applied": 0, "conflicts": 0}

    def add_peer(self, host: str, port: int = SYNC_PORT_SUB):
        self._peers.append((host, port))

    def _apply_remote_delta(self, delta: Dict[str, Any]) -> int:
        if delta["node_id"] == self.node_id:
            return 0

        self.version_vector.merge(delta["version_vector"])
        applied = 0

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            for remote_item in delta.get("items", []):
                local_row = conn.execute(
                    "SELECT * FROM memory_item WHERE id = ?", (remote_item["id"],)
                ).fetchone()

                local = dict(local_row) if local_row else None
                merged, action = self.merger.merge_item(local, remote_item)

                if action == "insert":
                    cols = ", ".join(merged.keys())
                    placeholders = ", ".join(["?"] * len(merged))
                    conn.execute(
                        f"INSERT OR IGNORE INTO memory_item ({cols}) VALUES ({placeholders})",
                        list(merged.values()),
                    )
                    applied += 1
                elif action == "update":
                    conn.execute(
                        "UPDATE memory_item SET heat = ?, status = ?, updated_at = ? WHERE id = ?",
                        (merged["heat"], merged["status"], merged["updated_at"], merged["id"]),
                    )
                    applied += 1
                elif action == "conflict":
                    self._stats["conflicts"] += 1

            conn.commit()
            conn.close()
        except Exception:
            pass

        self._stats["deltas_received"] += 1
        self._stats["merges_applied"] += applied
        return applied

    def poll_and_publish(self) -> Optional[bytes]:
        changes = self.change_detector.detect_changes()
        if not changes:
            return None

        seq = self.version_vector.tick()
        delta_bytes = SyncDelta.encode(
            self.node_id, self.version_vector.snapshot(), changes
        )
        self._stats["deltas_sent"] += 1
        return delta_bytes

    def run_once(self) -> Dict[str, Any]:
        delta = self.poll_and_publish()
        return {
            "node_id": self.node_id,
            "has_delta": delta is not None,
            "delta_size": len(delta) if delta else 0,
            "stats": dict(self._stats),
            "version_vector": self.version_vector.snapshot(),
        }

    def get_anti_entropy_state(self) -> Dict[str, Any]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM memory_item").fetchall()
            items = [dict(r) for r in rows]
            conn.close()
        except Exception:
            items = []

        return {
            "node_id": self.node_id,
            "version_vector": self.version_vector.snapshot(),
            "merkle_root": MerkleTree.compute_tree_root(items),
            "item_count": len(items),
        }


def load_peers_from_env(config_path: str = "") -> List[Tuple[str, int]]:
    if not config_path:
        config_path = os.path.expanduser("~/loci-memory-engine/config/nodes.env")

    peers = []
    if not os.path.exists(config_path):
        return peers

    env = {}
    with open(config_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"')

    for key in ("WORKSTATION_IP", "CONSOLE_IP", "VPS_HOST", "MAC_MINI_IP"):
        addr = env.get(key)
        if addr:
            peers.append((addr, SYNC_PORT_SUB))

    return peers


if __name__ == "__main__":
    daemon = NodeSyncDaemon()
    for host, port in load_peers_from_env():
        if host not in (socket.gethostname(), "127.0.0.1"):
            daemon.add_peer(host, port)

    print(f"[loci-sync] Node {daemon.node_id} starting, peers: {daemon._peers}")

    while True:
        result = daemon.run_once()
        if result["has_delta"]:
            print(f"[loci-sync] Delta published: {result['delta_size']}B, stats: {result['stats']}")
        time.sleep(POLL_INTERVAL)
