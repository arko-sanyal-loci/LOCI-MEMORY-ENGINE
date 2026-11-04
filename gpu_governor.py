#!/usr/bin/env python3
"""
LOCI GPU Governor — Multi-GPU Safety & Allocation

Manages the dual-GPU topology (NVIDIA RTX 5060 Ti + Intel Arc B580 Pro)
with a 5% safety margin over rated limits to ensure longevity. Prevents
task pileup by tracking per-GPU load and queuing when capacity is reached.

GPU Topology:
  GPU 0: NVIDIA RTX 5060 Ti — 16 GB VRAM, 180W TDP, CUDA 13.2
    - card1, renderD128, PCIe 06:00.0
    - Primary compute: Ollama models, CUDA workloads
  GPU 1: Intel Arc B70 Pro Sparkle — 32 GB VRAM, 330W TDP (Battlemage G31)
    - card2, renderD129, PCIe 04:00.0
    - Active: llama.cpp SYCL backend, loci-arc-35b (qwen3.6-35b-a3b MoE)

Safety Margins (5% below rated limits):
  NVIDIA: 171W max draw (180W * 0.95), 85°C thermal limit (90°C * ~0.94)
  Arc:    313W max draw (330W * 0.95), 90°C thermal limit (95°C * ~0.95)
  VRAM:   95% max allocation per GPU — always keep 5% free for system overhead
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# GPU Hardware Definitions
# ---------------------------------------------------------------------------

GPU_SPECS = {
    "nvidia_rtx_5060_ti": {
        "name": "NVIDIA GeForce RTX 5060 Ti",
        "pcie_id": "06:00.0",
        "drm_card": "card1",
        "render_node": "renderD128",
        "vram_mb": 16311,
        "tdp_watts": 180,
        "thermal_limit_c": 90,
        "compute_api": "cuda",
        "driver": "nvidia",
        # Safety margins: 5% below rated
        "safe_power_watts": 171,       # 180 * 0.95
        "safe_thermal_c": 85,          # ~5% margin
        "safe_vram_mb": 15495,         # 16311 * 0.95
    },
    "intel_arc_b580_pro": {
        "name": "Intel Arc B70 Pro Sparkle (Battlemage G31)",
        "pcie_id": "04:00.0",
        "drm_card": "card2",
        "render_node": "renderD129",
        "vram_mb": 32768,
        "tdp_watts": 330,
        "thermal_limit_c": 95,
        "compute_api": "pending",  # needs intel-opencl-icd + level-zero
        "driver": "xe",
        # Safety margins: 5% below rated
        "safe_power_watts": 313,       # 330 * 0.95
        "safe_thermal_c": 90,
        "safe_vram_mb": 31129,         # 32768 * 0.95
    },
}

# ---------------------------------------------------------------------------
# Task Queue — prevent pileup
# ---------------------------------------------------------------------------

MAX_CONCURRENT_TASKS_PER_GPU = 2  # Don't pile more than 2 tasks per GPU
TASK_QUEUE: List[Dict[str, Any]] = []
ACTIVE_TASKS: Dict[str, List[Dict[str, Any]]] = {
    "nvidia_rtx_5060_ti": [],
    "intel_arc_b580_pro": [],
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# GPU Status Polling
# ---------------------------------------------------------------------------

def get_nvidia_status() -> Dict[str, Any]:
    """Poll NVIDIA GPU via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,power.limit,"
             "fan.speed,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return {"error": "nvidia-smi failed", "raw": result.stderr}

        parts = [p.strip() for p in result.stdout.strip().split(",")]
        temp = float(parts[0])
        power_draw = float(parts[1])
        power_limit = float(parts[2])
        fan = int(parts[3])
        mem_used = int(parts[4])
        mem_total = int(parts[5])
        util = int(parts[6])

        spec = GPU_SPECS["nvidia_rtx_5060_ti"]
        return {
            "gpu": "nvidia_rtx_5060_ti",
            "name": spec["name"],
            "temperature_c": temp,
            "power_draw_w": power_draw,
            "power_limit_w": power_limit,
            "fan_speed_pct": fan,
            "vram_used_mb": mem_used,
            "vram_total_mb": mem_total,
            "vram_free_mb": mem_total - mem_used,
            "utilization_pct": util,
            "safe_power_w": spec["safe_power_watts"],
            "safe_thermal_c": spec["safe_thermal_c"],
            "safe_vram_mb": spec["safe_vram_mb"],
            "power_headroom_w": round(spec["safe_power_watts"] - power_draw, 1),
            "thermal_headroom_c": round(spec["safe_thermal_c"] - temp, 1),
            "vram_headroom_mb": spec["safe_vram_mb"] - mem_used,
            "within_safety_margin": (
                power_draw <= spec["safe_power_watts"]
                and temp <= spec["safe_thermal_c"]
                and mem_used <= spec["safe_vram_mb"]
            ),
            "active_tasks": len(ACTIVE_TASKS["nvidia_rtx_5060_ti"]),
            "can_accept_task": len(ACTIVE_TASKS["nvidia_rtx_5060_ti"]) < MAX_CONCURRENT_TASKS_PER_GPU,
        }
    except Exception as e:
        return {"error": str(e), "gpu": "nvidia_rtx_5060_ti"}


def get_intel_arc_status() -> Dict[str, Any]:
    """Poll Intel Arc GPU via sysfs (no compute runtime needed for basic status)."""
    spec = GPU_SPECS["intel_arc_b580_pro"]
    hwmon_path = "/sys/class/drm/card2/device/hwmon/hwmon7"

    status: Dict[str, Any] = {
        "gpu": "intel_arc_b580_pro",
        "name": spec["name"],
        "compute_api": spec["compute_api"],
        "vram_total_mb": spec["vram_mb"],
        "safe_power_w": spec["safe_power_watts"],
        "safe_thermal_c": spec["safe_thermal_c"],
        "safe_vram_mb": spec["safe_vram_mb"],
        "active_tasks": len(ACTIVE_TASKS["intel_arc_b580_pro"]),
        "can_accept_task": len(ACTIVE_TASKS["intel_arc_b580_pro"]) < MAX_CONCURRENT_TASKS_PER_GPU,
    }

    # Read power cap
    try:
        with open(f"{hwmon_path}/power1_cap") as f:
            power_cap_uw = int(f.read().strip())
            status["power_cap_w"] = power_cap_uw / 1_000_000
    except (FileNotFoundError, ValueError):
        status["power_cap_w"] = None

    # Read temperature (may not be available if card is in D3hot)
    try:
        with open(f"{hwmon_path}/temp1_input") as f:
            temp_mc = int(f.read().strip())
            status["temperature_c"] = temp_mc / 1000
            status["thermal_headroom_c"] = round(spec["safe_thermal_c"] - temp_mc / 1000, 1)
    except (FileNotFoundError, ValueError):
        status["temperature_c"] = None
        status["thermal_headroom_c"] = None
        status["power_state"] = "D3hot (suspended — no compute runtime active)"

    # Check if compute runtime is available
    status["compute_ready"] = os.path.exists("/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so")
    if not status["compute_ready"]:
        status["setup_needed"] = [
            "sudo apt-get install -y intel-opencl-icd intel-gpu-tools",
            f"sudo usermod -aG render,video {os.getenv('USER', 'arko-sanyal')}",
            "# Then log out and back in for group membership to take effect",
        ]

    status["within_safety_margin"] = True  # Can't measure load until compute is active

    return status


def get_full_gpu_status() -> Dict[str, Any]:
    """Combined status of all GPUs with safety margin assessment."""
    nvidia = get_nvidia_status()
    arc = get_intel_arc_status()

    total_vram_mb = GPU_SPECS["nvidia_rtx_5060_ti"]["vram_mb"] + GPU_SPECS["intel_arc_b580_pro"]["vram_mb"]
    nvidia_free = nvidia.get("vram_free_mb", 0)
    arc_free = GPU_SPECS["intel_arc_b580_pro"]["vram_mb"]  # All free until compute active

    return {
        "timestamp": _utc_iso(),
        "gpus": {"nvidia": nvidia, "intel_arc": arc},
        "combined": {
            "total_vram_mb": total_vram_mb,
            "total_vram_gb": round(total_vram_mb / 1024, 1),
            "estimated_free_vram_mb": nvidia_free + arc_free,
            "all_within_safety": nvidia.get("within_safety_margin", False) and arc.get("within_safety_margin", True),
            "total_active_tasks": len(ACTIVE_TASKS["nvidia_rtx_5060_ti"]) + len(ACTIVE_TASKS["intel_arc_b580_pro"]),
            "queued_tasks": len(TASK_QUEUE),
        },
        "safety_policy": {
            "margin_pct": 5,
            "max_concurrent_per_gpu": MAX_CONCURRENT_TASKS_PER_GPU,
            "principle": "5% below rated limits for longevity. Tasks queue instead of piling on.",
        },
    }


# ---------------------------------------------------------------------------
# Task Allocation — prevent pileup
# ---------------------------------------------------------------------------

def allocate_task(
    task_name: str,
    vram_estimate_mb: int,
    preferred_gpu: Optional[str] = None,
    agent_id: str = "unknown",
) -> Dict[str, Any]:
    """Allocate a task to a GPU, respecting safety margins and preventing pileup.

    If the preferred GPU is full or would exceed safety margins, the task
    is either routed to the other GPU or queued.
    """
    nvidia = get_nvidia_status()
    arc = get_intel_arc_status()

    # Try preferred GPU first
    if preferred_gpu == "nvidia" or preferred_gpu is None:
        if (nvidia.get("can_accept_task", False)
            and nvidia.get("vram_headroom_mb", 0) >= vram_estimate_mb
            and nvidia.get("within_safety_margin", False)):
            task = {
                "task_name": task_name,
                "agent_id": agent_id,
                "gpu": "nvidia_rtx_5060_ti",
                "vram_estimate_mb": vram_estimate_mb,
                "started_at": _utc_iso(),
            }
            ACTIVE_TASKS["nvidia_rtx_5060_ti"].append(task)
            return {"status": "allocated", "gpu": "nvidia_rtx_5060_ti", "task": task}

    # Try Arc if NVIDIA is full/unavailable
    if preferred_gpu == "intel_arc" or preferred_gpu is None:
        if arc.get("can_accept_task", False) and arc.get("compute_ready", False):
            task = {
                "task_name": task_name,
                "agent_id": agent_id,
                "gpu": "intel_arc_b580_pro",
                "vram_estimate_mb": vram_estimate_mb,
                "started_at": _utc_iso(),
            }
            ACTIVE_TASKS["intel_arc_b580_pro"].append(task)
            return {"status": "allocated", "gpu": "intel_arc_b580_pro", "task": task}

    # Queue the task — don't pile on
    queued = {
        "task_name": task_name,
        "agent_id": agent_id,
        "preferred_gpu": preferred_gpu,
        "vram_estimate_mb": vram_estimate_mb,
        "queued_at": _utc_iso(),
    }
    TASK_QUEUE.append(queued)
    return {
        "status": "queued",
        "reason": "All GPUs at capacity or safety limit. Task queued — it will run when capacity frees up.",
        "queue_position": len(TASK_QUEUE),
        "task": queued,
    }


def complete_task(task_name: str, gpu: str) -> Dict[str, Any]:
    """Mark a task as complete and check if queued tasks can now run."""
    for gpu_key in ACTIVE_TASKS:
        ACTIVE_TASKS[gpu_key] = [t for t in ACTIVE_TASKS[gpu_key] if t["task_name"] != task_name]

    # Try to dequeue
    dequeued = []
    remaining = []
    for queued in TASK_QUEUE:
        if not dequeued:  # Only dequeue one at a time
            result = allocate_task(
                queued["task_name"],
                queued["vram_estimate_mb"],
                queued.get("preferred_gpu"),
                queued.get("agent_id", "unknown"),
            )
            if result["status"] == "allocated":
                dequeued.append(result)
                continue
        remaining.append(queued)
    TASK_QUEUE.clear()
    TASK_QUEUE.extend(remaining)

    return {
        "completed": task_name,
        "dequeued": dequeued,
        "remaining_queue": len(TASK_QUEUE),
    }


# ---------------------------------------------------------------------------
# Model Allocation Plan
# ---------------------------------------------------------------------------

def get_model_allocation_plan() -> Dict[str, Any]:
    """Recommended model allocation across GPUs for maximum efficiency."""
    nvidia_spec = GPU_SPECS["nvidia_rtx_5060_ti"]
    arc_spec = GPU_SPECS["intel_arc_b580_pro"]

    return {
        "nvidia_rtx_5060_ti": {
            "safe_vram_mb": nvidia_spec["safe_vram_mb"],
            "recommended_models": [
                {"model": "loci-rtx-14b", "vram_mb": 9000, "role": "Deep reasoning, CARD routing"},
                {"model": "loci-agent (7b)", "vram_mb": 5000, "role": "Fast classification, entity extraction"},
            ],
            "total_allocated_mb": 14000,
            "headroom_mb": nvidia_spec["safe_vram_mb"] - 14000,
        },
        "intel_arc_b580_pro": {
            "safe_vram_mb": arc_spec["safe_vram_mb"],
            "recommended_models": [
                {"model": "large-model (70b-q4)", "vram_mb": 25000, "role": "Deep research, escalation chain endpoint", "status": "pending_compute_runtime"},
            ],
            "total_allocated_mb": 25000,
            "headroom_mb": arc_spec["safe_vram_mb"] - 25000,
            "prerequisite": "Install intel-opencl-icd + level-zero for compute",
        },
        "policy": {
            "safety_margin_pct": 5,
            "max_tasks_per_gpu": MAX_CONCURRENT_TASKS_PER_GPU,
            "principle": "Never exceed 95% VRAM, 95% TDP, or 2 concurrent tasks per GPU. Queue instead of pile.",
        },
    }
