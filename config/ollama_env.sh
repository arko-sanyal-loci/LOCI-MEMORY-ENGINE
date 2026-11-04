#!/usr/bin/env bash
# LOCI Dual-GPU Ollama Environment
#
# Two Ollama instances, one per GPU:
#   :11434 — NVIDIA RTX 5060 Ti (CUDA) — fast inference, ≤14B models
#   :11435 — Intel Arc B70 Pro Sparkle (Vulkan) — large models, overflow
#
# Usage:
#   source config/ollama_env.sh nvidia   # for NVIDIA instance (default)
#   source config/ollama_env.sh arc      # for Arc instance

GPU_TARGET="${1:-nvidia}"

# Shared constraints
export OLLAMA_MAX_LOADED_MODELS="2"
export OLLAMA_NUM_PARALLEL="1"
export OLLAMA_CONTEXT_LENGTH="8192"
export OLLAMA_KEEP_ALIVE="10m"

if [ "$GPU_TARGET" = "arc" ]; then
    export OLLAMA_HOST="127.0.0.1:11435"
    export CUDA_VISIBLE_DEVICES=""
    export GGML_VK_VISIBLE_DEVICES="1"
    export OLLAMA_GPU_LAYER="99"
    echo "LOCI Ollama [Arc B70 Pro Sparkle / Vulkan] → :11435"
else
    export OLLAMA_HOST="127.0.0.1:11434"
    export CUDA_VISIBLE_DEVICES="0"
    unset GGML_VK_DEVICE GGML_VK_VISIBLE_DEVICES 2>/dev/null
    echo "LOCI Ollama [NVIDIA RTX 5060 Ti / CUDA] → :11434"
fi
