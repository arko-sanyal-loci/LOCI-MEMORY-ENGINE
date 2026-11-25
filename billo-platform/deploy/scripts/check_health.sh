#!/usr/bin/env bash
# ==============================================================================
# check_health.sh - Diagnostic script for Billo & LOCI deployment
# ==============================================================================
set -euo pipefail

echo "=== 1. Checking System Services ==="
systemctl is-active billo-api.service && echo "billo-api: ACTIVE" || echo "billo-api: INACTIVE"
systemctl is-active billo-worker.service && echo "billo-worker: ACTIVE" || echo "billo-worker: INACTIVE"
systemctl is-active nginx.service && echo "nginx: ACTIVE" || echo "nginx: INACTIVE"
systemctl is-active ollama.service && echo "ollama: ACTIVE" || echo "ollama: INACTIVE"

echo ""
echo "=== 2. Checking Unix Socket ==="
if [ -S /run/billo/billo.sock ]; then
    echo "Unix socket /run/billo/billo.sock exists and is accessible."
else
    echo "Unix socket /run/billo/billo.sock NOT found!"
fi

echo ""
echo "=== 3. Checking Database WAL Mode ==="
DB_PATH="/opt/billo/data/context2.db"
if [ -f "$DB_PATH" ]; then
    JOURNAL_MODE=$(sqlite3 "$DB_PATH" "PRAGMA journal_mode;")
    echo "context2.db journal_mode: $JOURNAL_MODE"
    if [ "$JOURNAL_MODE" = "wal" ]; then
        echo "PASS: WAL mode active."
    else
        echo "WARN: WAL mode not active."
    fi
else
    echo "Database $DB_PATH not found."
fi

echo ""
echo "=== 4. Checking Ollama Local Models ==="
curl -s http://127.0.0.1:11434/api/tags | grep -o '"name":"[^"]*"' || echo "No models or Ollama offline."

echo ""
echo "=== 5. Querying API Health Endpoint ==="
curl -s --unix-socket /run/billo/billo.sock http://localhost/api/health || curl -s http://127.0.0.1:8000/api/health || echo "API not responding."
echo ""
