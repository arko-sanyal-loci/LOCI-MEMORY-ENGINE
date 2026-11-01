#!/usr/bin/env bash
# LOCI Ollama Environment — Safety-constrained model serving
# Source this before starting Ollama for optimal multi-GPU allocation
#
# Usage: source config/ollama_env.sh && ollama serve

# GPU allocation
export CUDA_VISIBLE_DEVICES="0"           # NVIDIA RTX 5060 Ti only (for now)
export ZE_AFFINITY_MASK="0"               # Intel Arc B70 Pro (when compute runtime installed)

# Model loading constraints — prevent VRAM pileup
export OLLAMA_MAX_LOADED_MODELS="2"       # Max 2 models in VRAM simultaneously
export OLLAMA_NUM_PARALLEL="1"            # 1 request at a time per model
export OLLAMA_CONTEXT_LENGTH="8192"       # Conservative context window

# Networking — keep Ollama localhost-only, proxy through sovereign engine
export OLLAMA_HOST="127.0.0.1:11434"      # Never bind to 0.0.0.0

# Memory
export OLLAMA_KEEP_ALIVE="10m"            # Unload idle models after 10 minutes

echo "LOCI Ollama env loaded: CUDA=$CUDA_VISIBLE_DEVICES, max_models=$OLLAMA_MAX_LOADED_MODELS, host=$OLLAMA_HOST"
