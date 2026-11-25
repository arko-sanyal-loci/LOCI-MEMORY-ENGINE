"""
Configuration settings for Billo and LOCI deployment.
"""

import os
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = os.getenv("BILLO_DB_PATH", str(DATA_DIR / "context2.db"))

# LLM Providers
OLLAMA_GPU_URL = os.getenv("OLLAMA_GPU_URL", "http://localhost:11434")
OLLAMA_VPS_TUNNEL = os.getenv("OLLAMA_VPS_TUNNEL", "http://localhost:11435")
OLLAMA_VPS_DIRECT = os.getenv("OLLAMA_VPS_DIRECT", "http://127.0.0.1:11434")

MODEL_GPU = os.getenv("MODEL_GPU", "qwen2.5-coder:14b")
MODEL_VPS = os.getenv("MODEL_VPS", "qwen2.5:3b")

TIMEOUT_VPS_COMPRESS = float(os.getenv("TIMEOUT_VPS_COMPRESS", "60.0"))

# Network & Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
SOCKET_PATH = os.getenv("SOCKET_PATH", None)

DOMAIN = os.getenv("DOMAIN", "billo.tech")
ARC_DOMAIN = os.getenv("ARC_DOMAIN", "arc.billo.tech")

# Hardware detection
IS_GPU_WORKSTATION = (platform.system() == "Windows") and (os.path.exists("F:\\Billo") or os.getenv("FORCE_GPU_WORKSTATION", "0") == "1")
