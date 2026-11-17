---
name: loci-defense
description: Defensive countermeasures for AI-mediated attacks on macOS — HID injection detection (ReiKey/KnockKnock/tccutil), MCP session hijack detection (file integrity + baseline hashes), AI-authored backdoor code review, PHP webshell YARA/grep sweeps. Use when: mouse/keyboard moving on its own, suspected computer-use MCP compromise, reviewing AI-written PRs, sweeping a webroot for backdoors, running Safe Mode ViewBridge origin test.
---

# LOCI Defense — Skill

Research assembled 2026-08-03 during active attack on Arko Sanyal. Concrete terminal commands, macOS-specific. Full brief follows; use section headers to jump.

## 1. HID injection countermeasures (`CGEventTapCreate` taps)

**Immediate — enumerate every event tap:**
```bash
brew install --cask reikey knockknock lulu
/Applications/ReiKey.app/Contents/MacOS/ReiKey -scan -pretty
```
Anything with `kCGEventMaskForAllEvents` or `kCGKeyDown|kCGKeyUp` from a source you don't recognize is suspect. Leave ReiKey running as a background monitor.

**Cross-check HID-plane clients:**
```bash
sudo ioreg -p IOHID -l -w 0 | grep -Ei 'client|hid|user'
sudo lsof -c '' | grep -i '/dev/console\|WindowServer\|CoreGraphics\|HID' | head -50
sudo fs_usage -w -f filesys | grep -i hid
```

**Enumerate TCC event grants (user DB — no sudo needed):**
```bash
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  "SELECT service, client, auth_value, datetime(last_modified,'unixepoch','localtime')
     FROM access
    WHERE service IN ('kTCCServicePostEvent','kTCCServiceListenEvent',
                      'kTCCServiceAccessibility','kTCCServiceAppleEvents')
    ORDER BY last_modified DESC;"
```
`auth_value >= 2` = granted. Anything granted between 2026-07-20 and now that you didn't approve = prime suspect. System DB at `/Library/Application Support/com.apple.TCC/TCC.db` needs FDA on Terminal.

**Revoke cleanly (no SIP disable required):**
```bash
tccutil reset PostEvent            # all apps
tccutil reset PostEvent <bundle-id>
tccutil reset ListenEvent
tccutil reset Accessibility
tccutil reset AppleEvents
tccutil reset All                  # nuclear
```

**Find persistence:**
```bash
sudo launchctl list | grep -v com.apple
find /Library/LaunchAgents /Library/LaunchDaemons ~/Library/LaunchAgents /Library/StartupItems \
     -type f -mtime -30 -ls 2>/dev/null
```
Then run KnockKnock (30+ persistence categories, VT-cross-refs each binary).

**Safe Mode — what it actually kills:** loads only Apple-signed kexts, skips `/Library/LaunchAgents`, `/Library/LaunchDaemons`, `~/Library/LaunchAgents`, login/startup items. Attacker taps die because their persistence doesn't fire. TCC grants **survive** Safe Mode. Boot Safe Mode (Apple Silicon: power → Options → hold Shift + Continue in Safe Mode), re-run the TCC query, re-run `sudo launchctl list` — anything present is either Apple's or has abused an Apple-signed loader.

**Bluetooth HID = real covert vector** (Marc Newlin CVE-2024-0230, "BLURtooth/Magic Keyboard"). Even patched macOS Sonoma 14.2+ has already-paired devices as a legitimate injection surface if RF is bridged. Kill it while working:
```bash
sudo defaults write /Library/Preferences/com.apple.Bluetooth ControllerPowerState -int 0
sudo killall bluetoothd
system_profiler SPBluetoothDataType | grep -A2 'Connected'
```
If pointer moves stop when BT is off = confirmed channel. If they continue = local process `CGEventPost` (see TCC.db above).

---

## 2. Detecting `computer-use` MCP session hijack

**Baseline hashes NOW (before touching anything):**
```bash
mkdir -p /Volumes/DevDrive/LOCI/baselines
find ~/.claude ~/.claude.json ~/.config/claude* \
     ~/Library/Application\ Support/Claude \
     ~/Library/Preferences/com.anthropic.* \
     -type f 2>/dev/null | xargs -I{} shasum -a 256 "{}" \
  > /Volumes/DevDrive/LOCI/baselines/claude-$(date +%Y%m%d-%H%M).sha256
```

**Diff on schedule:**
```bash
find ~/.claude ~/.claude.json ~/Library/Application\ Support/Claude -type f 2>/dev/null \
  | xargs shasum -a 256 | diff - /Volumes/DevDrive/LOCI/baselines/claude-*.sha256
```

**Inspect MCP config for injected servers:**
```bash
jq '.mcpServers' ~/.claude.json
jq '.mcpServers' ~/.claude.json | grep -i 'command\|args\|url'
find . -name '.mcp.json' -not -path '*/node_modules/*'
```
Watch for (a) added attacker-controlled server, (b) modified `command` wrapping the real binary, (c) `type` swap from `stdio` to `http`/`sse` on `127.0.0.1:<port>`.

**Also inspect:** `~/.claude/settings.json`, `~/.claude/settings.local.json`, project `.claude/settings.local.json`, and every `CLAUDE.md` (highest value for an attacker — always read into context).

**Verify MCP server binary:**
```bash
ps -ef | grep -i 'computer-use\|mcp' | grep -v grep
lsof -p <PID> | head
codesign -dv --verbose=4 <path>
spctl -a -vv <path>
xattr -l <path>
npm ls -g --depth=0 | grep -i mcp
npm audit signatures       # Sigstore attestations, npm 9.5+
```

**Reinstall + pin to absolute path** (relative `command` = trivial PATH-shim hijack):
```bash
claude mcp remove computer-use
claude mcp add computer-use --command /abs/path/to/verified-binary
```

**Scrubbed env** for Claude Code (kills library-injection hijacks):
```bash
env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/local/bin claude
```

**Firewall listeners:**
```bash
brew install --cask lulu
sudo lsof -iTCP -sTCP:LISTEN -n -P | grep -v '^launchd\|^rapportd\|^ControlCe\|^cfprefsd'
```

---

## 3. Defending code review against AI-authored backdoors

**AI-planted-backdoor signatures (2025-26 incident corpus):**
1. **Extra dependency** with nothing to do with the change — typosquat name.
2. **Silent network egress** in build/postinstall — `curl`, `wget`, `fetch(`, `http.request`, `urllib`, `net.connect`, `child_process.spawn`, `os.system`, `eval(`, base64 blobs.
3. **Unicode homoglyphs / bidi controls** in identifiers. `LC_ALL=C grep -P '[^\x00-\x7f]' <file>` — anything lit in code (not strings) is suspicious.
4. **"Refactor" that flips an auth check** by one operator (`==` → `!=`, `&&` → `||`).
5. **Environment-conditional behavior** (`if os.environ.get('CI')` / `if hostname == '…'`).
6. **Widened permissions** — new IAM statements, `chmod 777`, listing on a private bucket, CORS `*`.
7. **New config file** (`.env.example` with real-looking secrets, new `.github/workflows/*.yml`, an `mcp.json`).

**Install today:**
```bash
brew install gitleaks trufflehog semgrep syft grype cosign pip-audit ent yara
npm i -g @cyclonedx/cdxgen
```

**Per repo:**
```bash
gitleaks detect --no-git -v .
trufflehog filesystem . --only-verified
semgrep --config auto .
syft . -o cyclonedx-json > sbom.json && grype sbom:./sbom.json
```

**Supply-chain hardening:**
```bash
npm audit signatures                              # verifies attestations
npm audit --audit-level=high                       # fail CI on high
pip-audit -r requirements.txt --strict
pip install --require-hashes -r requirements.txt
cosign sign --yes <image>
cosign verify --certificate-identity-regexp '.*' <image>
```

**Signed commits (YubiKey ed25519):**
```bash
git config --global commit.gpgsign true
git config --global tag.gpgsign true
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519_yubikey.pub
git log --show-signature
```

**PHP webshell sweep (extends `Generic.PHP.Backdoor.M/N/L`):**
```bash
grep -RIn --include='*.php' --include='*.phtml' --include='*.inc' -E \
  'eval\s*\(\s*(base64_decode|gzinflate|gzuncompress|str_rot13|hex2bin|pack)|\b(assert|create_function|preg_replace)\s*\([^)]*/e|\b(shell_exec|system|passthru|proc_open|popen|exec|pcntl_exec)\s*\(|\$_(GET|POST|REQUEST|COOKIE|SERVER)\s*\[[^]]*\]\s*\([^)]*\)|FilesMan|WSO|c99sh|r57shell|b374k|weevely|IndoXploit|Alfa Team|MadSpot|die\s*\(\s*md5\s*\(|goto\s+[A-Za-z_]+\s*;|@\$[a-z]+=\s*"[a-zA-Z0-9+/=]{80,}"' \
  /path/to/webroot

# Files edited in the compromise window:
find /path/to/webroot -type f -newermt 2026-07-20 ! -newermt 2026-07-30 \
     \( -name '*.php' -o -name '*.phtml' -o -name '.htaccess' \) -ls

# High-entropy PHP (obfuscated shells score >5.5):
find /path/to/webroot -name '*.php' -exec sh -c \
  'e=$(ent -t "$1" 2>/dev/null | tail -1 | cut -d, -f2); \
   awk -v e="$e" -v f="$1" "BEGIN{if(e+0>5.5)print e\"\t\"f}"' _ {} \;

# YARA — community rules:
git clone https://github.com/Neo23x0/signature-base /tmp/sigbase
yara -r /tmp/sigbase/yara/gen_webshells.yar /path/to/webroot

# WordPress/Magento diff against upstream:
wp core verify-checksums
wp plugin verify-checksums --all
```

---

## Sources
- Objective-See: [ReiKey](https://objective-see.org/products/reikey.html), [KnockKnock](https://objective-see.org/products/knockknock.html), [LuLu](https://objective-see.org/products/lulu.html)
- [HackTricks — macOS Input Monitoring / TCC](https://hacktricks.wiki/en/macos-hardening/macos-security-and-privilege-escalation/macos-security-protections/macos-input-monitoring-screen-capture-accessibility.html)
- [Apple — Securely extending the kernel](https://support.apple.com/guide/security/securely-extending-the-kernel-sec8e454101b/web)
- [Marc Newlin BT keystroke injection](https://www.hackster.io/news/marc-newlin-s-keyboard-spoofing-attack-sends-arbitrary-commands-to-android-ios-macos-and-linux-21a738d6f548)
- [OWASP MCP Security Cheatsheet](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)
- [CSA Labs — MCP Security Crisis (2026)](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-security-crisis-20260504-csa-styled/)
- [Arnica — AI Code Security CISO Guide (Jul 2026)](https://www.arnica.io/blog/ai-code-security-complete-guide)
- [Neo23x0/signature-base — gen_webshells.yar](https://github.com/Neo23x0/signature-base/blob/master/yara/gen_webshells.yar)
- [Sucuri Labs — PHP backdoor generic webshell 001](https://labs.sucuri.net/signatures/malwares/php-backdoor-generic-webshell-001/)
