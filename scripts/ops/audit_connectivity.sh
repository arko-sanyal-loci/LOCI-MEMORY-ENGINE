#!/usr/bin/env bash
# scripts/audit_connectivity.sh
# Run ON the VPS ($VPS_HOST) or on the Ubuntu console node.
# Checks SSH, firewall, OS config, and reachability for all cluster nodes.
# Usage: bash scripts/ops/audit_connectivity.sh
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_nodes.sh"

PASS=0; WARN=0; FAIL=0
_ok()   { echo "  [PASS] $*"; ((PASS++)); }
_warn() { echo "  [WARN] $*"; ((WARN++)); }
_fail() { echo "  [FAIL] $*"; ((FAIL++)); }

section() { echo; echo "=== $* ==="; }

# ---------------------------------------------------------------------------
section "1. SSH DAEMON CONFIGURATION"
# ---------------------------------------------------------------------------
SSHD_CFG="/etc/ssh/sshd_config"
if [ ! -f "$SSHD_CFG" ]; then
    _fail "sshd_config not found at $SSHD_CFG"
else
    check_sshd() {
        local key="$1" want="$2"
        local val
        val=$(grep -iE "^\s*${key}\s" "$SSHD_CFG" | awk '{print $2}' | tail -1)
        if [ -z "$val" ]; then
            _warn "$key not explicitly set (default may apply) — expected: $want"
        elif [[ "${val,,}" == "${want,,}" ]]; then
            _ok "$key = $val"
        else
            _fail "$key = $val  (expected: $want)"
        fi
    }
    check_sshd "PasswordAuthentication"    "no"
    check_sshd "PubkeyAuthentication"      "yes"
    check_sshd "PermitEmptyPasswords"      "no"
    check_sshd "X11Forwarding"             "no"
    check_sshd "MaxAuthTries"              "3"
    check_sshd "LoginGraceTime"            "30"
    check_sshd "Protocol"                  "2"

    # PermitRootLogin: prohibit-password is fine (key-only root); 'yes' is not
    ROOT_LOGIN=$(grep -iE "^\s*PermitRootLogin\s" "$SSHD_CFG" | awk '{print $2}' | tail -1)
    if [[ "${ROOT_LOGIN,,}" == "yes" ]]; then
        _fail "PermitRootLogin = yes — password root login is open; set to prohibit-password"
    elif [[ "${ROOT_LOGIN,,}" == "prohibit-password" || "${ROOT_LOGIN,,}" == "without-password" ]]; then
        _ok "PermitRootLogin = $ROOT_LOGIN (key-only root: acceptable)"
    elif [[ "${ROOT_LOGIN,,}" == "no" ]]; then
        _ok "PermitRootLogin = no"
    else
        _warn "PermitRootLogin = '${ROOT_LOGIN:-unset}' — expected prohibit-password or no"
    fi

    # Check authorized_keys exist for root
    if [ -f /root/.ssh/authorized_keys ]; then
        KEY_COUNT=$(wc -l < /root/.ssh/authorized_keys)
        _ok "root authorized_keys exists ($KEY_COUNT line(s))"
    else
        _fail "/root/.ssh/authorized_keys missing — key-only login will not work"
    fi

    # Check .arc_keys directory
    if [ -d /root/.arc_keys ]; then
        ARC_KEY_COUNT=$(find /root/.arc_keys -type f | wc -l)
        _ok "/root/.arc_keys exists ($ARC_KEY_COUNT file(s))"
    else
        _warn "/root/.arc_keys directory missing — expected from SCP provisioning"
    fi

    # Check sshd is running
    if systemctl is-active --quiet sshd 2>/dev/null || systemctl is-active --quiet ssh 2>/dev/null; then
        _ok "sshd service is active"
    else
        _fail "sshd service is NOT active"
    fi
fi

# ---------------------------------------------------------------------------
section "2. FIREWALL (UFW)"
# ---------------------------------------------------------------------------
if command -v ufw >/dev/null 2>&1; then
    UFW_STATUS=$(ufw status | head -1)
    if echo "$UFW_STATUS" | grep -qi "active"; then
        _ok "UFW is active"
        # SSH should be allowed
        if ufw status | grep -qiE "OpenSSH|22/tcp|22 "; then
            _ok "UFW allows SSH (port 22)"
        else
            _fail "UFW has no rule allowing SSH — you may lock yourself out on next reload"
        fi
    else
        _warn "UFW is installed but INACTIVE — consider: ufw allow OpenSSH && ufw enable"
    fi
else
    _warn "UFW not installed (consider: apt install ufw)"
fi

# ---------------------------------------------------------------------------
section "3. FAIL2BAN"
# ---------------------------------------------------------------------------
if command -v fail2ban-client >/dev/null 2>&1; then
    if systemctl is-active --quiet fail2ban 2>/dev/null; then
        _ok "fail2ban is active"
        if fail2ban-client status sshd >/dev/null 2>&1; then
            BANNED=$(fail2ban-client status sshd | grep "Currently banned" | awk '{print $NF}')
            _ok "fail2ban sshd jail active (currently banned: $BANNED)"
        else
            _warn "fail2ban running but sshd jail not active — check /etc/fail2ban/jail.local"
        fi
    else
        _warn "fail2ban installed but not running — systemctl enable --now fail2ban"
    fi
else
    _warn "fail2ban not installed (consider: apt install fail2ban)"
fi

# ---------------------------------------------------------------------------
section "4. OS / PACKAGE UPDATES"
# ---------------------------------------------------------------------------
if command -v apt >/dev/null 2>&1; then
    apt-get update -qq 2>/dev/null || _warn "apt update failed (network issue?)"
    UPGRADEABLE=$(apt list --upgradeable 2>/dev/null | grep -c upgradeable || true)
    if [ "$UPGRADEABLE" -gt 0 ]; then
        _warn "$UPGRADEABLE package(s) upgradeable — run: apt upgrade -y"
    else
        _ok "All packages up to date"
    fi

    # unattended-upgrades
    if dpkg -l unattended-upgrades 2>/dev/null | grep -q "^ii"; then
        _ok "unattended-upgrades installed"
    else
        _warn "unattended-upgrades not installed — consider: apt install unattended-upgrades"
    fi
fi

# ---------------------------------------------------------------------------
section "5. NODE REACHABILITY"
# ---------------------------------------------------------------------------
check_host() {
    local label="$1" host="$2"
    if [ -z "$host" ]; then _warn "$label: not set in nodes.env"; return; fi
    if ping -c 1 -W 2 "$host" >/dev/null 2>&1; then
        if nc -z -w 2 "$host" 22 2>/dev/null; then
            _ok "$label ($host): reachable, port 22 open"
        else
            _warn "$label ($host): pingable but port 22 closed/filtered"
        fi
    else
        _warn "$label ($host): unreachable (offline or blocked by firewall)"
    fi
}
check_host "Workstation"  "${WORKSTATION_IP:-}"
check_host "Console"      "${CONSOLE_IP:-}"
check_host "Mac Mini"     "${MAC_MINI_IP:-}"

# GitHub SSH reachability (needed for node_sync.sh / git push)
if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -T git@github.com 2>&1 \
   | grep -q "successfully authenticated"; then
    _ok "GitHub SSH auth: authenticated"
else
    _warn "GitHub SSH auth: not authenticated or timed out — ensure deploy key / personal key is loaded"
fi

# ---------------------------------------------------------------------------
section "6. LOCI SERVICE"
# ---------------------------------------------------------------------------
if systemctl is-active --quiet loci-mcp 2>/dev/null || systemctl is-active --quiet loci-engine 2>/dev/null; then
    _ok "loci service is active"
else
    _warn "loci service not active — check systemd/loci-mcp.service; run: systemctl status loci-mcp"
fi

# Workspace path
VPS_WS="${VPS_PATH:-$LOCI_REPO_DIR}"
if [ -d "$VPS_WS" ]; then
    _ok "VPS workspace exists: $VPS_WS"
    if [ -f "$VPS_WS/manifest.sha256" ]; then
        _ok "manifest.sha256 present"
    else
        _warn "manifest.sha256 missing from workspace"
    fi
else
    _warn "VPS workspace $VPS_WS not found (run scripts/propagate_engine.sh?)"
fi

# ---------------------------------------------------------------------------
section "7. SUMMARY"
# ---------------------------------------------------------------------------
echo
echo "  PASS: $PASS   WARN: $WARN   FAIL: $FAIL"
echo
if [ "$FAIL" -gt 0 ]; then
    echo "  ACTION REQUIRED: $FAIL critical issue(s) above need fixing."
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo "  System is functional but $WARN item(s) should be reviewed."
    exit 0
else
    echo "  All checks passed."
    exit 0
fi
