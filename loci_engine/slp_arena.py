#!/usr/bin/env python3
"""
Loci Memory Engine - SymLinkPrev (SLP) 20-Byte Node Arena
Compendium Citation: Section 5 & Figure 1A (Host DDR5 RAM / /dev/shm)
Packing: Exactly 20 bytes per node; 3 nodes + 4B header per 64-byte cache line.
"""

import struct
import zlib

class SymLinkPrevNode:
    # Struct format: 8s (64b Z), 4s (32b D), H (16b Heat), H (16b Trust), I (32b CRC/Lineage)
    # Total: 8 + 4 + 2 + 2 + 4 = 20 Bytes exactly
    SLP_STRUCT_FMT = ">8s4sHHI"
    NODE_SIZE_BYTES = struct.calcsize(SLP_STRUCT_FMT)  # 20

    @classmethod
    def pack(cls, z_locator: bytes, domain_id: bytes, heat: float, trust: float, lineage_id: int) -> bytes:
        assert len(z_locator) <= 8, "z_locator max 8 bytes"
        assert len(domain_id) <= 4, "domain_id max 4 bytes"
        z_padded = z_locator.ljust(8, b'\x00')
        d_padded = domain_id.ljust(4, b'\x00')
        
        # Quantize [0.005, 0.995] to unsigned 16-bit integer (0..65535)
        q_heat = int(min(max(heat, 0.005), 0.995) * 65535)
        q_trust = int(min(max(trust, 0.0), 1.0) * 65535)
        
        return struct.pack(cls.SLP_STRUCT_FMT, z_padded, d_padded, q_heat, q_trust, lineage_id)

    @classmethod
    def unpack(cls, buffer: bytes) -> dict:
        z_padded, d_padded, q_heat, q_trust, lineage_id = struct.unpack(cls.SLP_STRUCT_FMT, buffer[:20])
        return {
            "z_locator": z_padded.rstrip(b'\x00').decode('utf-8', errors='ignore'),
            "domain_id": d_padded.rstrip(b'\x00').decode('utf-8', errors='ignore'),
            "heat": round(q_heat / 65535.0, 4),
            "trust": round(q_trust / 65535.0, 4),
            "lineage_id": lineage_id
        }

class CacheLineSlot64B:
    """Manages 64-byte slots: 4-byte header + three 20-byte SLP nodes."""
    SLOT_SIZE_BYTES = 64

    @classmethod
    def pack_slot(cls, slot_flags: int, nodes: list) -> bytes:
        assert len(nodes) <= 3, "Max 3 nodes per 64B cache line"
        header = struct.pack(">I", slot_flags)  # 4 bytes
        body = b"".join(nodes).ljust(60, b"\x00")
        return header + body
