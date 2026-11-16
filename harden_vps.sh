#!/usr/bin/env bash
# scripts/harden_vps.sh
# Run ONCE on the VPS as root to apply SSH hardening and OS baseline.
# Safe to re-run — all changes are idempotent.
# Usage: bash scripts/harden_vps.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: must be run as root"
    exit 1
fi

echo "=== LOCI VPS Hardening Baseline ==="

# ---------------------------------------------------------------------------
# 1. SSH DAEMON HARDENING
# ---------------------------------------------------------------------------
echo
echo "[1/5] Hardening sshd_config..."
SSHD_CFG="/etc/ssh/sshd_config"
BACKUP="/etc/ssh/sshd_config.bak.$(date +%Y%m%d%H%M%S)"
cp "$SSHD_CFG" "$BACKUP"
echo "  Backed up to $BACKUP"

apply_sshd() {
    local key="$1" value="$2"
    # If key already present (commented or not), replace the first occurrence
    if grep -qiE "^\s*#?\s*${key}\s" "$SSHD_CFG"; then
        sed -i -E "s|^\s*#?\s*${key}\s.*|${key} ${value}|I" "$SSHD_CFG"
    else
        echo "${key} ${value}" >> "$SSHD_CFG"
    fi
    echo "  $key = $value"
}

apply_sshd "PasswordAuthentication"  "no"
apply_sshd "PubkeyAuthentication"    "yes"
apply_sshd "PermitEmptyPasswords"    "no"
apply_sshd "PermitRootLogin"         "prohibit-password"
apply_sshd "X11Forwarding"           "no"
apply_sshd "MaxAuthTries"            "3"
apply_sshd "LoginGraceTime"          "30"
apply_sshd "ClientAliveInterval"     "120"
apply_sshd "ClientAliveCountMax"     "3"
apply_sshd "UseDNS"                  "no"
apply_sshd "PrintLastLog"            "yes"

# Validate config before restarting
if sshd -t; then
    echo "  sshd config valid — restarting..."
    systemctl restart sshd || systemctl restart ssh
    echo "  sshd restarted OK"
else
    echo "  ERROR: sshd config invalid — restoring backup"
    cp "$BACKUP" "$SSHD_CFG"
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. ARC KEYS DIRECTORY
# ---------------------------------------------------------------------------
echo
echo "[2/5] Ensuring /root/.arc_keys/ exists with correct permissions..."
mkdir -p /root/.arc_keys
chmod 700 /root/.arc_keys
echo "  /root/.arc_keys created (chmod 700)"

mkdir -p /root/.ssh
chmod 700 /root/.ssh
[ -f /root/.ssh/authorized_keys ] && chmod 600 /root/.ssh/authorized_keys || touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys
echo "  /root/.ssh/authorized_keys ensured (chmod 600)"

# ---------------------------------------------------------------------------
# 3. UFW FIREWALL
# ---------------------------------------------------------------------------
echo
echo "[3/5] Configuring UFW firewall..."
if command -v ufw >/dev/null 2>&1; then
    # Ensure SSH is allowed BEFORE enabling — prevent lockout
    ufw allow OpenSSH comment "LOCI baseline: SSH" 2>/dev/null || true
    # Allow MCP server port if defined
    ufw allow 8765/tcp comment "LOCI MCP server" 2>/dev/null || true
    ufw --force enable
    ufw status verbose
    echo "  UFW enabled with SSH allowed"
else
    apt-get install -y ufw
    ufw allow OpenSSH
    ufw --force enable
    echo "  UFW installed and enabled"
fi

# ---------------------------------------------------------------------------
# 4. FAIL2BAN
# ---------------------------------------------------------------------------
echo
echo "[4/5] Configuring fail2ban for SSH..."
if ! command -v fail2ban-client >/dev/null 2>&1; then
    apt-get install -y fail2ban
fi

JAIL_LOCAL="/etc/fail2ban/jail.local"
if [ ! -f "$JAIL_LOCAL" ]; then
    cat > "$JAIL_LOCAL" << 'EOF'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3
backend  = systemd

[sshd]
enabled  = true
port     = ssh
logpath  = %(sshd_log)s
EOF
    echo "  Created $JAIL_LOCAL"
fi

systemctl enable --now fail2ban
systemctl restart fail2ban
sleep 2
fail2ban-client status sshd && echo "  fail2ban sshd jail active" || echo "  WARNING: sshd jail not running yet"

# ---------------------------------------------------------------------------
# 5. UNATTENDED UPGRADES
# ---------------------------------------------------------------------------
echo
echo "[5/5] Enabling unattended-upgrades for security patches..."
apt-get install -y unattended-upgrades apt-listchanges
# Enable automatic security updates
cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
echo "  Unattended security upgrades enabled"

# ---------------------------------------------------------------------------
echo
echo "=== VPS HARDENING COMPLETE ==="
echo "Run scripts/audit_connectivity.sh to verify all checks pass."
