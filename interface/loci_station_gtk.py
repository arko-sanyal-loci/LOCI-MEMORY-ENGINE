#!/usr/bin/env python3
"""
loci_station_gtk.py — standalone LOCI desktop interface, native Wayland

Rewritten from the Tkinter version after confirming XWayland is not
installed on station-0 (journalctl: "Failed to execute child process
/usr/bin/Xwayland (No such file or directory)"). Tkinter is an X11
toolkit and needs XWayland as a compatibility bridge even on Wayland
sessions — rather than install that bridge just to run an X11 app on a
native-Wayland GNOME desktop, this uses GTK4 (PyGObject), which talks to
the Wayland compositor directly. No X11, no XWayland, no browser.

Needs: sudo apt install -y python3-gi gir1.2-gtk-4.0

Same honesty rules as before — nothing here changed:
  - Arc fan/temp: direct kernel sysfs read (bypasses `sensors`, which was
    confirmed wrong by ~30% for this chip's fan channel)
  - Arc util/VRAM-in-use: "—" unless xpu-smi or intel_gpu_top is installed
  - RTX: real values from nvidia-smi

Ethics: NOT a gate. Corrected 2026-11-04 — the loci-memory-engine ethics
core (StickPrincipleValenceGate, repo arko-sanyal-loci/LOCI-MEMORY-ENGINE) is
a guidance layer that shapes how accumulated knowledge is APPLIED, not a
checkpoint that blocks a message. Every message to arc_agent or qwen_14b
("all models using the infinite knowledge + memory") is scored for real
via the actual tested score_vexec() and the result (v_exec, any redirect
suggestion) is shown under the exchange — it informs, it never blocks.
Requires a real clone of loci-memory-engine on this machine:
  git clone https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE ~/loci-memory-engine

Run:  python3 loci_station_gtk.py
"""
import glob
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Pango

ARC_ENDPOINT = "http://127.0.0.1:11435/v1/chat/completions"
QWEN_ENDPOINT = "http://127.0.0.1:11434/api/generate"
QWEN_MODEL = "loci-agent-14b-qwen3"

# ─── Real ethics core (loci-memory-engine), not a vendored copy ──────────
LOCI_ENGINE_PATH = os.path.expanduser("~/loci-memory-engine")
sys.path.insert(0, LOCI_ENGINE_PATH)
try:
    from loci_engine.unified_core import StickPrincipleValenceGate
    ETHICS_CORE_AVAILABLE = True
except Exception as _e:
    ETHICS_CORE_AVAILABLE = False
    ETHICS_CORE_IMPORT_ERROR = str(_e)


# Heuristic classification of how the knowledge in this message would be
# APPLIED — this picks the application_point, which is what the Stick
# Principle actually keys valence off of (same knowledge, different vector).
# Deliberately conservative and simple; same honesty disclaimer as always:
# this is pattern-matching, not comprehension of intent.
_DESTRUCTIVE = ["rm -rf", "dd if=", "mkfs", "shred ", "> /etc/", ":(){ :|:& };:"]
_CREDENTIAL = ["authorized_keys", "private key", "api key", "ssh key", "password for", "exfiltrat"]
_HARDENING = ["harden", "lock down", "patch", "secure the", "fix the vulnerab"]
_CONFIG = ["configure", "set up", "install", "deploy", "change the setting"]


def classify_application_point(text: str):
    t = text.lower()
    if any(p in t for p in _DESTRUCTIVE):
        return "unverified_destructive_command", -0.6, 0.2
    if any(p in t for p in _CREDENTIAL):
        return "unauthorized_credential_exfiltration", -0.6, 0.2
    if any(p in t for p in _HARDENING):
        return "active_system_hardening", 0.4, 0.9
    if any(p in t for p in _CONFIG):
        return "precision_configuration_patch", 0.3, 0.9
    # ordinary chat/question — knowledge being discussed, not executed
    return "education_comprehension", 0.2, 0.9


def ethics_guidance(text: str):
    if not ETHICS_CORE_AVAILABLE:
        return {"ok": False, "error": ETHICS_CORE_IMPORT_ERROR}
    application_point, intent, consent = classify_application_point(text)
    result = StickPrincipleValenceGate.score_vexec(
        knowledge_k=text, application_point=application_point,
        intent=intent, consent=consent,
    )
    result["ok"] = True
    return result


# ─── Real telemetry (identical logic to the Tkinter/web versions) ────────

def find_arc_hwmon_dir():
    for name_path in glob.glob("/sys/class/hwmon/hwmon*/name"):
        try:
            with open(name_path) as f:
                if f.read().strip() == "xe":
                    return name_path.rsplit("/", 1)[0]
        except Exception:
            continue
    return None


def read_arc_sensors():
    out = {"temp_c": None, "fan_rpm": None, "power_cap_w": None,
           "vram_temp_c": None, "util_pct": None, "vram_used_gb": None,
           "vram_total_gb": 32}
    hwmon_dir = find_arc_hwmon_dir()
    if hwmon_dir is None:
        return out

    def read_int(path):
        try:
            with open(path) as f:
                return int(f.read().strip())
        except Exception:
            return None

    out["fan_rpm"] = read_int(f"{hwmon_dir}/fan1_input")

    vram_temps = []
    for label_path in glob.glob(f"{hwmon_dir}/temp*_label"):
        try:
            with open(label_path) as f:
                label = f.read().strip()
            val = read_int(label_path.replace("_label", "_input"))
            if val is None:
                continue
            temp_c = val / 1000.0
            if label == "pkg":
                out["temp_c"] = temp_c
            elif label.startswith("vram"):
                vram_temps.append(temp_c)
        except Exception:
            continue
    if vram_temps:
        out["vram_temp_c"] = round(max(vram_temps), 1)

    cap = read_int(f"{hwmon_dir}/power1_cap")
    if cap is not None:
        out["power_cap_w"] = cap / 1_000_000

    try:
        r = subprocess.run(["xpu-smi", "dump", "-d", "0", "-m", "0,5", "-n", "1"],
                            capture_output=True, text=True, timeout=4)
        if r.returncode == 0 and r.stdout.strip():
            lines = [l for l in r.stdout.strip().splitlines() if l and not l.lower().startswith("timestamp")]
            if lines:
                fields = lines[-1].split(",")
                if len(fields) >= 4:
                    out["util_pct"] = float(fields[2].strip())
                    out["vram_used_gb"] = round(float(fields[3].strip()) / 1024, 2)
    except Exception:
        pass
    return out


def read_rtx_nvidia_smi():
    out = {"temp_c": None, "fan_pct": None, "util_pct": None,
           "vram_used_mb": None, "vram_total_mb": None, "power_draw_w": None}
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=temperature.gpu,fan.speed,utilization.gpu,memory.used,memory.total,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        parts = [p.strip() for p in r.stdout.strip().split(",")]
        if len(parts) == 6:
            out["temp_c"], out["fan_pct"], out["util_pct"] = float(parts[0]), float(parts[1]), float(parts[2])
            out["vram_used_mb"], out["vram_total_mb"], out["power_draw_w"] = float(parts[3]), float(parts[4]), float(parts[5])
    except Exception:
        pass
    return out


# ─── Agent calls ──────────────────────────────────────────────────────────

def call_arc(message):
    payload = {
        "messages": [{"role": "user", "content": f"no_harm: {message}"}],
        "max_tokens": 800, "temperature": 0.3,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(ARC_ENDPOINT, data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        content = data["choices"][0]["message"].get("content", "")
        tps = data.get("timings", {}).get("predicted_per_second")
        return {"ok": True, "content": content or "(reasoning only)", "tok_per_s": tps}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def call_qwen(message):
    payload = {"model": QWEN_MODEL, "prompt": f"no_harm: {message}", "stream": False}
    req = urllib.request.Request(QWEN_ENDPOINT, data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        eval_count, eval_ns = data.get("eval_count", 0), data.get("eval_duration", 0)
        tps = round(eval_count / (eval_ns / 1e9), 1) if eval_ns else None
        return {"ok": True, "content": data.get("response", ""), "tok_per_s": tps}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── GTK4 app ──────────────────────────────────────────────────────────────

CSS = b"""
window { background-color: #0d1117; }
.gpu-card { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 10px; }
.gpu-title-arc { color: #9b72f5; font-weight: bold; font-size: 13px; }
.gpu-title-rtx { color: #10c07a; font-weight: bold; font-size: 13px; }
.gpu-stats { color: #8b949e; font-family: monospace; font-size: 11px; }
.gate-ok { background-color: #132a1a; color: #2ea043; padding: 8px; border-radius: 8px; font-family: monospace; font-size: 11px; }
.gate-bad { background-color: #3a1f1f; color: #e05555; padding: 8px; border-radius: 8px; font-family: monospace; font-size: 11px; }
.gate-warn { background-color: #2a2412; color: #d4a72c; padding: 8px; border-radius: 8px; font-family: monospace; font-size: 11px; }
.hint-label { color: #8b949e; font-size: 10px; }
textview { background-color: #161b22; color: #e6edf3; }
entry { background-color: #161b22; color: #e6edf3; }
"""


class LociWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="LOCI Station Interface")
        self.set_default_size(820, 640)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_margin_top(10); root.set_margin_bottom(10)
        root.set_margin_start(10); root.set_margin_end(10)
        self.set_child(root)

        self.gate_label = Gtk.Label(xalign=0)
        if ETHICS_CORE_AVAILABLE:
            self.gate_label.set_text("Ethics core: loci-memory-engine loaded — guidance active on every message (not a gate, never blocks).")
            self.gate_label.add_css_class("gate-ok")
        else:
            self.gate_label.set_text(f"Ethics core NOT loaded ({ETHICS_CORE_IMPORT_ERROR}). Sending works, but no guidance is shown. Clone it: git clone https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE ~/loci-memory-engine")
            self.gate_label.add_css_class("gate-warn")
        root.append(self.gate_label)

        gpu_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, homogeneous=True)
        root.append(gpu_row)
        self.arc_title, self.arc_stats, arc_card = self._make_gpu_card("ARC B70 PRO SPARKLE", "arc")
        self.rtx_title, self.rtx_stats, rtx_card = self._make_gpu_card("RTX 5060 Ti", "rtx")
        gpu_row.append(arc_card)
        gpu_row.append(rtx_card)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.chat_view = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD, left_margin=8, right_margin=8, top_margin=8, bottom_margin=8)
        self.chat_buffer = self.chat_view.get_buffer()
        self.tag_user = self.chat_buffer.create_tag("user", foreground="#8b949e", weight=Pango.Weight.BOLD, family="monospace")
        self.tag_arc = self.chat_buffer.create_tag("arc", foreground="#9b72f5", weight=Pango.Weight.BOLD, family="monospace")
        self.tag_qwen = self.chat_buffer.create_tag("qwen", foreground="#10c07a", weight=Pango.Weight.BOLD, family="monospace")
        self.tag_err = self.chat_buffer.create_tag("err", foreground="#e05555")
        self.tag_meta = self.chat_buffer.create_tag("meta", foreground="#8b949e", size_points=8)
        self.tag_guidance_ok = self.chat_buffer.create_tag("guidance_ok", foreground="#2ea043", size_points=9, style=Pango.Style.ITALIC)
        self.tag_guidance_warn = self.chat_buffer.create_tag("guidance_warn", foreground="#d4a72c", size_points=9, style=Pango.Style.ITALIC)
        scroll.set_child(self.chat_view)
        root.append(scroll)

        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.entry = Gtk.Entry(hexpand=True, placeholder_text="Type a message... (@arc / @qwen / nothing = both)")
        self.entry.connect("activate", lambda e: self.send())
        self.send_btn = Gtk.Button(label="Send")
        self.send_btn.connect("clicked", lambda b: self.send())
        input_row.append(self.entry)
        input_row.append(self.send_btn)
        root.append(input_row)

        hint = Gtk.Label(label="Every message tagged no_harm: and scored by the ethics core for guidance (shown under the reply) — guidance informs, it never blocks sending.", xalign=0)
        hint.add_css_class("hint-label")
        root.append(hint)

        self._start_telemetry_loop()

    def _make_gpu_card(self, title, kind):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("gpu-card")
        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class(f"gpu-title-{kind}")
        stats_label = Gtk.Label(label="loading...", xalign=0, wrap=True)
        stats_label.add_css_class("gpu-stats")
        card.append(title_label)
        card.append(stats_label)
        return title_label, stats_label, card

    def _start_telemetry_loop(self):
        def worker():
            while True:
                arc = read_arc_sensors()
                rtx = read_rtx_nvidia_smi()
                GLib.idle_add(self._update_telemetry, arc, rtx)
                time.sleep(3)
        threading.Thread(target=worker, daemon=True).start()

    def _update_telemetry(self, arc, rtx):
        util_str = f"{arc['util_pct']}%" if arc['util_pct'] is not None else "— (needs xpu-smi)"
        vram_str = f"{arc['vram_used_gb']}/{arc['vram_total_gb']}GB" if arc['vram_used_gb'] is not None else "— (needs xpu-smi)"
        self.arc_stats.set_text(
            f"Temp: {arc['temp_c']}°C   Fan: {arc['fan_rpm']} RPM\n"
            f"VRAM Temp: {arc['vram_temp_c']}°C   Power Cap: {arc['power_cap_w']}W\n"
            f"Util: {util_str}   VRAM: {vram_str}"
        )

        rtx_vram = f"{(rtx['vram_used_mb']/1024):.1f}/{(rtx['vram_total_mb']/1024):.0f}GB" if rtx['vram_used_mb'] is not None else "—"
        self.rtx_stats.set_text(
            f"Temp: {rtx['temp_c']}°C   Fan: {rtx['fan_pct']}%\n"
            f"Util: {rtx['util_pct']}%   Power: {rtx['power_draw_w']}W\n"
            f"VRAM: {rtx_vram}"
        )
        return False  # GLib.idle_add: don't repeat

    def _append(self, text, tag=None):
        end = self.chat_buffer.get_end_iter()
        if tag:
            self.chat_buffer.insert_with_tags(end, text, tag)
        else:
            self.chat_buffer.insert(end, text)
        mark = self.chat_buffer.create_mark(None, self.chat_buffer.get_end_iter(), False)
        self.chat_view.scroll_mark_onscreen(mark)

    def send(self):
        text = self.entry.get_text().strip()
        if not text:
            return
        self.entry.set_text("")

        target = "all"
        lowered = text.lower()
        if "@arc" in lowered:
            target = "arc"
        elif "@qwen" in lowered:
            target = "qwen"

        self._append(f"YOU → {target.upper()}\n", self.tag_user)
        self._append(f"{text}\n")

        # Ethics core: guidance, not a gate. Scored and shown, message always
        # proceeds — "all models using the infinite knowledge + memory" route
        # through the same score_vexec() call regardless of target.
        guidance = ethics_guidance(text)
        if guidance.get("ok"):
            tag = self.tag_guidance_ok if guidance["allow_execution"] else self.tag_guidance_warn
            line = f"[ethics core] v_exec={guidance['v_exec']:+.3f}  application={guidance['application_point']}"
            if guidance.get("redirect_suggestion"):
                line += f"  → consider: {guidance['redirect_suggestion']}"
            if guidance.get("needs_human_review"):
                line += "  (within review band — worth a second look, not blocked)"
            self._append(line + "\n", tag)
        else:
            self._append(f"[ethics core unavailable: {guidance.get('error')}]\n", self.tag_guidance_warn)
        self._append("\n")
        self.send_btn.set_sensitive(False)

        def worker():
            result = {}
            threads = []
            if target in ("arc", "all"):
                def do_arc():
                    result["arc"] = call_arc(text)
                t = threading.Thread(target=do_arc); t.start(); threads.append(t)
            if target in ("qwen", "all"):
                def do_qwen():
                    result["qwen"] = call_qwen(text)
                t = threading.Thread(target=do_qwen); t.start(); threads.append(t)
            for t in threads:
                t.join()
            GLib.idle_add(self._render_chat_result, result)

        threading.Thread(target=worker, daemon=True).start()

    def _render_chat_result(self, result):
        if "arc" in result:
            r = result["arc"]
            if r["ok"]:
                self._append("ARC_AGENT (qwen3.6-35b-a3b)\n", self.tag_arc)
                self._append(r["content"] + "\n")
                if r.get("tok_per_s"):
                    self._append(f"{r['tok_per_s']} tok/s\n", self.tag_meta)
            else:
                self._append(f"ARC_AGENT — error: {r['error']}\n", self.tag_err)
            self._append("\n")
        if "qwen" in result:
            r = result["qwen"]
            if r["ok"]:
                self._append("QWEN_14B (loci-agent-14b-qwen3)\n", self.tag_qwen)
                self._append(r["content"] + "\n")
                if r.get("tok_per_s"):
                    self._append(f"{r['tok_per_s']} tok/s\n", self.tag_meta)
            else:
                self._append(f"QWEN_14B — error: {r['error']}\n", self.tag_err)
            self._append("\n")
        self.send_btn.set_sensitive(True)
        return False


class LociApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.loci.station")

    def do_activate(self):
        win = LociWindow(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(win.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        win.present()


if __name__ == "__main__":
    import sys
    app = LociApp()
    sys.exit(app.run(sys.argv))
