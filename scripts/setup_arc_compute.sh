#!/usr/bin/env bash
# Intel Arc B70 Pro Sparkle — Compute Runtime Setup
# Run with: sudo bash scripts/setup_arc_compute.sh
set -euo pipefail

echo "=== LOCI Intel Arc B70 Pro Sparkle Compute Setup ==="
echo ""

# 1. Add user to render + video groups for DRI access
echo "[1/4] Adding arko-sanyal to render and video groups..."
usermod -aG render,video arko-sanyal
echo "  Done. Groups: render, video"

# 2. Install Intel OpenCL runtime (for non-Ollama compute like clinfo)
echo "[2/4] Installing Intel compute packages..."
apt-get install -y intel-opencl-icd intel-gpu-tools clinfo
echo "  Done."

# 3. Verify Vulkan sees the Battlemage GPU
echo "[3/4] Checking Vulkan enumeration..."
if command -v vulkaninfo &>/dev/null; then
    su - arko-sanyal -c "vulkaninfo --summary 2>&1 | grep -i 'deviceName\|driverName'" || echo "  (vulkaninfo may need re-login for group membership)"
else
    echo "  vulkaninfo not installed — install vulkan-tools for diagnostics"
fi

# 4. Create systemd unit for Arc Ollama instance
echo "[4/4] Installing loci-ollama-arc systemd service..."
cat > /etc/systemd/system/loci-ollama-arc.service <<'UNIT'
[Unit]
Description=LOCI Ollama — Intel Arc B70 Pro (Vulkan)
After=network.target
Wants=network.target

[Service]
Type=simple
User=arko-sanyal
Environment=OLLAMA_HOST=127.0.0.1:11435
Environment=OLLAMA_MODELS=/home/arko-sanyal/.ollama/models
Environment=OLLAMA_MAX_LOADED_MODELS=1
Environment=OLLAMA_NUM_PARALLEL=1
Environment=OLLAMA_CONTEXT_LENGTH=8192
Environment=OLLAMA_KEEP_ALIVE=10m
Environment=OLLAMA_GPU_LAYER=99
Environment=CUDA_VISIBLE_DEVICES=
Environment=GGML_VK_VISIBLE_DEVICES=1
ExecStart=/usr/bin/ollama serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
echo "  Service installed: loci-ollama-arc"
echo ""
echo "=== Setup Complete ==="
echo ""
echo "IMPORTANT: Log out and back in for group membership to take effect."
echo ""
echo "Then start the Arc Ollama instance:"
echo "  sudo systemctl start loci-ollama-arc"
echo "  sudo systemctl enable loci-ollama-arc"
echo ""
echo "Verify with:"
echo "  curl http://localhost:11435/api/tags"
echo "  OLLAMA_HOST=127.0.0.1:11435 ollama run loci-agent 'hello'"
