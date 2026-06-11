import tkinter as tk
from tkinter import ttk
import subprocess, platform, re, threading, datetime, os, sys, csv, socket
try:
    import ujson as json
except ImportError:
    import json
from PIL import Image, ImageTk
import ctypes


try:
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

try:
    import requests
    requests.packages.urllib3.disable_warnings(
        requests.packages.urllib3.exceptions.InsecureRequestWarning
    )
except ImportError:
    requests = None



DELETE_HOLD_MS = 2500
DELETE_BAR_STEPS = 6
DELETE_BAR_INTERVAL = DELETE_HOLD_MS // DELETE_BAR_STEPS

def _asset(relative_path):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)

BACKUP_ICON_PATH = _asset("assets/images/backup.png") 

# ── Constants ────────────────────────────────────────────────────
PING_COUNT  = 10
IS_WIN      = platform.system().lower() == "windows"

HIDE_TASKBAR_ICON = True

INTERVAL_CYCLE = [
    ("OFF", 0),
    ("1 MIN", 60),
    ("5 MIN", 300),
]

# ── Palette ──────────────────────────────────────────────────────
BG          = "#080b10"
CARD_BG     = "#0d1117"
BORDER      = "#1c2333"
TEXT        = "#cdd9e5"
TEXT_DIM    = "#637080"
GREEN       = "#3fb950"; GREEN_DIM  = "#0b2114"
YELLOW      = "#d29922"; YELLOW_DIM = "#261e07"
ORANGE      = "#e0823d"; ORANGE_DIM = "#2a1508"
RED         = "#f85149"; RED_DIM    = "#2a0d0c"
ACCENT      = "#58a6ff"; ACCENT_DIM = "#0c1d3a"
SILVER = "#C0C0C0"

BLINK_FAST  = 320
BLINK_MILD  = 720

CARD_RED    = "#1a0a09"
CARD_ORANGE = "#1a0e06"
CARD_YELLOW = "#141006"

DIM_TEXT      = "#2a3340"
DIM_TEXT_MID  = "#1e2830"
DIM_BORDER    = "#111822"
DIM_CARD_BG   = "#0a0e14"
DIM_ACCENT    = "#1e3550"
DIM_ACCENT_BG = "#080f18"

# ── Severity helpers ─────────────────────────────────────────────
SEV_STYLE = {
    "green":        (GREEN,  GREEN_DIM,  None),
    "yellow":       (YELLOW, YELLOW_DIM, None),
    "yellow_blink": (YELLOW, YELLOW_DIM, BLINK_MILD),
    "orange_blink": (ORANGE, ORANGE_DIM, BLINK_MILD),
    "red_blink":    (RED,    RED_DIM,    BLINK_FAST),
}

THEMES = {
    "OBSIDIAN": {"BG": "#080b10", "CARD_BG": "#0d1117", "BORDER": "#1c2333"},  # default blue-black
    "MIDNIGHT": {"BG": "#000000", "CARD_BG": "#0a0a0a", "BORDER": "#1a1a1a"},  # pure black
    "NAVY":     {"BG": "#020814", "CARD_BG": "#051020", "BORDER": "#0a2040"},  # deep blue
    "COBALT":   {"BG": "#030d1f", "CARD_BG": "#071828", "BORDER": "#0f3060"},  # bright blue tint
    "TEAL":     {"BG": "#021412", "CARD_BG": "#041e1a", "BORDER": "#083830"},  # deep teal
    "FOREST":   {"BG": "#041008", "CARD_BG": "#071a0c", "BORDER": "#0f3018"},  # deep green
    "MOSS":     {"BG": "#081206", "CARD_BG": "#0f1e0a", "BORDER": "#1e3a10"},  # olive green
    "DUSK":     {"BG": "#0c0818", "CARD_BG": "#140e24", "BORDER": "#281848"},  # deep purple
    "AMETHYST": {"BG": "#10061a", "CARD_BG": "#180a28", "BORDER": "#301450"},  # vivid purple
    "CRIMSON":  {"BG": "#140406", "CARD_BG": "#200609", "BORDER": "#400c12"},  # deep red
    "WINE":     {"BG": "#120308", "CARD_BG": "#1c050d", "BORDER": "#380a1a"},  # dark maroon
    "EMBER":    {"BG": "#140800", "CARD_BG": "#201004", "BORDER": "#402008"},  # dark orange
    "BRONZE":   {"BG": "#120e02", "CARD_BG": "#1c1604", "BORDER": "#362c08"},  # dark gold
    "SLATE":    {"BG": "#0a0c10", "CARD_BG": "#121418", "BORDER": "#202430"},  # cool gray
    "GRAPHITE": {"BG": "#0c0c0c", "CARD_BG": "#161616", "BORDER": "#282828"},  # warm gray
    "CHARCOAL": {"BG": "#080808", "CARD_BG": "#111111", "BORDER": "#202020"},  # near black gray
    "ROSE":     {"BG": "#140608", "CARD_BG": "#200a0e", "BORDER": "#401020"},  # deep rose
    "PINK":     {"BG": "#12040e", "CARD_BG": "#1e0818", "BORDER": "#3a1030"},  # deep pink
    "MAGENTA":  {"BG": "#140410", "CARD_BG": "#200618", "BORDER": "#3c0c30"},  # dark magenta
}
_active_theme = "DARK"

def loss_severity(pct):
    if pct <= 1:   return "green"
    if pct <= 9:   return "yellow_blink"
    if pct <= 49:  return "yellow"
    if pct <= 99:  return "orange_blink"
    return "red_blink"

def should_log(sev):
    return sev in ("orange_blink", "red_blink")

# ── Config / persistence ─────────────────────────────────────────
def _base():
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))

_CONFIGS_DIR = os.path.join(_base(), "assets", "configs")
_STORAGE_DIR = os.path.join(_base(), "assets", "data_storage")

os.makedirs(_CONFIGS_DIR, exist_ok=True)
os.makedirs(_STORAGE_DIR, exist_ok=True)

CONFIG_PATH   = os.path.join(_CONFIGS_DIR, "nm_config.json")
MISC_PATH     = os.path.join(_CONFIGS_DIR, "nm_misc.json")
SETTINGS_PATH = os.path.join(_CONFIGS_DIR, "nm_settings.json")
LOG_PATH      = os.path.join(_STORAGE_DIR, "nm_log.csv")

def load_settings():
    """Load the whole settings dict (branding + theme) with defaults."""
    default = {
        "title_part1": "NAME",
        "title_part1_color": SILVER,
        "title_part2": "ME",
        "title_part2_color": SILVER,
        "icon_path": "assets/images/icon.png",
        "theme": "OBSIDIAN"
    }
    try:
        with open(SETTINGS_PATH) as f:
            data = json.load(f)
            # Ensure all default keys exist
            for k, v in default.items():
                data.setdefault(k, v)
            return data
    except Exception:
        return default.copy()

def load_branding():
    """Backward‑compatible: return the whole dict (branding + theme)."""
    return load_settings()

def save_settings(data):
    """Write the whole settings dict."""
    try:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def load_theme():
    return load_settings().get("theme", "OBSIDIAN")

def save_theme(theme_name):
    data = load_settings()
    data["theme"] = theme_name
    save_settings(data)

_branding = load_branding()

DEFAULT_HOSTS = [
    {"vm_name": "VM 01", "ip": "", "physical_name": "", "system_name": "", "port": "", "endpoint": ""},
    {"vm_name": "VM 02", "ip": "", "physical_name": "", "system_name": "", "port": "", "endpoint": ""},
    {"vm_name": "VM 03", "ip": "", "physical_name": "", "system_name": "", "port": "", "endpoint": ""},
    {"vm_name": "VM 04", "ip": "", "physical_name": "", "system_name": "", "port": "", "endpoint": ""},
    {"vm_name": "VM 05", "ip": "", "physical_name": "", "system_name": "", "port": "", "endpoint": ""},
    {"vm_name": "VM 06", "ip": "", "physical_name": "", "system_name": "", "port": "", "endpoint": ""},
]

_DEFAULT_VM_PATTERN = re.compile(r"^VM\s+\d+$", re.IGNORECASE)

GEOMETRY_PATH = os.path.join(_CONFIGS_DIR, "nm_geometry.json")

def load_hosts():
    try:
        with open(CONFIG_PATH) as f:
            d = json.load(f)
            if isinstance(d, list) and d:
                return d
    except Exception:
        pass
    return [dict(h) for h in DEFAULT_HOSTS]

def save_hosts(hosts):
    try:
        cleaned = []
        for h in hosts:
            entry = dict(h)
            if entry.get("ip") == "0.0.0.0":
                entry["ip"] = ""
            cleaned.append(entry)
        with open(CONFIG_PATH, "w") as f:
            json.dump(cleaned, f, indent=2)
    except Exception:
        pass
    
def load_misc():
    try:
        with open(MISC_PATH) as f:
            d = json.load(f)
            if isinstance(d, list):
                return d
    except Exception:
        pass
    return []

def save_misc(entries):
    try:
        with open(MISC_PATH, "w") as f:
            json.dump(entries, f, indent=2)
    except Exception:
        pass


def save_geometry(x, y, width, height):
    """Save window position and size."""
    try:
        data = {"x": x, "y": y, "width": width, "height": height}
        with open(GEOMETRY_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def load_geometry():
    """Load previously saved geometry, return (x, y, width, height) or None."""
    try:
        with open(GEOMETRY_PATH) as f:
            data = json.load(f)
            return data["x"], data["y"], data["width"], data["height"]
    except Exception:
        return None

def log_event(what, vm_name, ip, diagnostic):
    def _sanitize(val):
        return str(val).replace("\n", " ").replace("\r", " ").strip()
    is_new = not os.path.exists(LOG_PATH)
    try:
        with open(LOG_PATH, "a", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["timestamp", "what", "server", "ip", "diagnostic"])
            w.writerow([
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                _sanitize(what), _sanitize(vm_name), _sanitize(ip), _sanitize(diagnostic)
            ])
    except Exception:
        pass

# ── Validation ───────────────────────────────────────────────────
def is_valid_host(value):
    """Check if value is a valid IP address or domain name"""
    if not value:
        return False
    # Strip protocol if present
    value = value.strip()
    if value.lower().startswith("https://"):
        value = value[8:]
    elif value.lower().startswith("http://"):
        value = value[7:]
    # Remove trailing slash
    value = value.rstrip("/")
    # Check if it's a valid IP address
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", value):
        return True
    # Check if it's a valid domain name
    if re.match(r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", value):
        return True
    return False

def clean_host(value):
    """Clean and return just the host part (IP or domain)"""
    if not value:
        return ""
    value = value.strip()
    if value.lower().startswith("https://"):
        value = value[8:]
    elif value.lower().startswith("http://"):
        value = value[7:]
    value = value.rstrip("/")
    return value

_PING_POOL = __import__("concurrent.futures", fromlist=["ThreadPoolExecutor"]).ThreadPoolExecutor(max_workers=6, thread_name_prefix="ping")

# ── Ping ─────────────────────────────────────────────────────────
def ping_host(ip, count, dot_callback=None):
    if not ip or ip == "0.0.0.0":
        return {"status": "EMPTY", "loss": 0, "avg": "—", "recv": 0}
    if not is_valid_host(ip):
        return {"status": "EMPTY", "loss": 0, "avg": "—", "recv": 0}

    flag = "-n" if IS_WIN else "-c"
    kw   = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WIN else {}

    results = [None] * count
    lock    = threading.Lock()
    

    def ping_one(idx):
        try:
            proc = subprocess.Popen(
                ["ping", flag, "1", "-W", "1" if not IS_WIN else "-w", "1000", ip] if not IS_WIN else ["ping", flag, "1", "-w", "1000", ip],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, **kw
            )
            out, _ = proc.communicate(timeout=3)
            lo = out.lower()
            success = ("reply from" in lo or "bytes from" in lo or
                        "icmp_seq" in lo or "seq=" in lo or
                        "time=" in lo or "time<" in lo or "ttl=" in lo)
            with lock:
                results[idx] = (success, out)
            if dot_callback:
                dot_callback(idx, success)
        except Exception:
            with lock:
                results[idx] = (False, "")
            if dot_callback:
                dot_callback(idx, False)

    futs = [_PING_POOL.submit(ping_one, i) for i in range(count)]
    for f in futs:
        try:
            f.result(timeout=4)
        except Exception:
            pass

    successes = [r for r in results if r and r[0]]
    recv      = len(successes)
    loss      = int(((count - recv) / count) * 100)

    # Parse avg from successful replies
    avg_ms = "—"
    times  = []
    for ok, out in (r for r in results if r):
        m = re.search(r"time[=<](\d+)ms", out, re.IGNORECASE)
        if not m:
            m = re.search(r"Average\s*=\s*(\d+)ms", out)
        if not m:
            m = re.search(r"[\d.]+/([\d.]+)/[\d.]+", out)
        if m:
            try:
                times.append(float(m.group(1)))
            except Exception:
                pass
    if times:
        avg_ms = f"{int(sum(times) / len(times))} ms"

    # Determine status
    all_out = " ".join(r[1] for r in results if r).lower()
    if recv == 0:
        if "unreachable" in all_out:
            status = "UNREACHABLE"
        elif "timed out" in all_out or "timeout" in all_out or "request" in all_out:
            status = "TIMEOUT"
        else:
            status = "DOWN"
    else:
        status = "UP"

    return {"status": status, "loss": loss, "avg": avg_ms, "recv": recv}


def check_port(ip, port, timeout=2):
    if not ip or ip == "0.0.0.0":
        return {"status": "EMPTY", "response_time": "—"}
    if not is_valid_host(ip):
        return {"status": "EMPTY", "response_time": "—"}

    try:
        port_num = int(port)
        if port_num < 1 or port_num > 65535:
            return {"status": "INVALID", "response_time": "—"}
    except (ValueError, TypeError):
        return {"status": "INVALID", "response_time": "—"}
    
    try:
        start = datetime.datetime.now()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port_num))
        elapsed = (datetime.datetime.now() - start).total_seconds() * 1000
        sock.close()
        
        if result == 0:
            return {"status": "OPEN", "response_time": f"{elapsed:.0f}ms"}
        else:
            return {"status": "CLOSED", "response_time": "—"}
    except socket.timeout:
        return {"status": "TIMEOUT", "response_time": "—"}
    except Exception:
        return {"status": "ERROR", "response_time": "—"}


# ── HTTP/S Request ───────────────────────────────────────────────
def check_http(host, port=80, endpoint="", timeout=3):

    if not any(c.isalpha() for c in str(host)):
        return {"status": "EMPTY", "response_time": "—", "status_code": "—", "protocol": "—"}
    
    if not host or host == "0.0.0.0":
        return {"status": "EMPTY", "response_time": "—", "status_code": "—", "protocol": "—"}

    if not requests:
        return {"status": "ERROR", "response_time": "—", "status_code": "no lib", "protocol": "—"}

    try:
        port_num = int(port) if port else 80
    except (ValueError, TypeError):
        port_num = 80

    endpoint_path = endpoint if endpoint else '/'

    # Pick scheme order based on port
    if port_num == 443:
        schemes = ["https"]
    elif port_num == 80:
        schemes = ["http", "https"]
    else:
        schemes = ["https", "http"]

    last_err = "ERROR"
    for scheme in schemes:
        url = f"{scheme}://{host}:{port_num}{endpoint_path}"
        try:
            start = datetime.datetime.now()
            response = requests.get(url, timeout=timeout, verify=False)
            elapsed = (datetime.datetime.now() - start).total_seconds() * 1000
            status_code = response.status_code

            if 200 <= status_code < 300:
                status = "OK"
            elif 300 <= status_code < 400:
                status = "REDIRECT"
            elif 400 <= status_code < 500:
                status = "CLIENT_ERR"
            elif 500 <= status_code < 600:
                status = "SERVER_ERR"
            else:
                status = "UNKNOWN"

            return {
                "status": status,
                "response_time": f"{elapsed:.0f}ms",
                "status_code": status_code,
                "protocol": scheme.upper(),
            }
        except requests.exceptions.Timeout:
            last_err = "TIMEOUT"
        except requests.exceptions.SSLError:
            last_err = "NO_CONNECTION"
        except requests.exceptions.ConnectionError:
            last_err = "NO_CONNECTION"
        except Exception:
            last_err = "ERROR"

    return {"status": last_err, "response_time": "—", "status_code": "—", "protocol": "—"}


def scan_network_devices(ip, timeout=1):
    """
    Scan the /24 subnet of the given IP for connected devices.
    Returns a list of dicts: {ip, hostname, mac, response_time, device_type}
    """
    import ipaddress, subprocess, socket, time

    results = []
    lock = threading.Lock()

    try:
        net = ipaddress.IPv4Network(f"{ip}/24", strict=False)
        hosts = list(net.hosts())
    except Exception:
        return []

    def probe(host_ip):
        host_str = str(host_ip)
        if host_str == ip:
            return
        try:
            start = time.time()
            flag = "-n" if IS_WIN else "-c"
            kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WIN else {}
            proc = subprocess.Popen(
                ["ping", flag, "1", "-w", "300", host_str],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, **kw
            )
            out, _ = proc.communicate(timeout=2)
            elapsed = (time.time() - start) * 1000
            lo = out.lower()
            alive = ("reply from" in lo or "bytes from" in lo or
                     "icmp_seq" in lo or "seq=" in lo)
            if not alive:
                return
            # Resolve hostname
            try:
                hostname = socket.gethostbyaddr(host_str)[0]
            except Exception:
                hostname = ""
            # Guess device type from hostname
            # Guess device type from hostname only if hostname is meaningful
            h_low = hostname.lower()
            if not hostname or hostname == host_str:
                device_type = "unknown"
            elif any(k in h_low for k in ["phone","android","iphone","mobile","pixel","samsung","huawei","xiaomi","oppo","vivo"]):
                device_type = "phone"
            elif any(k in h_low for k in ["laptop","notebook","macbook","thinkpad","surface"]):
                device_type = "laptop"
            elif any(k in h_low for k in ["printer","hp-","canon","epson","ricoh"]):
                device_type = "printer"
            elif any(k in h_low for k in ["cam","nvr","dvr","hikvision","dahua","axis"]):
                device_type = "camera"
            elif any(k in h_low for k in ["router","gateway","switch","ap-","access"]):
                device_type = "router"
            elif any(k in h_low for k in ["pc","desktop","ws","workstation","comp"]):
                device_type = "computer"
            else:
                device_type = "unknown"
            with lock:
                results.append({
                    "ip": host_str,
                    "hostname": hostname or host_str,
                    "response_time": f"{elapsed:.0f}ms",
                    "device_type": device_type,
                })
        except Exception:
            pass

    sem = threading.Semaphore(32)

    def probe_limited(host_ip):
        with sem:
            probe(host_ip)

    threads = [threading.Thread(target=probe_limited, args=(h,), daemon=True) for h in hosts]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    results.sort(key=lambda x: [int(p) for p in x["ip"].split(".")])
    return results

# ── Misc Sidebar Row ─────────────────────────────────────────────
class MiscRow(tk.Frame):
    def __init__(self, parent, entry, sidebar, **kw):
        super().__init__(parent, bg=CARD_BG, **kw)
        self.entry   = dict(entry)
        self.sidebar = sidebar
        self._blink_cb    = None
        self._blink_speed = None
        self._build()
        if self.entry.get("ip"):
            self.after(200, self._ping)

    def _build(self):
        self.configure(highlightbackground=BORDER, highlightthickness=0, padx=8, pady=6)

        top = tk.Frame(self, bg=CARD_BG)
        top.pack(fill="x")


        self.dot = tk.Label(top, text="●", font=("Consolas", 10),
                            fg=TEXT_DIM, bg=CARD_BG)
        self.dot.pack(side="left", padx=(0, 6))

        self.name_lbl = tk.Label(top, text=self.entry.get("name", "—"),
                                font=("Consolas", 9, "bold"), fg=TEXT,
                                bg=CARD_BG, anchor="w")
        self.name_lbl.pack(side="left", fill="x", expand=True)
        self.name_lbl.bind("<Button-3>", lambda e: self._open_edit_modal())

        # Delete button with red hover effect
        delete_btn = tk.Button(top, text="✕", font=("Consolas", 7),
                  fg=TEXT_DIM, bg=CARD_BG,
                  activeforeground=RED, activebackground=CARD_BG,
                  relief="flat", bd=0, cursor="hand2",
                  command=self._remove)
        delete_btn.pack(side="right")
        
        # Red hover effect for delete button
        def delete_enter(e):
            delete_btn.config(fg=RED)
        def delete_leave(e):
            delete_btn.config(fg=TEXT_DIM)
        delete_btn.bind("<Enter>", delete_enter)
        delete_btn.bind("<Leave>", delete_leave)

        bot = tk.Frame(self, bg=CARD_BG)
        bot.pack(fill="x", pady=(2, 0))

        self.ip_lbl = tk.Label(bot, text=self.entry.get("ip", "—"),
                            font=("Consolas", 8), fg=TEXT_DIM, bg=CARD_BG,
                            anchor="w")
        self.ip_lbl.pack(side="left", fill="x", expand=True)
        self.ip_lbl.bind("<Button-3>", lambda e: self._open_edit_modal())

        self.status_lbl = tk.Label(bot, text="—",
                                   font=("Consolas", 7, "bold"), fg=TEXT_DIM, bg=CARD_BG)
        self.status_lbl.pack(side="right")

        self.ts_lbl = tk.Label(self, text="",
                               font=("Consolas", 7), fg=TEXT_DIM, bg=CARD_BG,
                               anchor="w")
        self.ts_lbl.pack(fill="x", pady=(1, 0))

        dot_row = tk.Frame(self, bg=CARD_BG)
        dot_row.pack(fill="x", pady=(3, 0))
        self.dots = []
        for _ in range(3):
            d = tk.Label(dot_row, text="●", font=("Consolas", 7), fg=BORDER, bg=CARD_BG)
            d.pack(side="left", padx=1)
            self.dots.append(d)

            drag_widgets = (
                self,
                top,
                bot,
                dot_row,
                self.name_lbl,
                self.ip_lbl,
                self.status_lbl,
                self.dot
            )

            for w in drag_widgets:
                w.bind("<ButtonPress-1>", self._drag_start)
                w.bind("<B1-Motion>", self._drag_motion)
                w.bind("<ButtonRelease-1>", self._drag_release)

    def _remove(self):
        self._stop_blink()
        self.sidebar.remove_row(self)

    def _ping(self):
        ip = self.entry.get("ip", "")
        if not ip or ip == "0.0.0.0":
            return
        self.dot.config(fg=YELLOW)
        self.status_lbl.config(text="...", fg=YELLOW)
        for d in self.dots:
            d.config(fg=BORDER)
        def on_dot(idx, success):
            # idx 0-2 → dot 0, idx 3-6 → dot 1, idx 7-9 → dot 2
            slot = 0 if idx <= 2 else 1 if idx <= 6 else 2
            self.after(0, self.dots[slot].config, {"fg": GREEN if success else RED})
        def run():
            res = ping_host(ip, 10, dot_callback=on_dot)
            self.after(0, self._apply_result, res)
        threading.Thread(target=run, daemon=True).start()

    def _apply_result(self, res):
            status = res["status"]
            loss   = res["loss"]
            recv   = res["recv"]
            now    = datetime.datetime.now().strftime("%H:%M:%S")

            if status in ("TIMEOUT", "UNREACHABLE", "DOWN", "ERROR"):
                self.status_lbl.config(text="DOWN", fg=RED)
                for d in self.dots: d.config(fg=RED_DIM)
                self._start_blink(RED, BLINK_FAST)
                log_event(f"{status} | loss={loss}%", self.entry.get("name", ""),
                        self.entry.get("ip", ""), "sev=red_blink")
            elif status == "EMPTY":
                self.status_lbl.config(text="—", fg=TEXT_DIM)
                self._stop_blink()
                self.dot.config(fg=TEXT_DIM)
                return
            else:
                sev = loss_severity(loss)
                fg  = SEV_STYLE[sev][0]
                txt = "OK" if loss <= 1 else f"{loss}% loss"
                self.status_lbl.config(text=txt, fg=fg)
                filled = 1 if recv <= 3 else 2 if recv <= 7 else 3
                for i, d in enumerate(self.dots):
                    d.config(fg=fg if i < filled else RED_DIM)
                self._stop_blink()
                self.dot.config(fg=fg)

            self.ip_lbl.config(text=self.entry.get("ip", "—"))
            self.ts_lbl.config(text=f"LAST UPDATE: {now}")

    # REPLACE WITH:
    def _start_blink(self, color, speed):
        self._stop_blink()
        self._blink_speed = speed
        app = self.winfo_toplevel()
        def cb(state):
            if state:
                self.dot.config(fg=color)
                self.configure(highlightbackground=color, bg=CARD_RED)
                self._tint_children(CARD_RED)
            else:
                self.dot.config(fg=CARD_BG)
                self.configure(highlightbackground=BORDER, bg=CARD_BG)
                self._tint_children(CARD_BG)
        self._blink_cb = cb
        subs = (app._blink_fast_subs if speed == BLINK_FAST
                else app._blink_mild_subs)
        subs.append(cb)
        cb(app._blink_fast_state if speed == BLINK_FAST
        else app._blink_mild_state)

    # REPLACE WITH:
    def _stop_blink(self):
        if self._blink_cb:
            app = self.winfo_toplevel()
            subs = (app._blink_fast_subs if self._blink_speed == BLINK_FAST
                    else app._blink_mild_subs)
            try: subs.remove(self._blink_cb)
            except ValueError: pass
            self._blink_cb = None
        self._blink_speed = None
        self.configure(highlightbackground=BORDER, bg=CARD_BG)
        self._tint_children(CARD_BG)

    def _tint_children(self, color):
        for w in self.winfo_children():
            try: w.configure(bg=color)
            except Exception: pass
            for ww in w.winfo_children():
                try: ww.configure(bg=color)
                except Exception: pass

    def _drag_start(self, event):
        self._drag_start_y = event.y_root

        self.configure(
            highlightbackground=ACCENT,
            highlightthickness=2
        )

        self.lift()

        self.sidebar._drag_row = self

    def _drag_motion(self, event):
        rows = self.sidebar.rows

        if self not in rows:
            return

        idx = rows.index(self)

        dy = event.y_root - self._drag_start_y

        # Reset borders
        for r in rows:
            r.configure(highlightbackground=BORDER)

        # Dragged row
        self.configure(
            highlightbackground=ACCENT,
            highlightthickness=2
        )

        row_height = self.winfo_height() + 4

        # Move UP
        if dy < -(row_height // 2) and idx > 0:

            rows[idx], rows[idx - 1] = rows[idx - 1], rows[idx]

            self._repack(rows)

            self.sidebar._save()

            # Reset anchor AFTER successful swap
            self._drag_start_y = event.y_root

        # Move DOWN
        elif dy > (row_height // 2) and idx < len(rows) - 1:

            rows[idx], rows[idx + 1] = rows[idx + 1], rows[idx]

            self._repack(rows)

            self.sidebar._save()

            # Reset anchor AFTER successful swap
            self._drag_start_y = event.y_root

    def _drag_release(self, event):
        for r in self.sidebar.rows:
            r.configure(
                highlightbackground=BORDER,
                highlightthickness=1,
                bg=CARD_BG
            )

            r._tint_children(CARD_BG)

        self.sidebar._drag_row = None

    def _repack(self, rows):
        for row in rows:
            row.pack_forget()
        for row in rows:
            row.pack(fill="x", pady=(0, 4))

    def ping_now(self):
        self._ping()


    def _edit_press(self, event):
        self._edit_start_x = event.x_root
        self._edit_start_y = event.y_root

    def _edit_release(self, event):
        dx = abs(event.x_root - getattr(self, "_edit_start_x", event.x_root))
        dy = abs(event.y_root - getattr(self, "_edit_start_y", event.y_root))
        if dx < 5 and dy < 5:
            self._open_edit_modal()

    def _open_edit_modal(self):
        modal = tk.Toplevel(self)
        modal.title("")
        modal.configure(bg=BG)
        modal.resizable(False, False)
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        root = self.winfo_toplevel()
        root.update_idletasks()
        w, h = 400, 240
        x = root.winfo_rootx() + (root.winfo_width() - w) // 2
        y = root.winfo_rooty() + (root.winfo_height() - h) // 2
        modal.geometry(f"{w}x{h}+{x}+{y}")
        modal.configure(highlightbackground=SILVER, highlightthickness=0)

        try:
            root._dark_titlebar_for(modal)
        except Exception:
            pass

        card = tk.Frame(modal, bg=CARD_BG, padx=16, pady=14)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="EDIT DEVICE", font=("Consolas", 10, "bold"),
                 fg=TEXT, bg=CARD_BG).pack(anchor="w")
        tk.Frame(card, bg=ACCENT, height=2).pack(fill="x", pady=(8, 12))

        tk.Label(card, text="NAME", font=("Consolas", 8, "bold"),
                 fg=TEXT_DIM, bg=CARD_BG).pack(anchor="w")
        name_wrap = tk.Frame(card, bg=CARD_BG)
        name_wrap.pack(fill="x", pady=(4, 10))
        name_var = tk.StringVar(value=self.entry.get("name", ""))
        name_e = tk.Entry(name_wrap, textvariable=name_var,
                          font=("Consolas", 10), fg=TEXT, bg=CARD_BG,
                          insertbackground=TEXT, relief="flat", bd=0,
                          highlightthickness=0)
        name_e.pack(fill="x", ipady=6)
        tk.Frame(name_wrap, bg=BORDER, height=1).pack(fill="x")

        tk.Label(card, text="IP ADDRESS", font=("Consolas", 8, "bold"),
                 fg=TEXT_DIM, bg=CARD_BG).pack(anchor="w")
        ip_wrap = tk.Frame(card, bg=CARD_BG)
        ip_wrap.pack(fill="x", pady=(4, 12))
        ip_var = tk.StringVar(value=self.entry.get("ip", ""))
        ip_e = tk.Entry(ip_wrap, textvariable=ip_var,
                        font=("Consolas", 10), fg=TEXT, bg=CARD_BG,
                        insertbackground=TEXT, relief="flat", bd=0,
                        highlightthickness=0)
        ip_e.pack(fill="x", ipady=6)
        tk.Frame(ip_wrap, bg=BORDER, height=1).pack(fill="x")

        msg = tk.Label(card, text="", font=("Consolas", 7), fg=TEXT_DIM, bg=CARD_BG)
        msg.pack(anchor="w")

        btn_row = tk.Frame(card, bg=CARD_BG)
        btn_row.pack(fill="x", pady=(8, 0))

        def do_save():
            name = name_var.get().strip()
            ip   = ip_var.get().strip()
            if not name:
                msg.config(text="Need a name", fg=YELLOW)
                return
            cleaned = clean_host(ip)
            if ip and not is_valid_host(cleaned):
                msg.config(text="Invalid IP", fg=RED)
                return
            self.entry["name"] = name
            self.entry["ip"]   = cleaned
            self.name_lbl.config(text=name)
            self.ip_lbl.config(text=cleaned or "—")
            self.sidebar._save()
            modal.destroy()
            self.ping_now()

        tk.Button(btn_row, text="SAVE",
                  font=("Consolas", 9, "bold"), fg=BG, bg=ACCENT,
                  activeforeground=BG, activebackground="#79b8ff",
                  relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                  command=do_save).pack(side="left")

        cancel_btn = tk.Button(btn_row, text="CANCEL",
                  font=("Consolas", 9, "bold"), fg=TEXT_DIM, bg=CARD_BG,
                  activeforeground=TEXT, activebackground=BORDER,
                  relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                  command=modal.destroy)
        cancel_btn.pack(side="left", padx=(8, 0))
        def cancel_enter(e): cancel_btn.config(fg=RED)
        def cancel_leave(e): cancel_btn.config(fg=TEXT_DIM)
        cancel_btn.bind("<Enter>", cancel_enter)
        cancel_btn.bind("<Leave>", cancel_leave)

        name_e.focus_set()
        name_e.icursor("end")
        modal.bind("<Escape>", lambda _: modal.destroy())
        modal.bind("<Return>", lambda _: do_save())


# ── Misc Sidebar ─────────────────────────────────────────────────
class MiscSidebar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self.rows = []
        self._drag_row = None
        self._auto_scroll_job = None
        self._build()
        self._load()
        self._scroll_direction = 1
        self.after(4000, self._auto_scroll_tick)
        
    def _build(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", pady=(0, 6))

        tk.Label(hdr, text="BIOMETRIC DEVICES", font=("Consolas", 9, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(side="left")

        tk.Button(hdr, text="⟳", font=("Consolas", 9),
                  fg=TEXT_DIM, bg=BG,
                  activeforeground=ACCENT, activebackground=BG,
                  relief="flat", bd=0, cursor="hand2",
                  command=self._ping_all).pack(side="right")

        scroll_wrap = tk.Frame(self, bg=BG)
        scroll_wrap.pack(fill="both", expand=True)

        # Canvas without the scrollbar attachment
        self.canvas = tk.Canvas(
            scroll_wrap,
            bg=BG,
            highlightthickness=0,
            yscrollincrement=1
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        # Inner frame
        self.list_frame = tk.Frame(self.canvas, bg=BG)

        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.list_frame,
            anchor="nw"
        )

        # Update scrollregion automatically when items are added/removed
        self.list_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(
                self.canvas_window,
                width=e.width
            )
        )

        # Robust Mousewheel logic that works even when hovering over child widgets
        def _on_mousewheel(event):
            if not self.canvas.winfo_exists():
                return
            # Get current mouse coordinates
            x, y = self.canvas.winfo_pointerxy()
            # Find the exact widget under the cursor
            widget = self.canvas.winfo_containing(x, y)
            
            # If the widget under the mouse is part of this canvas (or the canvas itself)
            if widget and str(widget).startswith(str(self.canvas)):
                # Handle Windows/Mac (event.delta) and Linux (event.num)
                if getattr(event, 'num', 0) == 4 or getattr(event, 'delta', 0) > 0:
                    self.canvas.yview_scroll(-30, "units")
                elif getattr(event, 'num', 0) == 5 or getattr(event, 'delta', 0) < 0:
                    self.canvas.yview_scroll(30, "units")

        # Bind to the top-level window so it intercepts scrolls globally
        top = self.winfo_toplevel()
        top.bind("<MouseWheel>", _on_mousewheel, add="+")
        top.bind("<Button-4>", _on_mousewheel, add="+") # Linux Support
        top.bind("<Button-5>", _on_mousewheel, add="+") # Linux Support

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(8, 6))

    # ── Continuous auto-scroll ───────────────────────────────────
    def _is_mouse_over(self):
        """Check if the mouse is currently hovering over the sidebar."""
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
            return w is not None and str(w).startswith(str(self))
        except Exception:
            return False

    def _auto_scroll_tick(self):
        if not self.canvas.winfo_exists():
            return

        if self._is_mouse_over():
            self._auto_scroll_job = self.after(300, self._auto_scroll_tick)
            return

        top, bottom = self.canvas.yview()

        # All content fits — nothing to scroll
        if top == 0.0 and bottom >= 1.0:
            self._auto_scroll_job = self.after(1000, self._auto_scroll_tick)
            return

        # Reverse direction at boundaries
        if bottom >= 1.0:
            self._scroll_direction = -1
        elif top <= 0.0:
            self._scroll_direction = 1

        # Move by a tiny fraction instead of whole units
        step = 0.0009 * self._scroll_direction
        new_top = max(0.0, min(1.0, top + step))
        self.canvas.yview_moveto(new_top)

        self._auto_scroll_job = self.after(120, self._auto_scroll_tick)

    def _ping_all(self):
        for row in self.rows:
            if row.entry.get("ip"):
                row.ping_now()

    def _load(self):
        pass

       
        # Collapsible add panel
        self._add_panel = tk.Frame(self, bg=BG)

        self._name_var = tk.StringVar()
        self._ip_var   = tk.StringVar()

        add_f = tk.Frame(self._add_panel, bg=BG)
        add_f.pack(fill="x", pady=(4, 0))

        name_e = tk.Entry(add_f, textvariable=self._name_var,
                          font=("Consolas", 8), fg=TEXT_DIM, bg=CARD_BG,
                          insertbackground=TEXT, relief="flat",
                          highlightbackground=BORDER, highlightthickness=1, width=10)
        name_e.pack(side="left", ipady=3, padx=(0, 3))
        self._setup_ph(name_e, self._name_var, "Name")

        ip_e = tk.Entry(add_f, textvariable=self._ip_var,
                        font=("Consolas", 8), fg=TEXT_DIM, bg=CARD_BG,
                        insertbackground=TEXT, relief="flat",
                        highlightbackground=BORDER, highlightthickness=1, width=12)
        ip_e.pack(side="left", ipady=3, padx=(0, 3))
        self._setup_ph(ip_e, self._ip_var, "IP")

        tk.Button(add_f, text="+", font=("Consolas", 9, "bold"),
                  fg=BG, bg=ACCENT,
                  activeforeground=BG, activebackground="#79b8ff",
                  relief="flat", bd=0, padx=6, pady=3, cursor="hand2",
                  command=self._add_entry).pack(side="left")

        self._msg_lbl = tk.Label(self._add_panel, text="", font=("Consolas", 7),
                                 fg=TEXT_DIM, bg=BG)
        self._msg_lbl.pack(anchor="w", pady=(3, 0))


    def _setup_ph(self, entry, var, placeholder):
        var.set(placeholder)
        entry.config(fg=TEXT_DIM)
        def fi(_):
            if var.get() == placeholder:
                var.set("")
                entry.config(fg=TEXT)
        def fo(_):
            if not var.get().strip():
                var.set(placeholder)
                entry.config(fg=TEXT_DIM)
        entry.bind("<FocusIn>",  fi)
        entry.bind("<FocusOut>", fo)

    def _load(self):
        for e in load_misc():
            self._create_row(e)

    def _create_row(self, entry):
        row = MiscRow(self.list_frame, entry, self)
        row.pack(fill="x", pady=(0, 4))
        self.rows.append(row)
        self.after(50, lambda: self.canvas.yview_moveto(1.0))
        return row

    def _add_entry(self):
        name = self._name_var.get().strip()
        ip   = self._ip_var.get().strip()
        if name in ("", "Name"):
            self._msg_lbl.config(text="need a name", fg=YELLOW)
            return
        if not ip or ip == "IP":
            self._msg_lbl.config(text="bad IP", fg=RED)
            return
        cleaned = clean_host(ip)
        if not is_valid_host(cleaned):
            self._msg_lbl.config(text="bad IP", fg=RED)
            return
        self._create_row({"name": name, "ip": cleaned})
        self._save()
        self._name_var.set("Name")
        self._ip_var.set("IP")
        self._msg_lbl.config(text=f"added {name}", fg=GREEN)
        self.after(2000, lambda: self._msg_lbl.config(text=""))

    def remove_row(self, row):
        row.pack_forget()
        row.destroy()
        self.rows.remove(row)
        self._save()

    def _save(self):
        save_misc([r.entry for r in self.rows])


    def _open_add_misc_modal(self):
        modal = tk.Toplevel(self)
        modal.title("")
        modal.configure(bg=BG)
        modal.resizable(False, False)
        modal.transient(self.winfo_toplevel())
        modal.grab_set()
        self.after(100, lambda: self.winfo_toplevel()._dark_titlebar_for(modal))

        # Center modal
        root = self.winfo_toplevel()
        root.update_idletasks()

        w, h = 560, 320
        x = root.winfo_rootx() + (root.winfo_width() - w) // 2
        y = root.winfo_rooty() + (root.winfo_height() - h) // 2

        modal.geometry(f"{w}x{h}+{x}+{y}")

        # Border
        modal.configure(highlightbackground=SILVER, highlightthickness=0)

        card = tk.Frame(
            modal,
            bg=CARD_BG,
            padx=16,
            pady=14
        )
        card.pack(fill="both", expand=True)

        # Title
        tk.Label(
            card,
            text="ADD BIOMETRIC IP",
            font=("Consolas", 10, "bold"),
            fg=SILVER,
            bg=CARD_BG
        ).pack(anchor="w")

        tk.Frame(card, bg=SILVER, height=2).pack(fill="x", pady=(10, 14))

        # Name
        tk.Label(
            card,
            text="NAME",
            font=("Consolas", 8, "bold"),
            fg=SILVER,
            bg=CARD_BG
        ).pack(anchor="w")

        name_var = tk.StringVar()
        name_placeholder = ""

        # Name wrapper with silver border
        name_border = tk.Frame(card, bg=SILVER, padx=1, pady=1)
        name_border.pack(fill="x", pady=(4, 12))

        # Add inner padding frame for the entry
        name_padding = tk.Frame(name_border, bg=BG, padx=8, pady=4)  # 8px padding on sides
        name_padding.pack(fill="both", expand=True)

        name_e = tk.Entry(
            name_padding,
            textvariable=name_var,
            font=("Consolas", 10),
            fg=TEXT_DIM,
            bg=BG,
            insertbackground=SILVER,
            relief="flat",
            bd=0,
            highlightthickness=0
        )
        name_e.pack(fill="x", ipady=3)
        
        # Placeholder logic
        name_var.set(name_placeholder)
        def on_name_focus_in(e):
            if name_var.get() == name_placeholder:
                name_var.set("")
                name_e.config(fg=SILVER)
        def on_name_focus_out(e):
            if not name_var.get().strip():
                name_var.set(name_placeholder)
                name_e.config(fg=TEXT_DIM)
            else:
                name_e.config(fg=SILVER)
        name_e.bind("<FocusIn>", on_name_focus_in)
        name_e.bind("<FocusOut>", on_name_focus_out)

        # IP
        tk.Label(
            card,
            text="IP ADDRESS",
            font=("Consolas", 8, "bold"),
            fg=SILVER,
            bg=CARD_BG
        ).pack(anchor="w")

        ip_var = tk.StringVar()
        ip_placeholder = ""

        # IP wrapper with silver border
        ip_border = tk.Frame(card, bg=SILVER, padx=1, pady=1)
        ip_border.pack(fill="x", pady=(4, 14))

        # Add inner padding frame for the entry
        ip_padding = tk.Frame(ip_border, bg=BG, padx=8, pady=4)  # 8px padding on sides
        ip_padding.pack(fill="both", expand=True)

        ip_e = tk.Entry(
            ip_padding,
            textvariable=ip_var,
            font=("Consolas", 10),
            fg=TEXT_DIM,
            bg=BG,
            insertbackground=SILVER,
            relief="flat",
            bd=0,
            highlightthickness=0
        )
        ip_e.pack(fill="x", ipady=3)
        
        # Placeholder logic
        ip_var.set(ip_placeholder)
        def on_ip_focus_in(e):
            if ip_var.get() == ip_placeholder:
                ip_var.set("")
                ip_e.config(fg=SILVER)
        def on_ip_focus_out(e):
            if not ip_var.get().strip():
                ip_var.set(ip_placeholder)
                ip_e.config(fg=TEXT_DIM)
            else:
                ip_e.config(fg=SILVER)
        ip_e.bind("<FocusIn>", on_ip_focus_in)
        ip_e.bind("<FocusOut>", on_ip_focus_out)

        msg = tk.Label(
            card,
            text="",
            font=("Consolas", 7),
            fg=TEXT_DIM,
            bg=CARD_BG
        )
        msg.pack(anchor="w")

        btn_row = tk.Frame(card, bg=CARD_BG)
        btn_row.pack(fill="x", pady=(12, 0))

        def do_add():
            name = name_var.get().strip()
            ip = ip_var.get().strip()
            
            if not name or name == name_placeholder:
                msg.config(text="Need a name", fg=YELLOW)
                return
            
            if not ip or ip == ip_placeholder:
                msg.config(text="Need an IP address", fg=YELLOW)
                return

            cleaned_ip = clean_host(ip)
            if not is_valid_host(cleaned_ip):
                msg.config(text="Invalid IP", fg=RED)
                return

            self._create_row({
                "name": name,
                "ip": cleaned_ip
            })

            self._save()
            modal.destroy()

        # ADD BUTTON with hover animation
        add_btn_wrap = tk.Frame(btn_row, bg=SILVER, padx=1, pady=1)
        add_btn_wrap.pack(side="left")

        add_btn = tk.Button(
            add_btn_wrap,
            text="+ ADD",
            font=("Consolas", 9, "bold"),
            fg=SILVER,
            bg=BORDER,
            activeforeground=SILVER,
            activebackground="#1a1a1a",
            relief="flat",
            bd=0,
            padx=14,
            pady=5,
            cursor="hand2",
            command=do_add
        )
        add_btn.pack()

        # CANCEL BUTTON with hover animation
        cancel_btn_wrap = tk.Frame(btn_row, bg=SILVER, padx=1, pady=1)
        cancel_btn_wrap.pack(side="left", padx=(8, 0))

        cancel_btn = tk.Button(
            cancel_btn_wrap,
            text="CANCEL",
            font=("Consolas", 9, "bold"),
            fg=SILVER,
            bg=BORDER,
            activeforeground=SILVER,
            activebackground="#1a1a1a",
            relief="flat",
            bd=0,
            padx=14,
            pady=5,
            cursor="hand2",
            command=modal.destroy
        )
        cancel_btn.pack()

        # HOVER ANIMATION FOR BOTH BUTTONS
        def on_enter(btn, wrapper):
            wrapper.config(bg="#E0E0E0")  # Brighter silver border
            btn.config(bg="#1a1a1a")       # Slightly lighter black

        def on_leave(btn, wrapper):
            wrapper.config(bg=SILVER)      # Back to original silver
            btn.config(bg=BORDER)          # Back to dark border color

        # Bind hover effects for ADD button
        add_btn.bind("<Enter>", lambda e: on_enter(add_btn, add_btn_wrap))
        add_btn.bind("<Leave>", lambda e: on_leave(add_btn, add_btn_wrap))

        # Bind hover effects for CANCEL button
        cancel_btn.bind("<Enter>", lambda e: on_enter(cancel_btn, cancel_btn_wrap))
        cancel_btn.bind("<Leave>", lambda e: on_leave(cancel_btn, cancel_btn_wrap))

        name_e.focus_set()
        modal.bind("<Escape>", lambda _: modal.destroy())

# ── Host Card ────────────────────────────────────────────────────
class HostCard(tk.Frame):

    def _graph_layout(self, W, H, data):
        """Shared layout constants for all graph draw methods."""
        valid = [v for v in data if v is not None]
        max_ms = max(valid) if valid else 1
        min_ms = min(valid) if valid else 0
        STATS_H = 18
        pad_top = 10
        pad_bot = 32
        pad_l = 44 if W >= 500 else 30 if W >= 300 else 20
        pad_r = 10 if W >= 500 else 8 if W >= 300 else 5
        graph_h = max(30, H - pad_top - pad_bot - STATS_H)
        graph_w = max(50, W - pad_l - pad_r)
        floor_y = pad_top + graph_h
        n = len(data)

        def x_of(i):
            return pad_l if n <= 1 else pad_l + (i / max(1, n - 1)) * graph_w

        def y_of(v):
            if max_ms == min_ms:
                return pad_top + graph_h * 0.5
            return pad_top + (1 - (v - min_ms) / max(1, max_ms - min_ms)) * graph_h

        return valid, max_ms, min_ms, STATS_H, pad_top, pad_l, pad_r, graph_h, graph_w, floor_y, x_of, y_of

    def _animate_graph_drawIn(self):
        """Animate dots appearing one by one on first show."""
        if not self._graph_showing:
            return
        if not hasattr(self, "_graph_canvas") or not self._graph_canvas.winfo_exists():
            return

        data = self._latency_history[-50:]
        n = len(data)
        if n < 2:
            return

        step = getattr(self, "_graph_anim_step", 0)

        if step <= n:
            self._graph_anim_step = step + 1
            self._redraw_graph_partial(step)
            self.after(200 if step > 0 else 50, self._animate_graph_drawIn)
        else:
            self._graph_anim_step = n
            self._redraw_graph()
            self._animate_graph_pulse(0)

    def _redraw_graph_partial(self, visible_count):
        """Draw full graph (grid, fill, lines, labels, stats) but only dots up to visible_count."""
        if not self._graph_showing:
            return
        if not hasattr(self, "_graph_canvas") or not self._graph_canvas.winfo_exists():
            return

        self._graph_canvas.update_idletasks()
        W = self._graph_canvas.winfo_width()
        H = self._graph_canvas.winfo_height()
        if W < 100 or H < 100:
            return

        self._graph_canvas.delete("all")

        full_data = self._latency_history[-50:]
        n = len(full_data)
        if n < 2:
            return

        valid, max_ms, min_ms, STATS_H, pad_top, pad_l, pad_r, graph_h, graph_w, floor_y, x_of, y_of = \
            self._graph_layout(W, H, full_data)

        # ── Grid lines + Y labels ──
        if W > 200:
            for frac, label in [(0.0, f"{max_ms}ms"), (0.5, f"{(max_ms+min_ms)//2}ms"), (1.0, f"{min_ms}ms")]:
                gy = pad_top + frac * graph_h
                self._graph_canvas.create_line(pad_l, gy, W - pad_r, gy, fill=BORDER, dash=(3, 5))
                self._graph_canvas.create_text(pad_l - 4, gy, text=label,
                    font=("Consolas", 7), fill=TEXT_DIM, anchor="e")

        # ── X-axis time labels ──
        if W > 250:
            x_ticks = [0, n // 4, n // 2, 3 * n // 4, n - 1]
            for ti in x_ticks:
                tx = x_of(ti)
                offset = ti - (n - 1)
                lbl = "now" if offset == 0 else str(offset)
                fg = TEXT_DIM if offset == 0 else "#2a3340"
                self._graph_canvas.create_text(tx, floor_y + 8, text=lbl,
                    font=("Consolas", 7), fill=fg, anchor="center")

        # ── Y positions ──
        y_positions = []
        for v in full_data:
            y_positions.append(y_of(v) if v is not None else floor_y)

        # ── Fill polygon (full) ──
        fill_pts = [pad_l, floor_y]
        for i in range(n):
            fill_pts += [x_of(i), y_positions[i]]
        fill_pts += [x_of(n - 1), floor_y]
        self._graph_canvas.create_polygon(fill_pts, fill="#0c2a1a", outline="")

        # ── Loss markers ──
        for i, v in enumerate(full_data):
            if v is None:
                px = x_of(i)
                marker_w = max(2, min(6, W // 100))
                self._graph_canvas.create_rectangle(
                    px - marker_w, floor_y - 8, px + marker_w, floor_y,
                    fill="#2a0d0c", outline=""
                )

        # ── Lines (full) ──
        line_width = 1 if W < 400 else 2
        for i in range(n - 1):
            x1, x2 = x_of(i), x_of(i + 1)
            y1, y2 = y_positions[i], y_positions[i + 1]
            cv, nv = full_data[i], full_data[i + 1]
            if cv is None or nv is None:
                lc = RED
            elif nv <= 50:
                lc = GREEN
            elif nv <= 150:
                lc = YELLOW
            elif nv <= 300:
                lc = ORANGE
            else:
                lc = RED
            self._graph_canvas.create_line(x1, y1, x2, y2,
                fill=lc, width=line_width, smooth=False,
                capstyle="round", joinstyle="round")

        # ── Dots: only up to visible_count, with latency labels ──
        dot_scale = 1.0 if W >= 600 else 0.8 if W >= 400 else 0.6
        for i in range(min(visible_count, n)):
            v = full_data[i]
            px = x_of(i)
            py = y_positions[i]
            is_last = (i == n - 1)
            if v is not None:
                dc = GREEN if v <= 50 else YELLOW if v <= 150 else ORANGE if v <= 300 else RED
                if is_last:
                    # Last dot: full pulse handled by _animate_graph_pulse, draw normally for now
                    r = max(2, int(4 * dot_scale))
                    self._graph_canvas.create_oval(px - r, py - r, px + r, py + r,
                        fill=dc, outline="")
                else:
                    # Non-last dots: small filled dot + subtle dim glow ring
                    r = max(2, int(2.5 * dot_scale))
                    glow_r = r + 2
                    # Dim glow ring (low opacity via stipple)
                    self._graph_canvas.create_oval(
                        px - glow_r, py - glow_r, px + glow_r, py + glow_r,
                        fill="", outline=dc, width=1, stipple="gray25"
                    )
                    self._graph_canvas.create_oval(px - r, py - r, px + r, py + r,
                        fill=dc, outline="")
                if W > 250:
                    self._graph_canvas.create_text(px, py - 12,
                        text=f"{v}ms", font=("Consolas", max(6, int(7 * dot_scale)), "bold"),
                        fill=dc, anchor="s")
            else:
                # Loss point: red X
                r = max(3, int(4 * dot_scale))
                self._graph_canvas.create_line(px - r, py - r, px + r, py + r,
                    fill=RED, width=max(1, line_width + 1))
                self._graph_canvas.create_line(px - r, py + r, px + r, py - r,
                    fill=RED, width=max(1, line_width + 1))

        # ── Stats bar (always visible) ──
        bar_y = H - STATS_H
        self._graph_canvas.create_rectangle(pad_l, bar_y, W - pad_r, H, fill=CARD_BG, outline="")

        loss_count = sum(1 for v in full_data if v is None)
        avg_val = int(sum(valid) / len(valid)) if valid else 0
        min_val = min(valid) if valid else 0
        max_val = max(valid) if valid else 0

        stats = [
            ("AVG",  f"{avg_val}ms", GREEN if avg_val <= 50 else YELLOW if avg_val <= 150 else RED),
            ("MIN",  f"{min_val}ms", GREEN),
            ("MAX",  f"{max_val}ms", GREEN if max_val <= 50 else YELLOW if max_val <= 150 else ORANGE if max_val <= 300 else RED),
            ("LOSS", f"{loss_count}pkt", RED if loss_count > 0 else GREEN),
        ]

        avail_w = (W - pad_r) - (pad_l + 4)
        if avail_w > 100:
            col_w = avail_w // len(stats)
            font_size = 7 if W > 300 else 6
            for ci, (label, value, color) in enumerate(stats):
                cx = pad_l + 4 + ci * col_w + col_w // 2
                self._graph_canvas.create_text(cx, bar_y + STATS_H // 2,
                    text=f"{label} ", font=("Consolas", font_size), fill=TEXT_DIM, anchor="e")
                self._graph_canvas.create_text(cx, bar_y + STATS_H // 2,
                    text=value, font=("Consolas", font_size, "bold"), fill=color, anchor="w")

    def _animate_graph_pulse(self, tick):
        """Pulse the latest data point dot after draw-in completes."""
        if not self._graph_showing:
            return
        if not hasattr(self, "_graph_canvas") or not self._graph_canvas.winfo_exists():
            return

        data = self._latency_history[-50:]
        if not data:
            return

        # Find the last non-None value and its index
        last_idx = None
        last_val = None
        for i in range(len(data) - 1, -1, -1):
            if data[i] is not None:
                last_idx = i
                last_val = data[i]
                break

        if last_idx is None:
            return

        self._graph_canvas.update_idletasks()
        W = self._graph_canvas.winfo_width()
        H = self._graph_canvas.winfo_height()
        if W < 100 or H < 100:
            return

        valid, max_ms, min_ms, STATS_H, pad_top, pad_l, pad_r, graph_h, graph_w, floor_y, x_of, y_of = \
            self._graph_layout(W, H, data)

        px = x_of(last_idx)
        py = y_of(last_val)
        dc = GREEN if last_val <= 50 else YELLOW if last_val <= 150 else ORANGE if last_val <= 300 else RED

        dot_scale = 1.0 if W >= 600 else 0.8 if W >= 400 else 0.6

        # Pulse: expand and contract over 8 ticks
        PULSE_FRAMES = 8
        t = tick % (PULSE_FRAMES * 2)
        if t < PULSE_FRAMES:
            scale_factor = 1.0 + (t / PULSE_FRAMES) * 0.8   # grow  1x → 1.8x
        else:
            scale_factor = 1.8 - ((t - PULSE_FRAMES) / PULSE_FRAMES) * 0.8  # shrink 1.8x → 1x

        base_r = max(3, int(4 * dot_scale))
        r = max(2, int(base_r * scale_factor))

        # Delete old pulse tag, draw new one
        self._graph_canvas.delete("pulse_dot")

        # Outer glow ring
        glow_r = r + 3
        self._graph_canvas.create_oval(
            px - glow_r, py - glow_r, px + glow_r, py + glow_r,
            fill="", outline=dc, width=1,
            tags="pulse_dot"
        )
        # Inner filled dot
        self._graph_canvas.create_oval(
            px - r, py - r, px + r, py + r,
            fill=dc, outline="",
            tags="pulse_dot"
        )

        self._graph_pulse_job = self.after(60, lambda: self._animate_graph_pulse(tick + 1))

    def _create_devices_button(self, container):
        if not container.winfo_exists():
            return
        
        target = (self.host.get("ip") or "").strip()
        if not target or target == "0.0.0.0":
            return
        
        # Create wrapper with silver border inside the container
        devices_wrap = tk.Frame(container, bg=DIM_BORDER, padx=1, pady=1)
        devices_wrap.pack(fill="both", expand=True)
        
        self._devices_btn = tk.Button(
            devices_wrap,
            text="DEVICES",
            font=("Consolas", 8, "bold"),
            fg=SILVER,
            bg=BORDER,
            activeforeground=DIM_BORDER,
            activebackground="#1a1a1a",
            relief="flat",
            bd=0,
            padx=8,
            pady=2,
            cursor="hand2",
            highlightthickness=0,
            command=self._open_devices_modal
        )
        self._devices_btn.pack(fill="both", expand=True)
        
        # Hover effect matching + HOST button
        def on_devices_enter(e):
            devices_wrap.config(bg=DIM_BORDER) 
            self._devices_btn.config(bg="#717171")
        
        def on_devices_leave(e):
            devices_wrap.config(bg=DIM_BORDER)
            self._devices_btn.config(bg=BORDER)
        
        devices_wrap.bind("<Enter>", on_devices_enter)
        devices_wrap.bind("<Leave>", on_devices_leave)
        self._devices_btn.bind("<Enter>", on_devices_enter)
        self._devices_btn.bind("<Leave>", on_devices_leave)

    def _bind_scroll_recursive(self, widget):
        widget.bind("<MouseWheel>", self._forward_scroll, add="+")
        widget.bind("<Button-4>", self._forward_scroll, add="+")
        widget.bind("<Button-5>", self._forward_scroll, add="+")
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)

    def _forward_scroll(self, event):
        if hasattr(self.app, 'scroll') and hasattr(self.app.scroll, '_mw'):
            self.app.scroll._mw(event)
        return "break"

    def _on_graph_resize(self, event=None):
        if not self._graph_showing:
            return
        if not hasattr(self, "_graph_canvas") or not self._graph_canvas.winfo_exists():
            return
        if hasattr(self, "_resize_job"):
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(100, self._redraw_graph)


    def _bind_right_hold(self, widget):
        if isinstance(widget, (tk.Frame, tk.Label, tk.Canvas)):
            widget.bind("<ButtonPress-3>", self._rc_press)
            widget.bind("<ButtonRelease-3>", self._rc_release)
        for child in widget.winfo_children():
            self._bind_right_hold(child)

    def _cancel_hold(self):
        if getattr(self, "_rc_job", None):
            self.after_cancel(self._rc_job)
            self._rc_job = None
        self._rc_step = 0

    def _rc_press(self, _=None):
        if not self.host.get("ip") and not self.host.get("vm_name"):
            return
        self._cancel_hold()
        self._rc_step = 0
        self._rc_active = True
        self._last_ts = getattr(self, "_last_ts", "—")
        self.badge.config(text=" DELETING ", fg=RED, bg=RED_DIM)
        self.badge_frame.config(bg=RED_DIM)
        self.ts_lbl.config(text="▓" * 0 + "░" * DELETE_BAR_STEPS, fg=RED)
        self._rc_tick()

    def _rc_tick(self):
        if not getattr(self, "_rc_active", False):
            return
        self._rc_step += 1
        bar = "▓" * self._rc_step + "░" * (DELETE_BAR_STEPS - self._rc_step)
        self.ts_lbl.config(text=bar, fg=RED)

        if self._rc_step >= DELETE_BAR_STEPS:
            self._rc_job = None
            self._rc_fire()
        else:
            self._rc_job = self.after(DELETE_BAR_INTERVAL, self._rc_tick)

    def _rc_release(self, _=None):
        if getattr(self, "_rc_job", None):
            self.after_cancel(self._rc_job)
            self._rc_job = None
        self._rc_active = False
        self.ts_lbl.config(text=getattr(self, "_last_ts", "—"), fg=TEXT_DIM)
        self.badge.config(text=" IDLE ", fg=ACCENT, bg=ACCENT_DIM)
        self.badge_frame.config(bg=ACCENT_DIM)

    def _rc_fire(self):
        self._rc_active = False
        self.ts_lbl.config(text="DELETING", fg=RED)
        self.after(50, lambda: self.app._remove_card(self))

    def __init__(self, parent, host, app, **kw):
        super().__init__(parent, bg=CARD_BG, **kw)
        self.host = dict(host)
        self.is_website = self.host.get("is_website", False)
        self.app  = app
        self._blink_cb    = None
        self._blink_speed = None
        self._cur_sev     = "green"
        self.configure(highlightbackground=BORDER, highlightthickness=1, padx=12, pady=22)
        self.grid_propagate(False)
        self._build()
        self.after(50, self._apply_dim)
        self._rc_job = None
        self._rc_step = 0
        self._rc_active = False
        self._webview_job = None
        self._webview_showing = False
        self._webview_widget = None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_ghost = None
        self._latency_history = []
        self._graph_showing = False
        self._graph_hide_job = None


    def _is_unconfigured(self):
        vm  = (self.host.get("vm_name") or "").strip()
        ip  = (self.host.get("ip") or "").strip()
        has_default_name = bool(_DEFAULT_VM_PATTERN.match(vm)) or not vm
        has_no_ip        = not ip or ip == "0.0.0.0"
        return has_default_name and has_no_ip

    def _apply_dim(self):
        dim = self._is_unconfigured()
        bg       = DIM_CARD_BG   if dim else CARD_BG
        border   = DIM_BORDER    if dim else BORDER
        vm_fg    = DIM_TEXT      if dim else TEXT
        ip_fg    = DIM_TEXT_MID  if dim else TEXT_DIM
        stat_fg  = DIM_TEXT_MID  if dim else TEXT_DIM
        dot_fg   = DIM_BORDER    if dim else BORDER
        badge_fg = DIM_ACCENT    if dim else ACCENT
        badge_bg = DIM_ACCENT_BG if dim else ACCENT_DIM

        self.configure(bg=bg, highlightbackground=border)
        self.vm_entry.config(bg=bg, fg=vm_fg)
        current_badge = self.badge.cget("text").strip()
        if current_badge == "UNNAMED":
            self.badge.config(fg=TEXT_DIM, bg=BORDER)
            self.badge_frame.config(bg=BORDER)
        elif current_badge == "UNCONFIGURED":
            self.badge.config(fg="#c084fc", bg="#2e1065")
            self.badge_frame.config(bg="#2e1065")
        elif current_badge in ("IDLE", ""):
            self.badge.config(fg=ACCENT, bg=ACCENT_DIM)
            self.badge_frame.config(bg=ACCENT_DIM)
        self.ip_entry.config(bg=bg, fg=ip_fg)
        self.ip_saved.config(bg=bg)
        self.phys_entry.config(bg=bg)
        self.sys_entry.config(bg=bg)
        for key, w in self.stat_w.items():
            if w.cget("text") in ("—", ""):
                w.config(fg=stat_fg, bg=bg)
        for d in self.dots:
            if d.cget("fg") in (BORDER, DIM_BORDER):
                d.config(fg=dot_fg, bg=bg)
        self.ts_lbl.config(bg=bg)
        self._tint_children(bg)

    def _ph_field(self, parent, key, placeholder, font_spec, fg_active=TEXT, width=18):
        stored = self.host.get(key, "") or ""
        var = tk.StringVar(value=stored if stored else placeholder)
        fg_init = TEXT_DIM if not stored else fg_active
        e = tk.Entry(parent, textvariable=var, font=font_spec,
                     fg=fg_init, bg=CARD_BG, insertbackground=TEXT,
                     relief="flat", bd=0, highlightthickness=0, width=width)
        def focus_in(_=None):
            if var.get() == placeholder:
                var.set("")
                e.config(fg=fg_active)
        def focus_out(_=None):
            v = var.get().strip()
            if not v:
                var.set(placeholder)
                e.config(fg=TEXT_DIM)
                self.host[key] = ""
            else:
                self.host[key] = v
                e.config(fg=fg_active)
            save_hosts([c.host for c in self.app.cards])
            self._apply_dim()
        def key_release(_=None):
            v = var.get()
            if v != placeholder:
                self.host[key] = v
                save_hosts([c.host for c in self.app.cards])
            self._apply_dim()
        e.bind("<FocusIn>", focus_in)
        e.bind("<FocusOut>", focus_out)
        e.bind("<KeyRelease>", key_release)
        return e, var
    
    def _capture_natural_height(self):
        if self._locked_height:
            return
        self.update_idletasks()
        h = self.winfo_height()
        if h > 10:
            self._locked_height = h

    def _schedule_webview(self, url):
        if not HAS_WEBVIEW:
            return
        if hasattr(self, "_webview_show_job") and self._webview_show_job:
            self.after_cancel(self._webview_show_job)
            self._webview_show_job = None
        self._webview_show_job = self.after(5000, lambda: self._show_webview(url)) #DAGGER


    def _animate_dot(self):
        # Self-healing check: only animate if the webview is active and the dot exists
        if not self._webview_showing or not hasattr(self, "_status_dot") or not self._status_dot.winfo_exists():
            return

        self._blink_state = not self._blink_state
        current_fg = GREEN if self._blink_state else CARD_BG
        
        try:
            self._status_dot.configure(fg=current_fg)
        except Exception:
            return 

        self.after(500, self._animate_dot)

    def _show_webview(self, url):
        if not self._locked_height or self._locked_height < 10:
            return

        current_width = self.winfo_width()
        if current_width < 10: current_width = 520 

        self.configure(height=self._locked_height)
        self.grid_propagate(False)
        self.pack_propagate(False)

        self._webview_showing = True
        self._content.pack_forget()

        # 1. Cleanup old elements
        if hasattr(self, "_web_header") and self._web_header.winfo_exists():
            self._web_header.destroy()
        if hasattr(self, "_loading_overlay"):
            self._loading_overlay.destroy()
        if hasattr(self, "_content_container") and self._content_container.winfo_exists():
            self._content_container.destroy()

        self._web_frame.configure(height=self._locked_height, width=current_width)
        self.configure(padx=0, pady=0, height=self._locked_height)
        self.grid_propagate(False)
        self.pack_propagate(False)
        self._web_frame.pack(fill="both", expand=True)
        self._web_frame.pack_propagate(False)

        self._web_frame.bind("<MouseWheel>", self._forward_scroll, add="+")
        self._web_frame.bind("<Button-4>", self._forward_scroll, add="+")
        self._web_frame.bind("<Button-5>", self._forward_scroll, add="+")

        # Only build the header once — skip if already present
        if not hasattr(self, "_web_header") or not self._web_header.winfo_exists():
            self._web_header = tk.Frame(self._web_frame, bg=CARD_BG, height=22)
            self._web_header.pack(side="top", fill="x")
            self._web_header.pack_propagate(False)

            if hasattr(self, "_web_sep") and self._web_sep.winfo_exists():
                self._web_sep.destroy()

            self._web_sep = tk.Frame(
                self._web_frame,
                bg=BORDER,
                height=1
            )
            self._web_sep.pack(side="top", fill="x")

            self._status_dot = tk.Label(self._web_header, text="●", font=("Consolas", 7), fg=GREEN, bg=CARD_BG)
            self._status_dot.place(x=8, rely=0.5, anchor="w")

            domain = url.split("//")[-1].split("/")[0]

            tk.Label(
                self._web_header,
                text=domain,
                font=("Consolas", 7, "bold"),
                fg=TEXT_DIM,
                bg=CARD_BG
            ).place(x=24, rely=0.5, anchor="w")

            tk.Label(
                self._web_header,
                text="LIVE",
                font=("Consolas", 6, "bold"),
                fg="#10b981",
                bg=CARD_BG
            ).place(
                relx=1.0,
                x=-8,
                rely=0.5,
                anchor="e"
            )
            # Make header scrollable too
            self._bind_scroll_recursive(self._web_header)

        else:
            # Header exists — just restart the dot animation
            if not hasattr(self, "_status_dot") or not self._status_dot.winfo_exists():
                self._status_dot = tk.Label(self._web_header, text="●", font=("Consolas", 7), fg=GREEN, bg=CARD_BG)
                self._status_dot.place(x=8, y=8)

        self._blink_state = True
        self._animate_dot()

        # 3. Create a dedicated container for the content
        if hasattr(self, "_content_container"):
            try:
                self._content_container.destroy()
            except Exception:
                pass
            
        self._content_container = tk.Frame(self._web_frame, bg=CARD_BG)
        self._content_container.pack(side="top", fill="both", expand=True, anchor="n")

        # 4. Add Animated Spinner
        self._loading_overlay = tk.Frame(self._content_container, bg=CARD_BG)
        self._loading_overlay.place(relx=0.5, rely=0.5, anchor="center")
        self._loading_dots = []
        dot_row = tk.Frame(self._loading_overlay, bg=CARD_BG)
        dot_row.pack()
        for _ in range(5):
            d = tk.Label(dot_row, text="·", font=("Consolas", 18), fg=BORDER, bg=CARD_BG)
            d.pack(side="left", padx=3)
            self._loading_dots.append(d)

        self._content_container.bind("<MouseWheel>", self._forward_scroll, add="+")
        self._content_container.bind("<Button-4>", self._forward_scroll, add="+")
        self._content_container.bind("<Button-5>", self._forward_scroll, add="+")

        def animate_spinner():
            if not self._loading_dots or not self._loading_dots[0].winfo_exists(): return
            self._spin_state = (getattr(self, "_spin_state", 0) + 1) % len(self._loading_dots)
            for i, d in enumerate(self._loading_dots):
                d.config(fg=TEXT if i == self._spin_state else BORDER)
            self.after(180, animate_spinner)
        animate_spinner()

        # 5. Background Task (Offset kept at 105px for best fit)
        import threading
        def fetch_preview():
            try:
                from playwright.sync_api import sync_playwright
                from PIL import Image
                import io

                is_slow_local_site = any(k in url.lower() for k in ["gov.ph", "zamboanga", "httpbin"])
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=[
                        "--disable-gl-drawing-for-tests",
                        "--disable-extensions",
                        "--disable-background-networking",
                        "--block-new-web-contents",
                        "--no-first-run",
                        "--disable-dev-shm-usage",
                        "--disable-plugins",
                        "--disable-java",
                        "--disable-remote-fonts",
                        "--disable-sync",
                        "--disable-translate",
                        "--disable-default-apps",
                        "--disable-background-timer-throttling",
                        "--disable-client-side-phishing-detection",
                        "--disable-hang-monitor",
                        "--disable-prompt-on-repost",
                        "--safebrowsing-disable-auto-update",
                        "--no-pings",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ])
                    context = browser.new_context(
                        viewport={"width": 1200, "height": 800},
                        java_script_enabled=True,
                        accept_downloads=False,
                        bypass_csp=False,
                        ignore_https_errors=False,
                        has_touch=False,
                        is_mobile=False,
                        permissions=[],
                        geolocation=None,
                        color_scheme="dark",
                        extra_http_headers={
                            "DNT": "1",
                        },
                    )

                    page = context.new_page()
                    
                    is_local_ip = bool(re.match(r"https?://\d{1,3}(\.\d{1,3}){3}", url))

                    page.route("**/*", lambda route: route.abort()
                        if route.request.resource_type in ["media", "websocket", "eventsource"]
                        or any(k in route.request.url for k in [
                            "analytics", "tracking", "doubleclick",
                            "google-analytics", "hotjar", "facebook.com/tr",
                        ])
                        else route.continue_()
                    )
                    wait_until = "domcontentloaded" if is_local_ip else (
                        "commit" if is_slow_local_site else "networkidle"
                    )
                    timeout = 8000 if is_local_ip else (6000 if is_slow_local_site else 12000)

                    try:
                        page.goto(url, wait_until=wait_until, timeout=timeout)
                    except Exception as e:
                        print(f"[WEBVIEW] goto failed: {e}")
                        pass

                    print(f"[WEBVIEW] url='{url}' | title='{page.title()}' | current='{page.url}'")


                    if is_local_ip:
                        try:
                            page.wait_for_selector("nav, header, .navbar, #app", timeout=5000)
                        except Exception:
                            pass
                        try:
                            page.wait_for_function(
                                "() => [...document.images].every(i => i.complete)",
                                timeout=5000
                            )
                        except Exception:
                            pass

                    try:
                        scale_css = "" if is_local_ip else "transform: scale(0.90); transform-origin: top center; position: relative; top: 5px;"
                        page.evaluate(f"""() => {{
                            const style = document.createElement('style');
                            style.innerHTML = `body {{ margin: 0 !important; padding: 0 !important; {scale_css} width: 100% !important; }}`;
                            document.head.appendChild(style);
                            window.scrollTo(0, 0);
                        }}""")
                    except Exception:
                        pass

                    page.wait_for_timeout(2000 if is_local_ip else (2000 if is_slow_local_site else 1500))

                    
                    img_data = page.screenshot(type="jpeg", quality=60, full_page=False)
                    context.close(); browser.close()

                img = Image.open(io.BytesIO(img_data))
                target_h = self._locked_height - 22
                ratio = target_h / img.height
                target_w = int(img.width * ratio)

                img.thumbnail(
                    (current_width, target_h),
                    Image.Resampling.LANCZOS
                )
                self.after(0, lambda: display_image(img))
            except Exception as e: print(f"PLAYWRIGHT FETCH ERROR: {e}")

        def display_image(pil_img):
            from PIL import ImageTk
            if not self._webview_showing: return
            if hasattr(self, "_loading_overlay"): self._loading_overlay.destroy()
            for child in self._content_container.winfo_children(): child.destroy()
            self._preview_photo = ImageTk.PhotoImage(pil_img)
            
            tk.Label(
                self._content_container,
                image=self._preview_photo,
                bg=CARD_BG
            ).pack(side="top", anchor="n")
            # Recursively bind mouse wheel to all widgets inside the container
            self._bind_scroll_recursive(self._content_container)

        threading.Thread(target=fetch_preview, daemon=True).start()
        if hasattr(self, "_webview_hide_job") and self._webview_hide_job:
            self.after_cancel(self._webview_hide_job)
            self._webview_hide_job = None
        self._webview_hide_job = self.after(40000, self._hide_webview)



    def _hide_webview(self):
        if not self._webview_showing:
            return
        self._webview_showing = False
        self._web_frame.pack_forget()
        if hasattr(self, "_webview_widget") and self._webview_widget:
            try:
                self._webview_widget.destroy()
            except Exception:
                pass
            self._webview_widget = None
        self._content.pack(fill="both", expand=True)
        self.configure(padx=12, pady=22)
        if self._locked_height:
            self.configure(height=self._locked_height)
        self.grid_propagate(False)
        self.pack_propagate(False)

    def _show_latency_graph(self):
        if self._graph_showing or self._webview_showing:
            return
        if not self._latency_history or not any(v is not None for v in self._latency_history):
            return
        if not self._locked_height or self._locked_height < 10:
            return

        self._graph_showing = True
        self._content.pack_forget()

        self._graph_frame = tk.Frame(self, bg=CARD_BG)
        self._graph_frame.pack(fill="both", expand=True)
        self._graph_frame.pack_propagate(False)

        # Header bar
        hdr = tk.Frame(self._graph_frame, bg=CARD_BG, height=22)
        hdr.pack(side="top", fill="x")
        hdr.pack_propagate(False)
        tk.Frame(self._graph_frame, bg=BORDER, height=1).pack(side="top", fill="x")

        _sev_fg = SEV_STYLE.get(self._cur_sev, (GREEN, None, None))[0]
        self._graph_dot = tk.Label(hdr, text="●", font=("Consolas", 7), fg=_sev_fg, bg=CARD_BG)
        self._graph_dot.place(x=8, rely=0.5, anchor="w")

        def _graph_dot_cb(state):
            if not self._graph_showing or not self._graph_dot.winfo_exists():
                try: self.app._blink_mild_subs.remove(_graph_dot_cb)
                except ValueError: pass
                return
            self._graph_dot.config(fg=_sev_fg if state else CARD_BG)

        self.app._blink_mild_subs.append(_graph_dot_cb)
        tk.Label(hdr, text="LATENCY GRAPH", font=("Consolas", 7, "bold"),
         fg=TEXT_DIM, bg=CARD_BG).place(x=22, rely=0.5, anchor="w")
        tk.Label(hdr, text="", font=("Consolas", 6, "bold"),
                fg="#10b981", bg=CARD_BG).place(relx=1.0, x=-8, rely=0.5, anchor="e")

        # Canvas for graph
        self._graph_canvas = tk.Canvas(
            self._graph_frame, bg=CARD_BG,
            highlightthickness=0
        )
        self._graph_canvas.pack(fill="both", expand=True, padx=8, pady=(4, 6))

        self._graph_canvas.bind("<MouseWheel>", self._forward_scroll)

        def _on_mousewheel(self, event):
            # Forward scroll to main scrollable area
            if hasattr(self.app, 'scroll') and hasattr(self.app.scroll, '_mw'):
                self.app.scroll._mw(event)
            return "break"  # Prevent further propagation
        
        # Bind resize event AFTER canvas is created
        self._graph_canvas.bind("<Configure>", self._on_graph_resize)

        self.configure(padx=0, pady=0)
        if self._locked_height:
            self.configure(height=self._locked_height)
        self.grid_propagate(False)
        self.pack_propagate(False)

        if hasattr(self, "_graph_hide_job") and self._graph_hide_job:
            self.after_cancel(self._graph_hide_job)
        self._graph_hide_job = self.after(15000, self._hide_latency_graph)

        self._graph_anim_step = 0
        self._graph_pulse_job = None
        self.after(50, self._animate_graph_drawIn)

    def _redraw_graph(self):
        if not self._graph_showing:
            return
        if not hasattr(self, "_graph_canvas") or not self._graph_canvas.winfo_exists():
            return

        self._graph_canvas.update_idletasks()
        W = self._graph_canvas.winfo_width()
        H = self._graph_canvas.winfo_height()
        
        # If window is minimized or too small, wait and try again
        if W < 100 or H < 100:
            self.after(500, self._redraw_graph)
            return

        self._graph_canvas.delete("all")
        data = self._latency_history[-50:]
        n = len(data)
        if n < 2:
            return

        valid = [v for v in data if v is not None]
        if not valid:
            max_ms, min_ms = 1, 0
        else:
            max_ms = max(valid) or 1
            min_ms = min(valid) or 0

        # Adjust padding based on available width
        STATS_H = 18
        pad_top = 10
        pad_bot = 32
        
        # Responsive padding - smaller when window is narrow
        if W < 300:
            pad_l = 20
            pad_r = 5
        elif W < 500:
            pad_l = 30
            pad_r = 8
        else:
            pad_l = 44
            pad_r = 10
        
        graph_h = max(30, H - pad_top - pad_bot - STATS_H)  # Ensure minimum height
        graph_w = max(50, W - pad_l - pad_r)  # Ensure minimum width

        def x_of(i):
            if n <= 1:
                return pad_l
            return pad_l + (i / max(1, n - 1)) * graph_w

        def y_of(v):
            if max_ms == min_ms:
                return pad_top + graph_h * 0.5
            return pad_top + (1 - (v - min_ms) / max(1, max_ms - min_ms)) * graph_h

        floor_y = pad_top + graph_h

        # ── Grid lines + Y labels (skip if too narrow) ──
        if W > 200:
            for frac, label in [(0.0, str(max_ms) + "ms"), (0.5, str((max_ms + min_ms) // 2) + "ms"), (1.0, str(min_ms) + "ms")]:
                gy = pad_top + frac * graph_h
                self._graph_canvas.create_line(pad_l, gy, W - pad_r, gy, fill=BORDER, dash=(3, 5))
                self._graph_canvas.create_text(pad_l - 4, gy, text=label,
                    font=("Consolas", 7), fill=TEXT_DIM, anchor="e")

        # ── X-axis time labels (skip if too narrow) ──
        if W > 250:
            x_ticks = [0, n // 4, n // 2, 3 * n // 4, n - 1]
            for ti in x_ticks:
                tx = x_of(ti)
                offset = ti - (n - 1)
                lbl = "now" if offset == 0 else str(offset)
                fg = TEXT_DIM if offset == 0 else "#2a3340"
                self._graph_canvas.create_text(tx, floor_y + 8, text=lbl,
                    font=("Consolas", 7), fill=fg, anchor="center")

        # ── Build Y positions ──
        y_positions = []
        for i, v in enumerate(data):
            if v is not None:
                y_positions.append(y_of(v))
            else:
                y_positions.append(floor_y)

        # ── Fill under graph ──
        fill_pts = [pad_l, floor_y]
        for i in range(n):
            px = x_of(i)
            py = y_positions[i]
            fill_pts += [px, py]
        fill_pts += [x_of(n-1), floor_y]
        self._graph_canvas.create_polygon(fill_pts, fill="#0c2a1a", outline="")

        # ── Draw RED fill at bottom for loss points ──
        for i, v in enumerate(data):
            if v is None:
                px = x_of(i)
                # Scale marker size based on width
                marker_w = max(2, min(6, W // 100))
                self._graph_canvas.create_rectangle(
                    px - marker_w, floor_y - 8, px + marker_w, floor_y,
                    fill="#2a0d0c", outline=""
                )

        # ── Draw lines (thinner when window is small) ──
        line_width = 1 if W < 400 else 2
        for i in range(n - 1):
            x1 = x_of(i)
            x2 = x_of(i + 1)
            y1 = y_positions[i]
            y2 = y_positions[i + 1]
            
            current = data[i]
            next_val = data[i + 1]
            
            if current is None or next_val is None:
                lc = RED
            else:
                if next_val <= 50:
                    lc = GREEN
                elif next_val <= 150:
                    lc = YELLOW
                elif next_val <= 300:
                    lc = ORANGE
                else:
                    lc = RED
            
            self._graph_canvas.create_line(x1, y1, x2, y2,
                fill=lc, width=line_width, smooth=False,
                capstyle="round", joinstyle="round")

        # ── Draw dots and X markers for EACH point (scale sizes) ──
        dot_scale = 1.0
        if W < 400:
            dot_scale = 0.6
        elif W < 600:
            dot_scale = 0.8

        for i, v in enumerate(data):
            px = x_of(i)
            is_last = (i == n - 1)
            py = y_positions[i]

            if v is not None:
                dc = GREEN if v <= 50 else YELLOW if v <= 150 else ORANGE if v <= 300 else RED
                if is_last:
                    # Last dot drawn by pulse animator; draw base dot here
                    r = max(2, int(4 * dot_scale))
                    self._graph_canvas.create_oval(px - r, py - r, px + r, py + r,
                        fill=dc, outline="")
                else:
                    # Non-last: small dot + subtle dim glow ring
                    r = max(2, int(2.5 * dot_scale))
                    glow_r = r + 2
                    self._graph_canvas.create_oval(
                        px - glow_r, py - glow_r, px + glow_r, py + glow_r,
                        fill="", outline=dc, width=1, stipple="gray25"
                    )
                    self._graph_canvas.create_oval(px - r, py - r, px + r, py + r,
                        fill=dc, outline="")

                if W > 250:
                    font_size = int(7 * dot_scale)
                    self._graph_canvas.create_text(px, py - 12,
                        text=f"{v}ms", font=("Consolas", max(6, font_size), "bold"),
                        fill=dc, anchor="s")
            else:
                # Loss point: red X
                if W > 150:
                    r = max(3, int(4 * dot_scale))
                    self._graph_canvas.create_line(px - r, py - r, px + r, py + r,
                        fill=RED, width=max(1, int(line_width) + 1))
                    self._graph_canvas.create_line(px - r, py + r, px + r, py - r,
                        fill=RED, width=max(1, int(line_width) + 1))

        # ── Stats bar (scale text if needed) ──
        bar_y = H - STATS_H
        self._stats_rect_id = self._graph_canvas.create_rectangle(
            pad_l, bar_y, W - pad_r, H, fill=CARD_BG, outline=""
        )

        loss_count = sum(1 for v in data if v is None)
        avg_val    = int(sum(valid) / len(valid)) if valid else 0
        min_val    = min(valid) if valid else 0
        max_val    = max(valid) if valid else 0

        stats = [
            ("AVG",      f"{avg_val}ms",     GREEN  if avg_val <= 50 else YELLOW if avg_val <= 150 else RED),
            ("MIN",      f"{min_val}ms",     GREEN),
            ("MAX",      f"{max_val}ms",     GREEN  if max_val <= 50 else YELLOW if max_val <= 150 else ORANGE if max_val <= 300 else RED),
            ("LOSS",     f"{loss_count}pkt", RED    if loss_count > 0 else GREEN),
        ]

        avail_w = (W - pad_r) - (pad_l + 4)
        if avail_w > 100:  # Only draw stats if enough space
            col_w   = avail_w // len(stats)
            font_size = 7 if W > 300 else 6
            for ci, (label, value, color) in enumerate(stats):
                cx = pad_l + 4 + ci * col_w + col_w // 2
                pair = f"{label} "
                self._graph_canvas.create_text(cx, bar_y + STATS_H // 2,
                    text=pair, font=("Consolas", font_size), fill=TEXT_DIM, anchor="e")
                self._graph_canvas.create_text(cx, bar_y + STATS_H // 2,
                    text=value, font=("Consolas", font_size, "bold"), fill=color, anchor="w")

    def _hide_latency_graph(self):

        if hasattr(self, "_stats_rect_id"):
            del self._stats_rect_id

        if hasattr(self, "_graph_pulse_job") and self._graph_pulse_job:
            self.after_cancel(self._graph_pulse_job)
            self._graph_pulse_job = None

        if hasattr(self, "_graph_hide_job") and self._graph_hide_job:
            self.after_cancel(self._graph_hide_job)
            self._graph_hide_job = None
        if not self._graph_showing:
            return
        self._graph_showing = False
        if hasattr(self, "_graph_dot"):
            try: self.app._blink_mild_subs.remove(
                next(cb for cb in self.app._blink_mild_subs
                    if getattr(cb, "__qualname__", "").endswith("_graph_dot_cb")), )
            except (ValueError, StopIteration): pass
        if hasattr(self, "_graph_frame") and self._graph_frame.winfo_exists():
            self._graph_frame.destroy()
        self._content.pack(fill="both", expand=True)
        self.configure(padx=12, pady=22)
        if self._locked_height:
            self.configure(height=self._locked_height)
        self.grid_propagate(False)
        self.pack_propagate(False)

    def _build(self):
        self._content = tk.Frame(self, bg=CARD_BG)
        self._content.pack(fill="both", expand=True)
        self._view_area = tk.Frame(self._content, bg=CARD_BG, height=157)
        self._view_area.pack(fill="both", expand=True)
        self._view_area.pack_propagate(False)

        self._web_frame = tk.Frame(self, bg=CARD_BG, width=520, height=0)
        self._web_frame.pack_propagate(False)
        self._locked_height = None

        top = tk.Frame(self._view_area, bg=CARD_BG)
        top.pack(fill="x", pady=(0, 0))

        self.vm_entry, self.vm_var = self._ph_field(
            top, "vm_name", "VM Name", ("Consolas", 15, "bold"), fg_active=TEXT, width=14)
        self.vm_entry.pack(side="left")

        self.badge_frame = tk.Frame(top, bg=ACCENT_DIM, padx=7, pady=2)
        self.badge_frame.pack(side="right")
        vm = (self.host.get("vm_name") or "").strip()
        ip = (self.host.get("ip") or "").strip()
        has_default_name = bool(_DEFAULT_VM_PATTERN.match(vm)) or not vm
        if has_default_name and not ip:
            badge_text = " UNNAMED "
        elif not ip:
            badge_text = " UNCONFIGURED "
        else:
            badge_text = " ON HOLD "
        if badge_text.strip() == "UNNAMED":
            badge_fg, badge_bg = TEXT_DIM, BORDER
        elif badge_text.strip() == "UNCONFIGURED":
            badge_fg, badge_bg = "#c084fc", "#2e1065"
        else:
            badge_fg, badge_bg = ACCENT, ACCENT_DIM
        self.badge = tk.Label(self.badge_frame, text=badge_text,
                            font=("Consolas", 8, "bold"), fg=badge_fg, bg=badge_bg)
        self.badge_frame.config(bg=badge_bg)
        self.badge.pack()

        ip_row = tk.Frame(self._view_area, bg=CARD_BG)
        ip_row.pack(fill="x", pady=(0, 0))

        stored_ip = self.host.get("ip", "") or ""
        self.ip_var = tk.StringVar(value=stored_ip if stored_ip else "0.0.0.0")
        self.ip_entry = tk.Entry(ip_row, textvariable=self.ip_var,
                                 font=("Consolas", 9), fg=TEXT_DIM,
                                 bg=CARD_BG, insertbackground=TEXT,
                                 relief="flat", bd=0, highlightthickness=0, width=16)
        self.ip_entry.pack(side="left", fill="x", expand=True)
        ip_row.pack(fill="x")
        self.ip_saved = tk.Label(ip_row, text="", font=("Consolas", 7), fg=GREEN, bg=CARD_BG)
        self.ip_saved.pack(side="left", padx=(3, 0))

        self.ip_entry.bind("<FocusIn>",    self._ip_focus_in)
        self.ip_entry.bind("<FocusOut>",   self._ip_save)
        self.ip_entry.bind("<Return>",     self._ip_save)
        self.ip_entry.bind("<KeyRelease>", self._ip_key)

        phys_sys_row = tk.Frame(self._view_area, bg=CARD_BG)
        phys_sys_row.pack(fill="x", pady=(0, 0))

        self.phys_entry, _ = self._ph_field(
            phys_sys_row, "physical_name", "  ",
            ("Consolas", 8), fg_active=TEXT_DIM, width=18)
        self.phys_entry.pack(side="left")
        tk.Label(phys_sys_row, text="(", font=("Consolas", 8), fg=TEXT_DIM, bg=CARD_BG).pack(side="left")
        self.sys_entry, _ = self._ph_field(
            phys_sys_row, "system_name", "  ",
            ("Consolas", 8), fg_active=TEXT_DIM, width=11)
        self.sys_entry.pack(side="left")
        tk.Label(phys_sys_row, text=")", font=("Consolas", 8), fg=TEXT_DIM, bg=CARD_BG).pack(side="left")

        # ── Port and HTTP fields ──
        port_http_row = tk.Frame(self._view_area, bg=CARD_BG)
        port_http_row.pack(fill="x", pady=(4, 0))

        

        tk.Label(port_http_row, text="PORT:", font=("Consolas", 7), fg=TEXT_DIM, bg=CARD_BG).pack(side="left", padx=(0, 3))
        self.port_entry, _ = self._ph_field(
            port_http_row, "port", "",
            ("Consolas", 8), fg_active=TEXT_DIM, width=6)
        self.port_entry.pack(side="left", padx=(0, 8))

        tk.Label(port_http_row, text="ENDPOINT:", font=("Consolas", 7), fg=TEXT_DIM, bg=CARD_BG).pack(side="left", padx=(0, 3))
        self.endpoint_entry, _ = self._ph_field(
            port_http_row, "endpoint", "/api",
            ("Consolas", 8), fg_active=TEXT_DIM, width=10)
        self.endpoint_entry.pack(side="left")

                
        tk.Frame(self._view_area, bg=BORDER, height=1).pack(fill="x", pady=(3, 3))

        stats = tk.Frame(self._view_area, bg=CARD_BG)
        stats.pack(fill="x")
        self.stat_w = {}
        for lbl, key in [("AVERAGE PING", "avg"), ("LOSS", "loss"), ("PACKETS RECV", "recv"), ("PORT", "port_status"), ("HTTP/S", "http_status")]:
            col = tk.Frame(stats, bg=CARD_BG)
            col.pack(side="left", expand=True)
            tk.Label(col, text=lbl, font=("Consolas", 6), fg=TEXT_DIM, bg=CARD_BG).pack()
            # Use smaller font for port and HTTP to prevent text clipping
            f_size = 9 if key in ("port_status", "http_status") else 11
            v = tk.Label(col, text="—", font=("Consolas", f_size, "bold"), fg=TEXT, bg=CARD_BG)
            v.pack()
            self.stat_w[key] = v

        dot_row = tk.Frame(self._view_area, bg=CARD_BG)
        dot_row.pack(fill="x", pady=(4, 0))
        self.dots = []
        for _ in range(PING_COUNT):
            d = tk.Label(dot_row, text="●", font=("Consolas", 10), fg=BORDER, bg=CARD_BG)
            d.pack(side="left", padx=1, pady=(18, 0))
            self.dots.append(d)

        
        bot = tk.Frame(self._content, bg=CARD_BG)
        bot.pack(fill="x", pady=(12, 0))

        self.ts_lbl = tk.Label(bot, text="", font=("Consolas", 7), fg=TEXT_DIM, bg=CARD_BG)
        self.ts_lbl.pack(side="left")

        # Create a container that ALWAYS exists (reserves space for the button)
        devices_container = tk.Frame(bot, bg=CARD_BG, width=95, height=24)
        devices_container.pack(side="right", padx=(0, 6))
        devices_container.pack_propagate(False)  # Keep fixed size even when empty

        # Devices button — only for raw IPs (not domains/websites)
        target = (self.host.get("ip") or "").strip()
        is_raw_ip = bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target))
        is_website = self.host.get("is_website", False)

        if is_raw_ip and not is_website:
            # Schedule button creation after 3 seconds
            self.after(5000, lambda: self._create_devices_button(devices_container))

        
        self._lp_job = None
        self._dragging = False
        self._bind_long_press(self)
        self._bind_right_hold(self)
        self._init_card_drag(self)
        # Capture natural height before any webview activity
        self.after(200, self._capture_natural_height)
        self.after(250, self._build_tint_cache)

    def _open_devices_modal(self):
        ip = (self.host.get("ip") or "").strip()
        if not ip or ip == "0.0.0.0":
            return

        modal = tk.Toplevel(self.winfo_toplevel())
        modal.title("")
        modal.configure(bg=BG)
        modal.resizable(True, True)
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        root = self.winfo_toplevel()
        root.update_idletasks()



        w, h = 680, 520
        card_x = self.winfo_rootx()
        card_y = self.winfo_rooty()
        card_w = self.winfo_width()
        card_h = self.winfo_height()
        x = card_x + (card_w - w) // 2
        y = card_y + (card_h - h) // 2
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = max(0, min(x, screen_w - w))
        y = max(0, min(y, screen_h - h))
        modal.geometry(f"{w}x{h}+{x}+{y}")

        try:
            root._dark_titlebar_for(modal)
        except Exception:
            pass

        # ── Header ──
        hdr = tk.Frame(modal, bg="#060a10", padx=16, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="CONNECTED", font=("Consolas", 11, "bold"),
                 fg=TEXT, bg="#060a10").pack(side="left")
        tk.Label(hdr, text="DEVICES", font=("Consolas", 11, "bold"),
                 fg=TEXT, bg="#060a10").pack(side="left")
        vm = self.host.get("vm_name", "")
        tk.Label(hdr, text=f"  {vm} — {ip}/24",
                 font=("Consolas", 8), fg=TEXT_DIM, bg="#060a10").pack(side="left")

        # ── Count bar ──
        count_bar = tk.Frame(modal, bg=CARD_BG, padx=16, pady=6)
        count_bar.pack(fill="x")
        rescan_btn = tk.Button(count_bar, text="⟳ RESCAN",
                               font=("Consolas", 8), fg=TEXT_DIM, bg=CARD_BG,
                               activeforeground=ACCENT, activebackground=CARD_BG,
                               relief="flat", bd=0, cursor="hand2")
        rescan_btn.pack(side="right")
        self._dev_count_lbl = tk.Label(count_bar, text="[SCANNING]",
                                        font=("Consolas", 8), fg=YELLOW, bg=CARD_BG)
        self._dev_count_lbl.pack(side="left")
        tk.Frame(modal, bg=SILVER, height=1).pack(fill="x")

       # ── Column headers ──
        col_hdr = tk.Frame(modal, bg=BORDER, pady=8)
        col_hdr.pack(fill="x")
        for ci, weight in enumerate([1, 1, 1]):
            col_hdr.columnconfigure(ci, weight=weight, uniform="dev_col")
        tk.Label(col_hdr, text="IP",
                 font=("Consolas", 8, "bold"), fg=SILVER,
                 bg=BORDER, anchor="center"
                 ).grid(row=0, column=0, sticky="ew", padx=8)
        tk.Label(col_hdr, text="HOSTNAME",
                 font=("Consolas", 8, "bold"), fg=SILVER,
                 bg=BORDER, anchor="center"
                 ).grid(row=0, column=1, sticky="ew")
        tk.Label(col_hdr, text="PING",
                 font=("Consolas", 8, "bold"), fg=SILVER,
                 bg=BORDER, anchor="center"
                 ).grid(row=0, column=2, sticky="ew", padx=8)
        tk.Frame(modal, bg=BORDER, height=1).pack(fill="x")

        # ── Scrollable results area ──
        scroll_outer = tk.Frame(modal, bg=CARD_BG)
        scroll_outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_outer, bg=CARD_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_outer, orient="vertical",
                                  style="Dark.Vertical.TScrollbar",
                                  command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=CARD_BG)
        cw = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        inner.bind("<MouseWheel>",
                   lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        modal.bind("<MouseWheel>",
                   lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        DEVICE_COLORS = {
            "phone":    ACCENT,
            "laptop":   GREEN,
            "printer":  YELLOW,
            "camera":   ORANGE,
            "router":   "#c084fc",
            "computer": TEXT,
            "unknown":  TEXT_DIM,
        }

        def render_devices(devices):
            for w in inner.winfo_children():
                w.destroy()
            if not devices:
                tk.Label(inner, text="[NO DEVICES FOUND]",
                         font=("Consolas", 9), fg=TEXT_DIM, bg=CARD_BG,
                         pady=30).pack()
                return

            for i, dev in enumerate(devices):
                row_bg = CARD_BG
                row = tk.Frame(inner, bg=row_bg)
                row.pack(fill="x")
                for ci, weight in enumerate([1, 1, 1]):
                    row.columnconfigure(ci, weight=weight, uniform="dev_col")

                dtype = dev.get("device_type", "computer")
                color = DEVICE_COLORS.get(dtype, TEXT)
                hn = dev.get("hostname", "—")
                if hn == dev["ip"]:
                    hn = "—"
                
                # Show device type as subtitle if hostname is unknown
                dtype = dev.get("device_type", "unknown")
                color = DEVICE_COLORS.get(dtype, TEXT_DIM)
                type_label = dtype.upper() if dtype != "unknown" else "UNKNOWN DEVICE"

                tk.Label(row, text=dev["ip"],
                         font=("Consolas", 10, "bold"),
                         fg=color, bg=row_bg,
                         anchor="center", pady=10
                         ).grid(row=0, column=0, sticky="ew", padx=8)
                tk.Label(row,
                         text=hn if hn != "—" else type_label,
                         font=("Consolas", 9, "bold" if hn == "—" else "normal"),
                         fg=color if hn == "—" else TEXT_DIM,
                         bg=row_bg,
                         anchor="center", pady=10
                         ).grid(row=0, column=1, sticky="ew")
                tk.Label(row, text=dev.get("response_time", "—"),
                         font=("Consolas", 10, "bold"),
                         fg=GREEN, bg=row_bg,
                         anchor="center", pady=10
                         ).grid(row=0, column=2, sticky="ew", padx=8)

                def _enter(e, r=row, rb=row_bg):
                    for w in r.winfo_children():
                        try: w.config(bg=ACCENT_DIM)
                        except: pass
                    r.config(bg=ACCENT_DIM)
                def _leave(e, r=row, rb=row_bg):
                    for w in r.winfo_children():
                        try: w.config(bg=rb)
                        except: pass
                    r.config(bg=rb)
                row.bind("<Enter>", _enter)
                row.bind("<Leave>", _leave)
                for child in row.winfo_children():
                    child.bind("<Enter>", _enter)
                    child.bind("<Leave>", _leave)

        def do_scan():
            self._dev_count_lbl.config(text="[SCANNING FOR DEVICES]", fg=SILVER)
            rescan_btn.config(state="disabled", fg=TEXT_DIM)

            def run():
                devices = scan_network_devices(ip)
                modal.after(0, lambda: finish(devices))

            def finish(devices):
                try:
                    if not inner.winfo_exists():
                        return
                except Exception:
                    return
                render_devices(devices)
                n = len(devices)
                self._dev_count_lbl.config(
                    text=f"{n} DEVICES{'s' if n != 1 else ''} FOUND ON {ip.rsplit('.', 1)[0]}.0/24",
                    fg=GREEN if n > 0 else TEXT_DIM
                )
                rescan_btn.config(state="normal", fg=TEXT_DIM)

            threading.Thread(target=run, daemon=True).start()

        rescan_btn.config(command=do_scan)
        modal.bind("<Escape>", lambda _: modal.destroy())

        # Auto-start scan
        modal.after(200, do_scan)

    def _ip_focus_in(self, _=None):
        if self.ip_var.get() in ("Enter IP…", "0.0.0.0") and not self.host.get("ip"):
            self.ip_var.set("")
            self.ip_entry.config(fg=TEXT)

    def _ip_key(self, _=None):
        self.ip_saved.config(text="")
        if hasattr(self, "_ip_deb"):
            self.after_cancel(self._ip_deb)
        self._ip_deb = self.after(600, self._ip_save)

    def _ip_save(self, _=None):
        val = self.ip_var.get().strip()
        if val and val != "Enter IP…":
            cleaned = clean_host(val)
            if is_valid_host(cleaned):
                old = self.host.get("ip", "")
                self.host["ip"] = cleaned
                self.ip_entry.config(fg=TEXT_DIM)
                self.ip_saved.config(text="✓")
                self.after(2000, lambda: self.ip_saved.config(text=""))
                save_hosts([c.host for c in self.app.cards])
                self._apply_dim()
                if old != cleaned:
                    self._reset_stats()
                    if cleaned != "0.0.0.0":
                        self.after(100, self._ping_single)
            else:
                self.ip_saved.config(text="✗ bad IP")
                self.after(2000, lambda: self.ip_saved.config(text=""))
        elif not val or val == "0.0.0.0":
            self.ip_var.set("0.0.0.0")
            self.ip_entry.config(fg=TEXT_DIM)
            self.host["ip"] = ""
            save_hosts([c.host for c in self.app.cards])
            self._reset_stats()
            self._apply_dim()

    def _stop_blink(self):
        if self._blink_cb:
            subs = (self.app._blink_fast_subs if self._blink_speed == BLINK_FAST
                    else self.app._blink_mild_subs)
            try: subs.remove(self._blink_cb)
            except ValueError: pass
            self._blink_cb = None
        self._blink_speed = None
        self.configure(highlightbackground=BORDER, bg=CARD_BG)
        self._tint_children(CARD_BG)

    # REPLACE WITH:
    def _start_blink(self, fg_on, bg_on, fg_off, bg_off, speed, card_tint=None):
        self._stop_blink()
        self._blink_speed = speed
        def cb(state):
            if state:
                self.badge.config(fg=fg_on,  bg=bg_on)
                self.badge_frame.config(bg=bg_on)
                self.configure(highlightbackground=fg_on, bg=card_tint or CARD_BG)
                self._tint_children(card_tint or CARD_BG)
            else:
                self.badge.config(fg=fg_off, bg=bg_off)
                self.badge_frame.config(bg=bg_off)
                self.configure(highlightbackground=BORDER, bg=CARD_BG)
                self._tint_children(CARD_BG)
        self._blink_cb = cb
        subs = (self.app._blink_fast_subs if speed == BLINK_FAST
                else self.app._blink_mild_subs)
        subs.append(cb)
        cb(self.app._blink_fast_state if speed == BLINK_FAST
        else self.app._blink_mild_state)

    def _build_tint_cache(self):
        skip = {self.badge_frame, self.badge}
        if hasattr(self, "_devices_btn") and self._devices_btn:
            parent = self._devices_btn.master
            if parent:
                skip.add(parent)
        result = []
        def _recurse(w, depth=0):
            if depth > 5:
                return
            for child in w.winfo_children():
                if child in skip:
                    continue
                result.append(child)
                _recurse(child, depth + 1)
        _recurse(self)
        self._tintable = result

    def _tint_children(self, color):
        if not getattr(self, "_tintable", None):
            self._build_tint_cache()
        for w in self._tintable:
            try:
                w.configure(bg=color)
            except Exception:
                pass

            # Special handling for Canvas (graph)
            if isinstance(w, tk.Canvas):
                try:
                    w.config(bg=color)
                except Exception:
                    pass
                if hasattr(self, "_graph_showing") and self._graph_showing:
                    if hasattr(self, "_stats_rect_id"):
                        try:
                            self._graph_canvas.itemconfig(self._stats_rect_id, fill=color)
                        except Exception:
                            pass

            # Also manually handle the graph frame's header labels
            if hasattr(self, "_graph_frame") and w == self._graph_frame:
                for child in w.winfo_children():
                    if isinstance(child, tk.Frame):
                        child.config(bg=color)
                        for sub in child.winfo_children():
                            if isinstance(sub, tk.Label):
                                sub.config(bg=color)


    def _ping_single(self):
        if not self.host.get("ip"):
            return
        self.set_pinging()
        def run():
            self.after(0, lambda: self._latency_history.clear())
            target   = (self.host.get("ip") or "").strip().lower()
            port_val = (self.host.get("port") or "").strip()
            ep       = (self.host.get("endpoint") or "").strip()
            
            is_raw_ip  = bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target))
            has_alpha  = bool(re.search(r"[a-z]", target))
            is_domain  = has_alpha and not is_raw_ip

            if self.is_website:
                is_domain = True

            if is_domain:
                active_port = port_val if port_val else "443"
                
                success_count = 0
                total_time = 0
                valid_times_count = 0
                last_http_result = {}
                http_results = [None] * PING_COUNT
                http_lock = threading.Lock()

                def http_one(idx):
                    result = check_http(target, active_port, ep, timeout=10)
                    with http_lock:
                        http_results[idx] = result
                    is_ok = result.get("status") == "OK" or "200" in str(result.get("status_code", ""))
                    self.after(0, self._update_dot, idx, is_ok)

                http_threads = [threading.Thread(target=http_one, args=(i,), daemon=True)
                                for i in range(PING_COUNT)]
                for t in http_threads:
                    t.start()
                for t in http_threads:
                    t.join(timeout=15)

                for idx, result in enumerate(http_results):
                    if not result:
                        continue
                    is_ok = result.get("status") == "OK" or "200" in str(result.get("status_code", ""))
                    if is_ok:
                        success_count += 1
                        r_time_str = result.get("response_time", "").replace("ms", "").strip()
                        if r_time_str.isdigit():
                            total_time += int(r_time_str)
                            valid_times_count += 1
                    last_http_result = result

                loss_pct = int(((PING_COUNT - success_count) / PING_COUNT) * 100)
                true_avg_ms = f"{int(total_time / valid_times_count)}ms" if valid_times_count > 0 else "—"

                if success_count > 0:
                    self.after(0, self.update_result, {
                        "status": "UP",
                        "avg": "—",
                        "loss": loss_pct,
                        "recv": success_count
                    })
                    self.after(0, self._update_port_status, {
                        "status": "OPEN",
                        "response_time": "Open"
                    })
                    status_code = last_http_result.get("status_code", "200")
                    protocol = last_http_result.get("protocol", "HTTPS")
                    self.after(0, self._update_http_status, {
                        "status": "OK",
                        "status_code": f"{status_code} ({true_avg_ms})",
                        "protocol": protocol,
                        "response_time": true_avg_ms
                    })
                else:
                    port_result = check_port(target, active_port)
                    self.after(0, self._update_port_status, port_result)
                    self.after(0, self.update_result, {
                        "status": "DOWN",
                        "avg": "—",
                        "loss": 100,
                        "recv": 0
                    })
            else:
                def on_dot(idx, success):
                    self.after(0, self._update_dot, idx, success)
                result = ping_host(target, PING_COUNT, dot_callback=on_dot)
                self.after(0, self.update_result, result)
                
                if port_val:
                    port_result = check_port(target, port_val)
                    self.after(0, self._update_port_status, port_result)
                self.after(0, self._update_http_status, {
                    "status": "EMPTY", "response_time": "—",
                    "status_code": "—", "protocol": "—"
                })

        threading.Thread(target=run, daemon=True).start()

    def _update_dot(self, idx, success):
        if idx < len(self.dots):
            self.dots[idx].config(fg=GREEN if success else RED)

    def _update_port_status(self, result):
        status = result.get("status", "ERROR")
        response_time = result.get("response_time", "—")
        
        if status == "OPEN":
            fg = GREEN
            text = f"{response_time}"
        elif status == "CLOSED":
            fg = RED
            text = "Closed"
        elif status == "TIMEOUT":
            fg = ORANGE
            text = "Timeout"
        else:
            fg = TEXT_DIM
            text = "—"
        
        self.stat_w["port_status"].config(text=text, fg=fg)

    def _update_http_status(self, result):
        status = result.get("status", "ERROR")
        status_code = result.get("status_code", "—")
        response_time = result.get("response_time", "—")
        protocol = result.get("protocol", "—")

        if status == "EMPTY":
            fg = TEXT_DIM
            text = "—"
        elif status == "OK":
            fg = GREEN
            text = f"{protocol} {status_code}"
        elif status == "REDIRECT":
            fg = YELLOW
            text = f"{protocol} {status_code}"
        elif status == "CLIENT_ERR":
            fg = ORANGE
            text = f"{protocol} {status_code}"
        elif status == "SERVER_ERR":
            fg = RED
            text = f"{protocol} {status_code}"
        elif status == "TIMEOUT":
            fg = ORANGE
            text = "Timeout"
        elif status == "NO_CONNECTION":
            fg = RED
            text = "No Conn"
        elif status == "ERROR":
            fg = RED
            text = "Err"
        else:
            fg = TEXT_DIM
            text = "—"

        self.stat_w["http_status"].config(text=text, fg=fg)

    def set_pinging(self):
        self._stop_blink()
        self.badge.config(text=" PROBING ", fg=YELLOW, bg=YELLOW_DIM)
        self.badge_frame.config(bg=YELLOW_DIM)
        for d in self.dots:
            d.config(fg=BORDER)

    def _reset_stats(self):
        self._stop_blink()
        self._latency_history = []
        if getattr(self, "_graph_showing", False):
            self._hide_latency_graph()
        self.configure(highlightbackground=BORDER, bg=CARD_BG)
        self._tint_children(CARD_BG)
        for v in self.stat_w.values():
            v.config(text="—", fg=TEXT)
        for d in self.dots:
            d.config(fg=BORDER)
        vm = (self.host.get("vm_name") or "").strip()
        ip = (self.host.get("ip") or "").strip()
        has_default_name = bool(_DEFAULT_VM_PATTERN.match(vm)) or not vm
        if has_default_name and not ip:
            badge_text = " UNNAMED "
        elif not ip:
            badge_text = " UNCONFIGURED "
        else:
            badge_text = " IDLE "
        if badge_text.strip() == "UNNAMED":
            badge_fg, badge_bg = TEXT_DIM, BORDER
        elif badge_text.strip() == "UNCONFIGURED":
            badge_fg, badge_bg = "#c084fc", "#2e1065"
        else:
            badge_fg, badge_bg = ACCENT, ACCENT_DIM
        self.badge.config(text=badge_text, fg=badge_fg, bg=badge_bg)
        self.badge_frame.config(bg=badge_bg)
        self.ts_lbl.config(text="")
        self._apply_dim()

    def update_result(self, stats):
        now    = datetime.datetime.now().strftime("%H:%M:%S")
        status = stats["status"]
        loss   = stats["loss"]
        avg    = stats["avg"]
        recv   = stats["recv"]

        if status in ("TIMEOUT", "UNREACHABLE", "DOWN", "ERROR"):
            sev = "red_blink"
        else:
            sev = loss_severity(loss)

        self._cur_sev = sev
        fg, bg, bspeed = SEV_STYLE[sev]

        badge_map = {
            "UP":          "    OK    ",
            "DOWN":        "   DOWN   ",
            "TIMEOUT":     "NO RESPONSE",
            "UNREACHABLE": "NO RESPONSE",
            "ERROR":       "   ERROR  ",
            "EMPTY":       "   IDLE   ",
        }
        self.badge.config(text=badge_map.get(status, status))

        if bspeed:
            tint = CARD_RED if sev == "red_blink" else CARD_ORANGE if sev == "orange_blink" else CARD_YELLOW
            self._start_blink(fg, bg, TEXT_DIM, BG, bspeed, card_tint=tint)
        else:
            self._stop_blink()
            self.badge.config(fg=fg, bg=bg)
            self.badge_frame.config(bg=bg)
            border_col = fg if sev != "green" else BORDER
            self.configure(highlightbackground=border_col, bg=CARD_BG)
            self._tint_children(CARD_BG)

        self.stat_w["avg"].config(text=avg, fg=fg)
        loss_fg = (GREEN if loss <= 1
                   else RED   if loss == 100
                   else ORANGE if loss >= 50
                   else YELLOW)
        self.stat_w["loss"].config(text=f"{loss}%", fg=loss_fg)
        self.stat_w["recv"].config(text=f"{recv}/{PING_COUNT}", fg=fg)

        for i, d in enumerate(self.dots):
            d.config(fg=fg if i < recv else RED_DIM)
        self._last_ts = f"checked {now}"
        self.ts_lbl.config(text=f"LAST UPDATE: {now}", fg=TEXT_DIM)

        if should_log(sev):
            what = f"{status} | loss={loss}%"
            diag = f"avg={avg}, recv={recv}/{PING_COUNT}, sev={sev}"
            log_event(what, self.host.get("vm_name", ""), self.host.get("ip", ""), diag)

        target = (self.host.get("ip") or "").strip()
        is_domain = bool(re.search(r"[a-zA-Z]", target)) and not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target)
        should_webview = is_domain or self.is_website
        if should_webview and status == "UP" and not self._webview_showing:
            port = (self.host.get("port") or "").strip()
            if port == "443":
                self._schedule_webview(f"https://{target}")
            elif port == "80":
                self._schedule_webview(f"http://{target}")
            elif port:
                scheme = "https" if port == "443" else "http"
                self._schedule_webview(f"{scheme}://{target}:{port}")
            else:
                # No port set — use https for domains, http for local IPs
                is_local_ip = bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target))
                scheme = "http" if is_local_ip else "https"
                self._schedule_webview(f"{scheme}://{target}")
        elif not is_domain and self.host.get("ip"):
            # Parse avg ms into int for graph
            avg_str = stats.get("avg", "—")
            try:
                ms_val = int(str(avg_str).replace("ms", "").replace(" ", "").strip())
            except Exception:
                ms_val = None
            recv = stats.get("recv", 0)
            for i in range(PING_COUNT):
                self._latency_history.append(ms_val if (i < recv and ms_val is not None) else None)
            # Keep last 60 data points
            self._latency_history = self._latency_history[-50:]
            has_valid = any(v is not None for v in self._latency_history)
            if not self._graph_showing and not self._webview_showing and len(self._latency_history) >= PING_COUNT and has_valid:
                self.after(15000, self._show_latency_graph)
            elif self._graph_showing:
                self.after(0, self._redraw_graph)

    def _init_card_drag(self, widget):
        if isinstance(widget, (tk.Frame, tk.Label)):
            widget.bind("<ButtonPress-1>",   self._card_drag_start, add="+")
            widget.bind("<B1-Motion>",       self._card_drag_motion, add="+")
            widget.bind("<ButtonRelease-1>", self._card_drag_release, add="+")
        for child in widget.winfo_children():
            self._init_card_drag(child)

    def _card_drag_start(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._dragging = False

        # Create ghost label that follows cursor
        self._drag_ghost = tk.Toplevel(self)
        self._drag_ghost.overrideredirect(True)
        self._drag_ghost.attributes("-alpha", 0.6)
        self._drag_ghost.configure(bg=ACCENT)
        tk.Label(
            self._drag_ghost,
            text=self.host.get("vm_name", "HOST"),
            font=("Consolas", 10, "bold"),
            fg=BG, bg=ACCENT,
            padx=12, pady=6
        ).pack()
        self._drag_ghost.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        self._drag_ghost.withdraw()

    def _card_drag_motion(self, event):
        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)
        if not self._dragging and (dx > 8 or dy > 8):
            self._dragging = True
            self.configure(highlightbackground=ACCENT)
            # Show ghost once dragging starts
            if self._drag_ghost:
                self._drag_ghost.deiconify()
            # Cancel long-press if user starts dragging
            if hasattr(self, "_lp_job") and self._lp_job:
                self.after_cancel(self._lp_job)
                self._lp_job = None
                self.ts_lbl.config(
                    text=self._last_ts if hasattr(self, "_last_ts") else "—",
                    fg=TEXT_DIM
                )
                self.badge.config(
                    text=self._last_badge if hasattr(self, "_last_badge") else " IDLE ",
                    fg=self._last_badge_fg if hasattr(self, "_last_badge_fg") else ACCENT,
                    bg=self._last_badge_bg if hasattr(self, "_last_badge_bg") else ACCENT_DIM
                )
                self.badge_frame.config(
                    bg=self._last_badge_bg if hasattr(self, "_last_badge_bg") else ACCENT_DIM
                )

        if not self._dragging:
            return

        # Move ghost with cursor
        if self._drag_ghost:
            self._drag_ghost.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

        # Find which card we're hovering over
        x, y = event.x_root, event.y_root
        target = None
        for card in self.app.cards:
            if card is self:
                continue
            cx = card.winfo_rootx()
            cy = card.winfo_rooty()
            cw = card.winfo_width()
            ch = card.winfo_height()
            if cx <= x <= cx + cw and cy <= y <= cy + ch:
                target = card
                break

        # Highlight target
        for card in self.app.cards:
            if card is self:
                continue
            if card is target:
                card.configure(highlightbackground=ACCENT)
            else:
                card.configure(highlightbackground=BORDER)

    def _card_drag_release(self, event):
        # Destroy ghost
        if self._drag_ghost:
            self._drag_ghost.destroy()
            self._drag_ghost = None

        if not getattr(self, "_dragging", False):
            return
        self._dragging = False
        self.configure(highlightbackground=BORDER)

        # Find drop target
        x, y = event.x_root, event.y_root
        target = None
        for card in self.app.cards:
            if card is self:
                continue
            cx = card.winfo_rootx()
            cy = card.winfo_rooty()
            cw = card.winfo_width()
            ch = card.winfo_height()
            if cx <= x <= cx + cw and cy <= y <= cy + ch:
                target = card
                break

        # Reset all highlights
        for card in self.app.cards:
            card.configure(highlightbackground=BORDER)

        if target:
            self.app._swap_cards(self, target)

    def _bind_long_press(self, widget):
            # Only bind on non-interactive widgets to avoid blocking text entry
            if isinstance(widget, (tk.Frame, tk.Label, tk.Canvas)):
                widget.bind("<ButtonPress-1>",   self._lp_press)
                widget.bind("<ButtonRelease-1>", self._lp_release)
            for child in widget.winfo_children():
                self._bind_long_press(child)

    def _lp_press(self, _=None):
        if not self.host.get("ip"):
            return
        self._last_badge = self.badge.cget("text")
        self._last_badge_fg = self.badge.cget("fg")
        self._last_badge_bg = self.badge.cget("bg")
        self.badge.config(text=" PROBING ", fg=YELLOW, bg=YELLOW_DIM)
        self.badge_frame.config(bg=YELLOW_DIM)
        self._lp_step = 0
        self._lp_tick()

    def _lp_tick(self):
        steps = 6
        interval = 2500  // steps   # 100 ms per step
        self._lp_step += 1
        bar = "▓" * self._lp_step + "░" * (steps - self._lp_step)
        self.ts_lbl.config(text=bar, fg=YELLOW)
        if self._lp_step >= steps:
            self._lp_job = None
            self._lp_fire()
        else:
            self._lp_job = self.after(interval, self._lp_tick)

    def _lp_release(self, _=None):
        if hasattr(self, "_lp_job") and self._lp_job:
            self.after_cancel(self._lp_job)
            self._lp_job = None
            self.ts_lbl.config(text=self._last_ts if hasattr(self, "_last_ts") else "—", fg=TEXT_DIM)
            self.badge.config(text=self._last_badge, fg=self._last_badge_fg, bg=self._last_badge_bg)
            self.badge_frame.config(bg=self._last_badge_bg)

    def _lp_fire(self):
        self._lp_job = None
        self.ts_lbl.config(text=self._last_ts if hasattr(self, "_last_ts") else "—", fg=TEXT_DIM)
        self.badge.config(text="  COMPLETE  ", fg=ACCENT, bg=ACCENT_DIM)
        self.badge_frame.config(bg=ACCENT_DIM)
        self.after(2000, self._ping_single)

# ── Scrollable Frame ─────────────────────────────────────────────
class ScrollableFrame(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.Vertical.TScrollbar",
                        gripcount=0, background=ACCENT, darkcolor=BG, lightcolor=BG,
                        troughcolor="#060810", bordercolor=BG,
                        arrowcolor=ACCENT, arrowsize=13)
        style.map("Dark.Vertical.TScrollbar",
                  background=[("active", "#79b8ff"), ("!active", ACCENT)])

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.sb     = ttk.Scrollbar(self, orient="vertical",
                                    style="Dark.Vertical.TScrollbar",
                                    command=self.canvas.yview)
        self.inner  = tk.Frame(self.canvas, bg=BG)

        self.inner.bind("<Configure>", lambda _: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<MouseWheel>", self._mw)
        self.inner.bind("<MouseWheel>",  self._mw)

    def _start_pendulum(self):
        self._pendulum_dir = 1
        self._pendulum_pausing = False
        self._pendulum_job = None
        self._pendulum_tick()

    def _stop_pendulum(self):
        if getattr(self, "_pendulum_job", None):
            self.after_cancel(self._pendulum_job)
            self._pendulum_job = None

    def _pendulum_tick(self):
        if not self.canvas.winfo_exists():
            return
        top, bottom = self.canvas.yview()
        if self._pendulum_dir == 1 and bottom >= 1.0:
            if not self._pendulum_pausing:
                self._pendulum_pausing = True
                self._pendulum_job = self.after(1800, self._pendulum_reverse)
                return
        elif self._pendulum_dir == -1 and top <= 0.0:
            if not self._pendulum_pausing:
                self._pendulum_pausing = True
                self._pendulum_job = self.after(1800, self._pendulum_reverse)
                return
        step = 0.0006 * self._pendulum_dir
        self.canvas.yview_moveto(max(0.0, min(1.0, top + step)))
        self._pendulum_job = self.after(30, self._pendulum_tick)

    def _pendulum_reverse(self):
        self._pendulum_pausing = False
        self._pendulum_dir *= -1
        self._pendulum_job = self.after(30, self._pendulum_tick)

    def _mw(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def bind_mw(self, w):
        w.bind("<MouseWheel>", self._mw)
        for c in w.winfo_children():
            self.bind_mw(c)


# ── Main App ─────────────────────────────────────────────────────
class PingApp(tk.Tk):

    def _console_reset_data(self):
        self._console_write("WARNING: This will DELETE the entire assets/ directory!\n", RED)
        self._console_write("This includes ALL configs, logs, images, and saved data.\n", RED)
        self._console_write("The app will recreate necessary folders on restart.\n", RED)
        self._console_write("Type 'yes' to confirm, or 'no' to cancel:\n", RED)
        self._awaiting_reset_confirm = True

    def _console_inspect_host(self, args):
        if not args:
            self._console_write("Usage: inspect <VM name>\n", RED)
            return
        target_name = " ".join(args).strip()
        # Find the card by vm_name (case-insensitive)
        card = None
        for c in self.cards:
            if c.host.get("vm_name", "").lower() == target_name.lower():
                card = c
                break
        if not card:
            self._console_write(f"Host '{target_name}' not found.\n", RED)
            return

        host = card.host
        vm = host.get("vm_name", "?")
        ip = host.get("ip", "")
        port = host.get("port", "").strip()
        endpoint = host.get("endpoint", "").strip()
        is_website = host.get("is_website", False)

        self._console_write(f"\n--- INSPECTING {vm} ---\n", ACCENT)
        self._console_write(f"IP: {ip}\n", TEXT)
        self._console_write(f"Port: {port if port else '(not set)'}\n", TEXT)
        self._console_write(f"Endpoint: {endpoint if endpoint else '(none)'}\n", TEXT)
        self._console_write(f"Treat as website: {is_website}\n", TEXT)

        if not ip:
            self._console_write("No IP configured.\n", RED)
            return

        # Perform live check in background
        def do_check():
            import time
            if is_website:
                active_port = port if port else "443"
                self.after(0, lambda: self._console_write(f"\n→ Checking HTTP(S) on {ip}:{active_port}{endpoint or '/'} ...\n", YELLOW))
                result = check_http(ip, active_port, endpoint, timeout=5)
                status = result.get("status", "ERROR")
                resp_time = result.get("response_time", "—")
                status_code = result.get("status_code", "—")
                protocol = result.get("protocol", "—")
                self.after(0, lambda: self._console_write(
                    f"Result: {status} | {protocol} {status_code} | {resp_time}\n",
                    GREEN if status == "OK" else RED
                ))
                # Also show raw port status for reference
                if port:
                    port_result = check_port(ip, active_port)
                    port_status = port_result.get("status", "ERROR")
                    port_time = port_result.get("response_time", "—")
                    self.after(0, lambda: self._console_write(
                        f"TCP port {active_port}: {port_status} {port_time}\n",
                        YELLOW
                    ))
            else:
                self.after(0, lambda: self._console_write(f"\n→ Running ICMP ping to {ip} ...\n", YELLOW))
                ping_res = ping_host(ip, 4)  # quick ping
                self.after(0, lambda: self._console_write(
                    f"Ping: {ping_res['status']} | loss {ping_res['loss']}% | avg {ping_res['avg']}\n",
                    GREEN if ping_res['status']=="UP" else RED
                ))
                if port:
                    self.after(0, lambda: self._console_write(f"→ Checking TCP port {port} ...\n", YELLOW))
                    port_result = check_port(ip, port)
                    port_status = port_result.get("status", "ERROR")
                    port_time = port_result.get("response_time", "—")
                    self.after(0, lambda: self._console_write(
                        f"TCP port {port}: {port_status} {port_time}\n",
                        GREEN if port_status=="OPEN" else ORANGE if port_status=="CLOSED" else RED
                    ))
            self.after(0, lambda: self._console_write("---\n", TEXT_DIM))

        threading.Thread(target=do_check, daemon=True).start()

    def _save_geometry(self, event=None):
        if event and event.widget == self:
            x = self.winfo_x()
            y = self.winfo_y()
            w = self.winfo_width()
            h = self.winfo_height()
            # Basic validation – ignore if window is minimized or weird
            if w > 100 and h > 100:
                save_geometry(x, y, w, h)

    def _restart_app(self):
        self._running = False
        if self._auto_job:
            self.after_cancel(self._auto_job)
        self._suspend_all()
        
        # Schedule restart after a short delay
        self.after(100, self._do_restart)

    def _do_restart(self):
        import subprocess, sys
        subprocess.Popen([sys.executable] + sys.argv)
        self.quit()
        sys.exit(0)

    def _open_console_modal(self):
        # If console already exists, raise it
        if hasattr(self, '_console_window') and self._console_window.winfo_exists():
            self._console_window.lift()
            self._console_window.focus_force()
            return

        # Create the console window
        console = tk.Toplevel(self)
        console.title("")
        console.geometry("800x500")
        console.minsize(600, 300)
        console.configure(bg=BG)
        # Dark titlebar (Windows only, but safe)
        self._dark_titlebar_for(console)

        # Store reference
        self._console_window = console

        # Output area
        output_frame = tk.Frame(console, bg=BG)
        output_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.console_output = tk.Text(
            output_frame,
            bg=CARD_BG,                     # now uses theme background
            fg=TEXT,                        # main text color
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
            bd=0,
            highlightthickness=0,
            insertbackground=TEXT
        )
        self.console_output.pack(fill="both", expand=True)

        # Configure tags using theme colors
        self.console_output.tag_config("green", foreground=GREEN)
        self.console_output.tag_config("red", foreground=RED)
        self.console_output.tag_config("yellow", foreground=YELLOW)
        self.console_output.tag_config("silver", foreground=SILVER)
        self.console_output.tag_config("accent", foreground=ACCENT)
        self.console_output.tag_config("dim", foreground=TEXT_DIM)

        # Welcome message
        self._console_write("Console ready. Type 'help' for commands.\n", TEXT)

        # Input area
        input_frame = tk.Frame(console, bg=BG)
        input_frame.pack(fill="x", padx=8, pady=(0, 8))

        prompt = tk.Label(input_frame, text="> ", font=("Consolas", 10, "bold"),
                        fg=TEXT, bg=BG)
        prompt.pack(side="left")

        self.console_entry = tk.Entry(
            input_frame,
            font=("Consolas", 10),
            fg=TEXT,
            bg=CARD_BG,                     # theme background
            insertbackground=TEXT,
            relief="flat",
            highlightbackground=BORDER,
            highlightthickness=1
        )
        self.console_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.console_entry.bind("<Return>", self._console_execute)
        self.console_entry.bind("<Up>", self._console_history_up)
        self.console_entry.bind("<Down>", self._console_history_down)
        self.console_entry.focus_set()

        # Command history storage
        self._console_history = []
        self._history_index = -1

        # Cleanup on close
        console.protocol("WM_DELETE_WINDOW", self._close_console)

    def _close_console(self):
        if hasattr(self, '_console_window'):
            self._console_window.destroy()
            delattr(self, '_console_window')

    def _console_write(self, text, color=SILVER):
        # Map common color names to tag names
        color_map = {
            GREEN: "green", RED: "red", YELLOW: "yellow",
            SILVER: "silver", ACCENT: "accent", TEXT_DIM: "dim"
        }
        tag = color_map.get(color, "silver")
        self.console_output.configure(state="normal")
        self.console_output.insert("end", text, tag)
        self.console_output.see("end")
        self.console_output.configure(state="disabled")

    def _console_show_results(self):
        self._console_write("\n--- MAIN CARDS STATUS ---\n", ACCENT)
        for card in self.cards:
            vm = card.host.get("vm_name", "?")
            ip = card.host.get("ip", "not set")
            status = card._cur_sev if hasattr(card, "_cur_sev") else "unknown"
            loss = card.stat_w["loss"].cget("text") if "loss" in card.stat_w else "?"
            self._console_write(f"{vm} ({ip}) : {status} (loss {loss})\n", 
                                GREEN if status == "green" else YELLOW)
        self._console_write("\n--- BIOMETRIC STATUS ---\n", ACCENT)
        for row in self.misc.rows:
            name = row.entry.get("name", "?")
            ip = row.entry.get("ip", "not set")
            current_status = row.status_lbl.cget("text")
            self._console_write(f"{name} ({ip}) : {current_status}\n", 
                                GREEN if current_status == "OK" else YELLOW if current_status == "..." else RED)

    def _console_view_main(self):
        if not self.cards:
            self._console_write("No hosts configured.\n", YELLOW)
            return
        for card in self.cards:
            vm = card.host.get("vm_name", "?")
            ip = card.host.get("ip", "not set")
            self._console_write(f"{vm} ({ip})\n", SILVER)

    def _console_view_misc(self):
        """Show only biometric devices (name + IP only, no status)."""
        if not self.misc.rows:
            self._console_write("No biometric devices.\n", YELLOW)
            return
        for row in self.misc.rows:
            name = row.entry.get("name", "?")
            ip = row.entry.get("ip", "not set")
            self._console_write(f"{name} ({ip})\n", SILVER)

    def _console_view_all(self):
        """Display all devices (main + biometric) with names and IPs only."""
        self._console_write("\n--- MAIN CARDS ---\n", TEXT)
        self._console_view_main()
        self._console_write("\n--- BIOMETRIC DEVICES ---\n", TEXT)
        self._console_view_misc()

    def _console_countdown(self, n):
        if n > 0:
            self._console_write(f"{n}\n", YELLOW)
            self.after(1000, lambda: self._console_countdown(n - 1))
        else:
            self._console_write("Restarting...\n", GREEN)
            self.after(500, self._restart_app)

    def _console_entry_set_state(self, state):
        try:
            self.console_entry.config(state=state)
        except Exception:
            pass

    def _console_execute(self, event=None):
        cmd = self.console_entry.get().strip()
        if not cmd:
            return
        self._console_history.append(cmd)
        self._history_index = len(self._console_history)
        self._console_write(f"\n> {cmd}\n", SILVER)
        self.console_entry.delete(0, "end")

        parts = cmd.split()
        if not parts:
            self._console_write("\n", SILVER)
            return

        # Handle reset confirmation input
        if getattr(self, "_awaiting_reset_confirm", False):
            self._awaiting_reset_confirm = False
            if cmd.lower() == "yes":
                self._console_write("Wiping entire assets directory...\n", RED)
                
                # Get the assets directory path
                assets_dir = os.path.join(_base(), "assets")
                
                if os.path.exists(assets_dir):
                    try:
                        import shutil
                        shutil.rmtree(assets_dir)
                        self._console_write(f"Deleted: assets/ directory\n", ORANGE)
                        
                        # Recreate necessary subdirectories for clean restart
                        os.makedirs(_CONFIGS_DIR, exist_ok=True)
                        os.makedirs(_STORAGE_DIR, exist_ok=True)
                        self._console_write(f"Recreated: assets/configs/ and assets/data_storage/\n", GREEN)
                        
                    except Exception as e:
                        self._console_write(f"Failed to delete assets/: {e}\n", RED)
                else:
                    self._console_write("assets/ directory not found\n", YELLOW)
                
                self._console_write("Restarting in...\n", GREEN)
                self._console_entry_set_state("disabled")
                self._console_countdown(5)
            else:
                self._console_write("Reset cancelled.\n", TEXT_DIM)
            return

        raw_command = parts[0].lower()
        # Remove surrounding single or double quotes if present
        if (raw_command.startswith("'") and raw_command.endswith("'")) or \
        (raw_command.startswith('"') and raw_command.endswith('"')):
            raw_command = raw_command[1:-1]
        command = raw_command

        if command == "help":
            self._console_help()
        elif command == "clear":
            self.console_output.configure(state="normal")
            self.console_output.delete(1.0, "end")
            self.console_output.configure(state="disabled")
        elif command == "ping_all":
            self._console_ping_all()
        elif command == "view_all":
            self._console_view_all()
        elif command == "view_main":
            self._console_view_main()
        elif command == "view_misc":
            self._console_view_misc()
        elif command == "quit_console":
            self._close_console()          # closes only the console window
        elif command == "quit":
            self._console_quit()   
        elif command == "inspect":
            self._console_inspect_host(parts[1:])
        elif command == "reset_data":
            self._console_reset_data()
        else:
            self._console_write(f"Unknown command. Type 'help'.\n\n", RED)

        self._console_write("\n", SILVER)

    def _console_quit(self):
        self._close_console()
        self.quit()          # stops tkinter mainloop
        sys.exit(0)          # ensure process terminates

    def _console_ping_all(self):
        if self._running:
            self._console_write("Scan already in progress.\n", YELLOW)
            return
        self._console_write("Starting full network scan...\n", ACCENT)
        self._ping_all()
        def check_scan():
            if self._running:
                self.after(500, check_scan)
            else:
                self._console_write("\nScan completed. Results:\n", GREEN)
                self._console_show_results()
        self.after(500, check_scan)

    def _console_help(self):
        help_text = """
        Available commands:
        help          - show this help
        clear         - clear console output
        ping_all      - trigger a full network scan (all main cards + biometric)
        view_all      - show current status of all devices (main + biometric)
        view_main     - show only main host cards
        view_misc     - show only biometric devices
        reset_data    - wipe all config and log files (asks for confirmation)
        quit_console  - close the console window
        quit          - exit the entire application
        """
        self._console_write(help_text, SILVER)

    def _console_list_hosts(self):
        """List all main hosts."""
        if not self.cards:
            self._console_write("No hosts configured.\n", YELLOW)
            return
        for card in self.cards:
            vm = card.host.get("vm_name", "?")
            ip = card.host.get("ip", "not set")
            status = card._cur_sev if hasattr(card, "_cur_sev") else "unknown"
            self._console_write(f"{vm} : {ip} [{status}]\n", GREEN if status=="green" else YELLOW)

    def _console_list_biometric(self):
        """List biometric sidebar devices."""
        if not self.misc.rows:
            self._console_write("No biometric devices added.\n", YELLOW)
            return
        for row in self.misc.rows:
            name = row.entry.get("name", "?")
            ip = row.entry.get("ip", "not set")
            self._console_write(f"{name} : {ip}\n", SILVER)

    def _console_ping(self, args):
        """Ping a host by VM name or IP."""
        if not args:
            self._console_write("Usage: ping <vm_name or IP>\n", RED)
            return
        target = args[0]
        # Search in main cards
        for card in self.cards:
            if card.host.get("vm_name", "").lower() == target.lower():
                ip = card.host.get("ip")
                break
        else:
            # Not found by VM name, treat as direct IP
            ip = target
        if not ip or ip == "0.0.0.0":
            self._console_write(f"Cannot ping: no IP for '{target}'\n", RED)
            return
        self._console_write(f"Pinging {ip} ...\n", ACCENT)
        # Run ping in thread to avoid blocking
        def do_ping():
            res = ping_host(ip, 4)  # use 4 pings for quick response
            out = f"Result: {res['status']} - loss {res['loss']}%, avg {res['avg']}\n"
            self.after(0, lambda: self._console_write(out, GREEN if res['status']=='UP' else RED))
        threading.Thread(target=do_ping, daemon=True).start()

    def _console_theme(self, args):
        """Change theme from console."""
        if not args:
            self._console_write(f"Current theme: {_active_theme}\n", SILVER)
            self._console_write("Available: " + ", ".join(THEMES.keys()) + "\n", SILVER)
            return
        theme_name = args[0].upper()
        if theme_name in THEMES:
            self._apply_theme(theme_name)
            self._console_write(f"Theme changed to {theme_name}\n", GREEN)
        else:
            self._console_write(f"Theme '{theme_name}' not found.\n", RED)

    def _console_status(self):
        """Show quick status of all hosts."""
        up = sum(1 for c in self.cards if c.host.get("ip") and c._cur_sev == "green")
        down = sum(1 for c in self.cards if c.host.get("ip") and c._cur_sev in ("red_blink",))
        warn = sum(1 for c in self.cards if c.host.get("ip") and c._cur_sev in ("yellow_blink", "yellow", "orange_blink"))
        total = up + down + warn
        self._console_write(f"Hosts total: {total}  |  UP: {up}  |  WARN: {warn}  |  DOWN: {down}\n", SILVER)
        if self._interval > 0:
            self._console_write(f"Auto‑ping interval: {self._interval_label}\n", TEXT_DIM)
        else:
            self._console_write("Auto‑ping: OFF\n", TEXT_DIM)

    def _console_history_up(self, event):
        """Navigate up through command history."""
        if not self._console_history:
            return "break"
        if self._history_index > 0:
            self._history_index -= 1
            self.console_entry.delete(0, "end")
            self.console_entry.insert(0, self._console_history[self._history_index])
        return "break"

    def _console_history_down(self, event):
        """Navigate down through command history."""
        if not self._console_history:
            return "break"
        if self._history_index < len(self._console_history) - 1:
            self._history_index += 1
            self.console_entry.delete(0, "end")
            self.console_entry.insert(0, self._console_history[self._history_index])
        else:
            self._history_index = len(self._console_history)
            self.console_entry.delete(0, "end")
        return "break"

    def _on_console_key(self, event):
        if event.keysym in ('grave', 'asciitilde'):
            self._open_console_modal()

    def _apply_window_border(self, color="#2a2a2a"):
        try:
            DWMWA_BORDER_COLOR = 34
            col = color.lstrip("#")
            r, g, b = (int(col[i:i+2], 16) for i in (0, 2, 4))
            colorref = r | (g << 8) | (b << 16)
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_BORDER_COLOR,
                ctypes.byref(ctypes.c_int(colorref)),
                ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

    def _apply_theme(self, name, skip_repaint=False):
        global BG, CARD_BG, BORDER, _active_theme
        t = THEMES.get(name, THEMES["OBSIDIAN"])
        BG      = t["BG"]
        CARD_BG = t["CARD_BG"]
        BORDER  = t["BORDER"]
        _active_theme = name

        save_theme(name)   # persist theme

        # If this is the very first call (during __init__), skip restart.
        # The UI hasn't been built yet – we just update the globals.
        if skip_repaint or not getattr(self, "_initialized", False):
            return

        # For all other theme changes (user interaction), restart the app
        self._restart_app()



    def _open_theme_modal(self):
        modal = tk.Toplevel(self)
        modal.title("")
        modal.configure(bg=BG)
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()
        w, h = 620, 400
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        modal.geometry(f"{w}x{h}+{x}+{y}")
        modal.configure(highlightbackground=BORDER, highlightthickness=0)
        self.after(100, lambda: self._dark_titlebar_for(modal))

        card = tk.Frame(modal, bg=CARD_BG, padx=20, pady=16)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="THEME", font=("Consolas", 11, "bold"),
                 fg=SILVER, bg=CARD_BG).pack(anchor="w")
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", pady=(8, 14))

        grid_frame = tk.Frame(card, bg=CARD_BG)
        grid_frame.pack(fill="both", expand=True)

        COLS = 3
        ROWS_PER_COL = 7
        theme_names = list(THEMES.keys())

        for idx, name in enumerate(theme_names):
            colors = THEMES[name]
            col = idx // ROWS_PER_COL
            row = idx % ROWS_PER_COL

            cell = tk.Frame(grid_frame, bg=CARD_BG)
            cell.grid(row=row, column=col, sticky="w", padx=(0, 20), pady=3)

            swatch_row = tk.Frame(cell, bg=CARD_BG)
            swatch_row.pack(side="left", padx=(0, 8))
            for col_hex in colors.values():
                tk.Frame(swatch_row, bg=col_hex, width=14, height=14,
                         highlightbackground=BORDER, highlightthickness=1
                         ).pack(side="left", padx=1)

            is_active = (name == _active_theme)
            btn = tk.Button(
                cell,
                text=f"{'▶ ' if is_active else '  '}{name}",
                font=("Consolas", 9, "bold"),
                fg=SILVER if is_active else TEXT_DIM,
                bg=CARD_BG,
                activeforeground=CARD_BG,
                activebackground=CARD_BG,
                relief="flat", bd=0,
                cursor="hand2",
                anchor="w",
                width=12,
                command=lambda n=name: (self._apply_theme(n), modal.destroy())
            )
            btn.pack(side="left")

            def btn_enter(e, b=btn): b.config(fg=SILVER)
            def btn_leave(e, b=btn, n=name): b.config(fg=SILVER if n == _active_theme else TEXT_DIM)
            btn.bind("<Enter>", btn_enter)
            btn.bind("<Leave>", btn_leave)

        modal.bind("<Escape>", lambda _: modal.destroy())

    def _create_default_icon(self, size=32):
        img = Image.new("RGBA", (size, size), (88, 166, 255, 255))  # ACCENT color
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", size // 2)
        except:
            font = ImageFont.load_default()
        draw.text((size//4, size//4), "NM", fill="white", font=font)
        return ImageTk.PhotoImage(img)

    def _open_branding_modal(self):
        modal = tk.Toplevel(self)
        modal.title(" ")
        modal.configure(bg=BG)
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()
        w, h = 520, 500   # enough height for bigger buttons
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        modal.geometry(f"{w}x{h}+{x}+{y}")
        modal.configure(highlightbackground=SILVER, highlightthickness=0)
        self.after(100, lambda: self._dark_titlebar_for(modal))

        card = tk.Frame(modal, bg=CARD_BG, padx=20, pady=16)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="EDIT HEADER PANEL", font=("Consolas", 11, "bold"),
                fg=SILVER, bg=CARD_BG).pack(anchor="w")
        tk.Frame(card, bg=SILVER, height=2).pack(fill="x", pady=(8, 14))

        # Helper – padded entry with spaces
        def padded_entry(parent, initial_text):
            frame = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
            frame.pack(fill="x", pady=(4, 8))
            entry = tk.Entry(frame, font=("Consolas", 10), bg=CARD_BG, fg=SILVER,
                            insertbackground=SILVER, relief="flat", bd=0,
                            highlightthickness=0)
            entry.pack(fill="x", ipady=6, padx=2, pady=2)
            entry.insert(0, " ")
            entry.insert(tk.END, " ")
            if initial_text:
                entry.insert(1, initial_text)
            else:
                entry.insert(1, " " * 8)
            entry.icursor(1)
            return entry

        # Part 1 Text
        tk.Label(card, text="TEXT 1", font=("Consolas", 9, "bold"),
                fg=SILVER, bg=CARD_BG).pack(anchor="w")
        p1_entry = padded_entry(card, _branding.get("title_part1", "NAME"))

        # Part 1 Color
        tk.Label(card, text="TEXT 1 COLOR", font=("Consolas", 9, "bold"),
                fg=SILVER, bg=CARD_BG).pack(anchor="w")
        p1c_row = tk.Frame(card, bg=CARD_BG)
        p1c_row.pack(fill="x", pady=(4, 8))
        p1c_frame = tk.Frame(p1c_row, bg=BORDER, padx=1, pady=1)
        p1c_frame.pack(side="left", fill="x", expand=True)
        p1c_entry = tk.Entry(p1c_frame, font=("Consolas", 10), bg=CARD_BG, fg=SILVER,
                            insertbackground=SILVER, relief="flat", bd=0,
                            highlightthickness=0)
        p1c_entry.pack(fill="x", ipady=6, padx=2, pady=2)
        p1c_entry.insert(0, " ")
        p1c_entry.insert(tk.END, " ")
        p1c_entry.insert(1, _branding.get("title_part1_color", SILVER))
        p1c_entry.icursor(1)

        cw1_wrap = tk.Frame(p1c_row, bg=SILVER, padx=1, pady=1)
        cw1_wrap.pack(side="left", padx=(8, 0), fill="y")
        def pick_p1c():
            self._open_color_picker(modal, p1c_entry.get().strip(),
                                    lambda color: (p1c_entry.delete(0, tk.END),
                                                p1c_entry.insert(0, f" {color} "),
                                                p1c_entry.icursor(1)))
        tk.Button(cw1_wrap, text="COLOR WHEEL", command=pick_p1c,
                font=("Consolas", 9), fg=SILVER, bg=BORDER,
                activeforeground=SILVER, activebackground="#1a1a1a",
                relief="flat", bd=0, padx=12, pady=6, cursor="hand2").pack(fill="both", expand=True)

        # Part 2 Text
        tk.Label(card, text="TEXT 2", font=("Consolas", 9, "bold"),
                fg=SILVER, bg=CARD_BG).pack(anchor="w")
        p2_entry = padded_entry(card, _branding.get("title_part2", "ME"))

        # Part 2 Color
        tk.Label(card, text="TEXT 2 COLOR", font=("Consolas", 9, "bold"),
                fg=SILVER, bg=CARD_BG).pack(anchor="w")
        p2c_row = tk.Frame(card, bg=CARD_BG)
        p2c_row.pack(fill="x", pady=(4, 8))
        p2c_frame = tk.Frame(p2c_row, bg=BORDER, padx=1, pady=1)
        p2c_frame.pack(side="left", fill="x", expand=True)
        p2c_entry = tk.Entry(p2c_frame, font=("Consolas", 10), bg=CARD_BG, fg=SILVER,
                            insertbackground=SILVER, relief="flat", bd=0,
                            highlightthickness=0)
        p2c_entry.pack(fill="x", ipady=6, padx=2, pady=2)
        p2c_entry.insert(0, " ")
        p2c_entry.insert(tk.END, " ")
        p2c_entry.insert(1, _branding.get("title_part2_color", SILVER))
        p2c_entry.icursor(1)

        cw2_wrap = tk.Frame(p2c_row, bg=SILVER, padx=1, pady=1)
        cw2_wrap.pack(side="left", padx=(8, 0), fill="y")
        def pick_p2c():
            self._open_color_picker(modal, p2c_entry.get().strip(),
                                    lambda color: (p2c_entry.delete(0, tk.END),
                                                p2c_entry.insert(0, f" {color} "),
                                                p2c_entry.icursor(1)))
        tk.Button(cw2_wrap, text="COLOR WHEEL", command=pick_p2c,
                font=("Consolas", 9), fg=SILVER, bg=BORDER,
                activeforeground=SILVER, activebackground="#1a1a1a",
                relief="flat", bd=0, padx=12, pady=6, cursor="hand2").pack(fill="both", expand=True)

        # Icon selection
        # Icon selection – hidden entry + Browse button
        # Icon selection – hidden entry + full‑width Browse button
        tk.Label(card, text="ICON (PNG file)", font=("Consolas", 9, "bold"),
                fg=SILVER, bg=CARD_BG).pack(anchor="w")

        icon_container = tk.Frame(card, bg=CARD_BG)
        icon_container.pack(fill="x", pady=(4, 16))

        # Hidden entry (keeps the variable)
        icon_path_var = tk.StringVar(value=_branding.get("icon_path", "assets/images/icon.png"))
        icon_entry = tk.Entry(icon_container, textvariable=icon_path_var)
        icon_entry.pack_forget()  # hidden

        def pick_icon():
            from tkinter import filedialog
            f = filedialog.askopenfilename(
                title="SELECT ICON (PNG)",
                filetypes=[("PNG images", "*.png"), ("All files", "*.*")]
            )
            if f:
                icon_path_var.set(f)

        # Make the button wide – fill the container horizontally
        btn = tk.Button(icon_container, text="SELECT ICON", command=pick_icon,
                        font=("Consolas", 10), fg=SILVER, bg=BORDER,
                        relief="flat", bd=0, padx=20, pady=8, cursor="hand2")
        btn.pack(fill="x", expand=True)   # ← stretches full width

        msg = tk.Label(card, text="", font=("Consolas", 8), fg=YELLOW, bg=CARD_BG)
        msg.pack(anchor="w", pady=(4, 0))

        def do_save():
            p1_text = p1_entry.get().strip()
            p1_color = p1c_entry.get().strip()
            p2_text = p2_entry.get().strip()
            p2_color = p2c_entry.get().strip()
            # Validate colors (hex or name)
            for col, name in [(p1_color, "Part 1"), (p2_color, "Part 2")]:
                if col and not (col.startswith('#') or col.isalpha()):
                    msg.config(text=f"Invalid color format for {name}", fg=RED)
                    return
            new_branding = {
                "title_part1": p1_text or "NAME",
                "title_part1_color": p1_color or SILVER,
                "title_part2": p2_text or "ME",
                "title_part2_color": p2_color or SILVER,
                "icon_path": "assets/images/icon.png"
            }
            chosen_icon = icon_path_var.get().strip()
            if chosen_icon and chosen_icon != "assets/images/icon.png":
                try:
                    import shutil
                    dest = _asset("assets/images/icon.png")
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copy2(chosen_icon, dest)
                    # Also copy to backup.png if desired? Not needed – backup is separate.
                except Exception as e:
                    msg.config(text=f"Failed to copy icon: {e}", fg=RED)
                    return
            try:
                current = load_settings()          # gets full dict including theme
                current.update(new_branding)       # update branding keys
                save_settings(current)  
            except Exception as e:
                msg.config(text=f"Save failed: {e}", fg=RED)
                return
            self._reload_branding()
            modal.destroy()
            self._set_status("SETTINGS SAVED. ", SILVER)

        # BUTTONS – ONE ROW, clearly visible
        btn_row = tk.Frame(card, bg=CARD_BG)
        btn_row.pack(fill="x", pady=(20, 0))
        tk.Button(btn_row, text="SAVE", command=do_save,
                font=("Consolas", 10, "bold"), fg=SILVER, bg=BORDER,
                relief="flat", padx=24, pady=10, cursor="hand2").pack(side="left", expand=True, fill="x")
        tk.Button(btn_row, text="CANCEL", command=modal.destroy,
                font=("Consolas", 10, "bold"), fg=SILVER, bg=BORDER,
                relief="flat", padx=24, pady=10, cursor="hand2").pack(side="left", padx=(12,0), expand=True, fill="x")
        
    def _reload_branding(self):
        global _branding
        _branding = load_branding()
        self._apply_branding()

    def _apply_branding(self):
        # Update title labels
        self.title_part1_label.config(
            text=_branding.get("title_part1", "NAME"),
            fg=_branding.get("title_part1_color", SILVER)
        )
        self.title_part2_label.config(
            text=_branding.get("title_part2", "ME"),
            fg=_branding.get("title_part2_color", SILVER)
        )
        
        # Update header icon with fallback
        icon_path = _branding.get("icon_path", "assets/images/icon.png")
        full_icon_path = _asset(icon_path)
        img = None
        try:
            img = Image.open(full_icon_path).resize((32, 32), Image.LANCZOS)
        except Exception:
            # Try backup icon
            try:
                img = Image.open(BACKUP_ICON_PATH).resize((32, 32), Image.LANCZOS)
            except Exception:
                pass
        
        if img:
            self._header_icon = ImageTk.PhotoImage(img)
            if hasattr(self, 'header_icon_label'):
                self.header_icon_label.config(image=self._header_icon)
        else:
            # Fallback to default coloured icon
            self._header_icon = self._create_default_icon(32)
            if hasattr(self, 'header_icon_label'):
                self.header_icon_label.config(image=self._header_icon)
        
        # Update window icon (taskbar)
        if not HIDE_TASKBAR_ICON:
            win_icon = None
            try:
                win_icon = Image.open(full_icon_path)
            except Exception:
                try:
                    win_icon = Image.open(BACKUP_ICON_PATH)
                except Exception:
                    pass
            if win_icon:
                self._win_icon = ImageTk.PhotoImage(win_icon)
                self.iconphoto(True, self._win_icon)
            else:
                self._win_icon = self._create_default_icon(32)
                self.iconphoto(True, self._win_icon)
            self.after(100, lambda: self.iconphoto(True, self._win_icon))

    def _open_color_picker(self, parent, initial_color, callback):
        from tkinter import IntVar

        picker = tk.Toplevel(parent)
        picker.title(" ")
        picker.configure(bg=BG)                     # Force dark background
        picker.resizable(False, False)
        picker.transient(parent)
        picker.grab_set()

        # --- Force the window to be dark before drawing anything ---
        picker.update_idletasks()                   # Apply background immediately

        w, h = 480, 360
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        picker.geometry(f"{w}x{h}+{x}+{y}")
        picker.configure(highlightbackground=SILVER, highlightthickness=0)
        self._dark_titlebar_for(picker)

        # Full‑window dark background frame (covers any leftover white)
        main_bg = tk.Frame(picker, bg=BG)
        main_bg.pack(fill="both", expand=True)

        # --- Helper functions for color conversion ---
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return (192, 192, 192)   # fallback silver

        def rgb_to_hex(r, g, b):
            return f"#{r:02x}{g:02x}{b:02x}"

        r, g, b = hex_to_rgb(initial_color)
        rgb_var = IntVar(value=r)
        g_var   = IntVar(value=g)
        b_var   = IntVar(value=b)

        def update_preview(*_):
            rv = rgb_var.get()
            gv = g_var.get()
            bv = b_var.get()
            hex_val = rgb_to_hex(rv, gv, bv)
            preview.config(bg=hex_val)
            hex_entry.delete(0, tk.END)
            hex_entry.insert(0, hex_val)

        def on_hex_change(*_):
            hex_val = hex_entry.get().strip()
            if hex_val.startswith('#') and len(hex_val) == 7:
                try:
                    rv, gv, bv = hex_to_rgb(hex_val)
                    rgb_var.set(rv)
                    g_var.set(gv)
                    b_var.set(bv)
                except:
                    pass

        # --- Main content card ---
        card = tk.Frame(main_bg, bg=CARD_BG, padx=20, pady=16)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="CUSTOM COLOR PICKER", font=("Consolas", 10, "bold"),
                fg=SILVER, bg=CARD_BG).pack(anchor="w")
        tk.Frame(card, bg=SILVER, height=2).pack(fill="x", pady=(8, 12))

        # Preview
        preview = tk.Frame(card, bg=rgb_to_hex(r, g, b), height=60, relief="flat", bd=0)
        preview.pack(fill="x", pady=(0, 12))

        # RGB sliders
        def make_slider(label, var, from_, to_):
            frame = tk.Frame(card, bg=CARD_BG)
            frame.pack(fill="x", pady=4)
            tk.Label(frame, text=label, font=("Consolas", 8, "bold"),
                    fg=SILVER, bg=CARD_BG, width=4).pack(side="left")
            slider = tk.Scale(frame, from_=from_, to=to_, orient="horizontal",
                            variable=var, bg=CARD_BG, fg=SILVER,
                            highlightthickness=0, troughcolor="#1e2830",
                            activebackground=ACCENT,
                            sliderlength=15, length=200)
            slider.pack(side="left", fill="x", expand=True, padx=8)
            entry = tk.Entry(frame, textvariable=var, width=4, font=("Consolas", 8),
                            bg=CARD_BG, fg=SILVER, insertbackground=SILVER,
                            relief="flat", highlightbackground=BORDER, highlightthickness=1)
            entry.pack(side="left")
            var.trace_add("write", update_preview)

        make_slider("R", rgb_var, 0, 255)
        make_slider("G", g_var,   0, 255)
        make_slider("B", b_var,   0, 255)

        # Hex entry
        hex_frame = tk.Frame(card, bg=CARD_BG)
        hex_frame.pack(fill="x", pady=(8, 0))
        tk.Label(hex_frame, text="HEX", font=("Consolas", 8, "bold"),
                fg=SILVER, bg=CARD_BG, width=4).pack(side="left")
        hex_entry = tk.Entry(hex_frame, font=("Consolas", 10), bg=BG, fg=SILVER,
                            insertbackground=SILVER, relief="flat",
                            highlightbackground=SILVER, highlightthickness=1)
        hex_entry.pack(side="left", fill="x", expand=True, padx=8)
        hex_entry.insert(0, rgb_to_hex(r, g, b))
        hex_entry.bind("<KeyRelease>", lambda e: on_hex_change())

        # Buttons
        btn_row = tk.Frame(card, bg=CARD_BG)
        btn_row.pack(fill="x", pady=(16, 0))

        def on_ok():
            callback(hex_entry.get().strip())
            picker.destroy()

        tk.Button(btn_row, text="SAVE", command=on_ok,
                font=("Consolas", 9, "bold"), fg=SILVER, bg=BORDER,
                relief="flat", padx=16, pady=5, cursor="hand2").pack(side="left")

        tk.Button(btn_row, text="CANCEL", command=picker.destroy,
                font=("Consolas", 9, "bold"), fg=TEXT_DIM, bg=CARD_BG,
                relief="flat", padx=12, pady=5, cursor="hand2").pack(side="left", padx=8)

        update_preview()


    def _remove_card(self, card):
        if card not in self.cards:
            return

        card._stop_blink()
        card._cancel_hold()
        card.grid_forget()
        self.cards.remove(card)

        for w in self.grid_f.winfo_children():
            w.grid_forget()

        for i, c in enumerate(self.cards):
            r, col = divmod(i, 3)
            pad_l = (0, 5) if col == 0 else (5, 5) if col == 1 else (5, 0)
            c.grid(row=r, column=col, sticky="nsew", padx=pad_l, pady=(0, 10))

        save_hosts([c.host for c in self.cards])
        self._set_status(f"Deleted {card.host.get('vm_name', '')}", RED)

    def _start_pendulum_idle_watch(self):
        self._pendulum_idle_job = None
        self._reset_pendulum_idle_timer()

    def _on_search(self, *_):
        query = self._search_var.get().strip().lower()
        if query:
            self._search_clear.pack(side="right")
            # Cancel idle while actively searching
            if self._idle_restore_job:
                self.after_cancel(self._idle_restore_job)
                self._idle_restore_job = None
            self._exit_idle()
        else:
            self._search_clear.pack_forget()
            # Resume idle when search is cleared
            self._idle_restore_job = self.after(5000, self._enter_idle)
        self._filter_cards(query)

    def _clear_search(self):
        self._search_var.set("")
        self._search_entry.focus_set()
        # Restore all biometric rows
        for row in self.misc.rows:
            row.pack(fill="x", pady=(0, 4))

    def _filter_cards(self, query):
        # ── Main cards ──
        if not query:
            # Restore original grid positions
            for card in self.cards:
                info = getattr(card, "_original_grid_info", None)
                if info:
                    card.grid(**info)
                else:
                    card.grid()

            # Restore all biometric rows
            for row in self.misc.rows:
                row.pack(fill="x", pady=(0, 4))
        else:
            matched = [c for c in self.cards if self._card_matches(c.host, query)]
            unmatched = [c for c in self.cards if not self._card_matches(c.host, query)]

            # Save original grid info before touching anything
            for card in self.cards:
                if not hasattr(card, "_original_grid_info"):
                    card._original_grid_info = card.grid_info()

            for card in unmatched:
                card.grid_remove()

            for i, card in enumerate(matched):
                r, col = divmod(i, 3)
                pad_l = (0, 5) if col == 0 else (5, 5) if col == 1 else (5, 0)
                card.grid(row=r, column=col, sticky="nsew", padx=pad_l, pady=(0, 10))

            # Biometric sidebar rows
            for row in self.misc.rows:
                haystack = " ".join([
                    row.entry.get("name", ""),
                    row.entry.get("ip", ""),
                ]).lower()
                if query in haystack:
                    row.pack(fill="x", pady=(0, 4))
                else:
                    row.pack_forget()

    def _card_matches(self, host, query):
        haystack = " ".join([
            host.get("vm_name", ""),
            host.get("ip", ""),
            host.get("physical_name", ""),
            host.get("system_name", ""),
        ]).lower()
        return query in haystack

    def _reset_pendulum_idle_timer(self, event=None):
        if getattr(self, "_pendulum_idle_job", None):
            self.after_cancel(self._pendulum_idle_job)
            self._pendulum_idle_job = None
        self.scroll._stop_pendulum()
        self._pendulum_idle_job = self.after(7000, self._try_start_pendulum)

    def _try_start_pendulum(self):
        if len(self.cards) > 9:
            self.scroll._start_pendulum()

    def _swap_cards(self, card_a, card_b):
        cards = self.app.cards if hasattr(self, "app") else self.cards
        idx_a = self.cards.index(card_a)
        idx_b = self.cards.index(card_b)

        # Swap hosts
        card_a.host, card_b.host = card_b.host, card_a.host

        # Refresh display of both cards
        for card in (card_a, card_b):
            card.vm_var.set(card.host.get("vm_name") or "VM Name")
            card.ip_var.set(card.host.get("ip") or "0.0.0.0")
            card._reset_stats()
            card._apply_dim()
            if card.host.get("ip"):
                card.after(100, card._ping_single)

        save_hosts([c.host for c in self.cards])
        self._set_status(f"Swapped {card_a.host.get('vm_name','')} ↔ {card_b.host.get('vm_name','')}", ACCENT)


    def _dark_titlebar_for(self, win):
        def _apply(w):
            try:
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                hwnd = ctypes.windll.user32.GetParent(w.winfo_id())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(ctypes.c_int(1)),
                    ctypes.sizeof(ctypes.c_int)
                )
            except Exception:
                pass
            try:
                DWMWA_BORDER_COLOR = 34
                col = "2a2a2a"
                r, g, b = (int(col[i:i+2], 16) for i in (0, 2, 4))
                colorref = r | (g << 8) | (b << 16)
                hwnd = ctypes.windll.user32.GetParent(w.winfo_id())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_BORDER_COLOR,
                    ctypes.byref(ctypes.c_int(colorref)),
                    ctypes.sizeof(ctypes.c_int)
                )
            except Exception:
                pass
            try:
                _ico_path = os.path.join(_base(), "_blank.ico")
                if os.path.exists(_ico_path):
                    w.wm_iconbitmap(_ico_path)
            except Exception:
                pass
            try:
                if hasattr(self, '_blank_ico_path') and os.path.exists(self._blank_ico_path):
                    w.wm_iconbitmap(self._blank_ico_path)
            except Exception:
                pass

        _apply(win)
        win.after(100, lambda: _apply(win))
        win.after(300, lambda: _apply(win))

    def _dark_titlebar(self):
        try:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)),
                ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

    def _defocus(self, event):
        widget = event.widget
        if isinstance(widget, (tk.Frame, tk.Canvas, tk.Label)):
            self.focus_set()

    def __init__(self):
        super().__init__()
        self.title(" ")

        self.withdraw()
        
        # --- Load saved geometry FIRST, before any other geometry call ---
        geom = load_geometry()
        if geom:
            x, y, w, h = geom
            # Clamp to screen (optional)
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            if x + w > screen_w: x = max(0, screen_w - w)
            if y + h > screen_h: y = max(0, screen_h - h)
            self.geometry(f"{w}x{h}+{x}+{y}")
        else:
            self.geometry("1200x760")   # default only if no saved geometry
        
        self.configure(bg=BG) 
        self.resizable(True, True)
        self.minsize(1200, 760)
        
        # --- Set window icon with fallback ---
                # --- Set window icon with fallback ---
        import io, struct, zlib
        def _make_transparent_ico():
            # 1x1 transparent PNG
            png = (
                b'\x89PNG\r\n\x1a\n'
                b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
                b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
            )
            # Minimal ICO wrapper around the PNG
            ico = struct.pack('<HHH', 0, 1, 1)          # ICONDIR
            ico += struct.pack('<BBBBHHII',              # ICONDIRENTRY
                1, 1, 0, 0, 1, 32, len(png), 22)
            ico += png
            return ico

        _ico_data = _make_transparent_ico()
        
        images_dir = _asset("assets/images")
        os.makedirs(images_dir, exist_ok=True)
        
        _ico_path = os.path.join(images_dir, "_blank.ico")
        with open(_ico_path, "wb") as _f:
            _f.write(_ico_data)
        self._blank_ico_path = _ico_path
        self.wm_iconbitmap(_ico_path)
        self.after(200, lambda: self.wm_iconbitmap(_ico_path))

        self._auto_job     = None
        self._running      = False
        self._interval_idx = 1
        self.cards             = []
        self._blink_fast_state = True
        self._blink_mild_state = True
        self._blink_fast_subs  = []
        self._blink_mild_subs  = []
        self._hosts_data       = load_hosts()
        saved_theme = load_theme()
        self._apply_theme(saved_theme, skip_repaint=True)  
        self._build_ui()
        self._initialized = True
        self._apply_branding()
        self._start_blink_clock()

        self.after(100, lambda: self._user_set_interval("1 MIN"))

        self._ui_hidden = False
        self._pinging_all = False

        self._idle_job = None
        self._graph_hide_job = None

        self._start_pendulum_idle_watch()
        self.bind("<Motion>", self._reset_pendulum_idle_timer, add="+")
        self.bind_all("<KeyPress>", self._reset_pendulum_idle_timer, add="+")
        self.bind_all("<ButtonPress>", self._reset_pendulum_idle_timer, add="+")

        self.bind_all('<Key>', self._on_console_key)
        self.after(100, self._dark_titlebar)
        self.after(150, self._apply_window_border)
        self.after(5000, self._ping_all)

        self._idle_restore_job = None
        self.bind("<Motion>", self._reset_idle_timer, add="+")
        self.bind_all("<KeyPress>", self._reset_idle_timer, add="+")
        self.bind_all("<ButtonPress>", self._reset_idle_timer, add="+")
        self.after(5000, self._enter_idle)

        self.bind("<Configure>", self._save_geometry)

        self.deiconify()

    @property
    def _interval(self):
        return INTERVAL_CYCLE[self._interval_idx][1]

    @property
    def _interval_label(self):
        return INTERVAL_CYCLE[self._interval_idx][0]

    def _toggle_add_host(self):
        self._open_add_host_modal()

    def _open_add_host_modal(self):
        modal = tk.Toplevel(self)
        modal.title("")
        modal.configure(bg=BG)
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        modal.update_idletasks()
        w, h = 560, 420
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        modal.geometry(f"{w}x{h}+{x}+{y}")
        modal.configure(highlightbackground=SILVER, highlightthickness=0)
        self.after(100, lambda: self._dark_titlebar_for(modal))

        card = tk.Frame(modal, bg=CARD_BG, padx=18, pady=16)
        card.pack(fill="both", expand=True)

        top = tk.Frame(card, bg=CARD_BG)
        top.pack(fill="x")

        tk.Label(
            top,
            text="ADD HOST",
            font=("Consolas", 10, "bold"),
            fg=SILVER,
            bg=CARD_BG
        ).pack(side="left")

        tk.Label(
            top,
            text="",
            font=("Consolas", 8),
            fg=SILVER,
            bg=CARD_BG
        ).pack(side="right")

        tk.Frame(card, bg=SILVER, height=2).pack(fill="x", pady=(10, 14))

        form = tk.Frame(card, bg=CARD_BG)
        form.pack(fill="x")

        fields = [
            ("VM Name", 14),
            ("IP", 14),
            ("Physical Name", 16),
            ("System", 16),
            ("Port", 8),
            ("Endpoint", 14),
        ]

        _vars = []

        for r, (label_text, width) in enumerate(fields):
            row = tk.Frame(form, bg=CARD_BG)
            row.pack(fill="x", pady=(0, 10))

            tk.Label(
                row,
                text=label_text,
                font=("Consolas", 8, "bold"),
                fg=SILVER,
                bg=CARD_BG,
                width=14,
                anchor="w"
            ).pack(side="left")

            box = tk.Frame(
                row,
                bg=CARD_BG,
                padx=6,
                pady=1
            )

            e = self._ph_entry(box, label_text, width)

            e.configure(
                bg=BG,
                fg=SILVER,
                insertbackground=SILVER,
                relief="flat",
                bd=0,
                highlightthickness=0
            )

            e.pack(fill="both", expand=True)

            box.pack(
                side="left",
                fill="x",
                expand=True,
                padx=(0, 6),
                ipady=5
            )
            _vars.append((e, label_text))

        # --- CHECKBOX FOR WEBSITE ---
        chk_frame = tk.Frame(form, bg=CARD_BG)
        chk_frame.pack(fill="x", pady=(5, 10))
        is_website_var = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(
            chk_frame,
            text="Treat as website (HTTP/HTTPS)",
            variable=is_website_var,
            font=("Consolas", 8),
            fg=TEXT_DIM,
            bg=CARD_BG,
            selectcolor=CARD_BG,
            activebackground=CARD_BG,
            anchor="w"
        )
        chk.pack(side="left")
        # -------------------------

        msg_lbl = tk.Label(card, text="", font=("Consolas", 7), fg=SILVER, bg=CARD_BG)
        msg_lbl.pack(anchor="w", pady=(4, 0))

        btn_row = tk.Frame(card, bg=CARD_BG)
        btn_row.pack(fill="x", pady=(16, 0))

        def do_add():
            vals = [e.get().strip() for e, ph in _vars]
            defaults = [ph for _, ph in _vars]

            vm, ip, phys, sys_n, port, endpoint = [
                "" if v == defaults[i] else v
                for i, v in enumerate(vals)
            ]

            if not vm:
                vm = f"VM {len(self.cards) + 1:02d}"

            if ip:
                cleaned_ip = clean_host(ip)
                if not is_valid_host(cleaned_ip):
                    msg_lbl.config(text="Invalid IP format", fg=RED)
                    return
                ip = cleaned_ip

            host = {
                "vm_name": vm,
                "ip": ip,
                "physical_name": phys,
                "system_name": sys_n,
                "port": port,
                "endpoint": endpoint,
                "is_website": is_website_var.get()   # <-- use local variable
            }

            self._add_card(host, len(self.cards))
            save_hosts([c.host for c in self.cards])

            self.after(
                100,
                lambda: self.scroll.canvas.yview_moveto(1.0)
            )

            self._set_status(
                f"Added {host['vm_name']} ({ip or 'no IP'})",
                GREEN
            )

            modal.destroy()

        # ── ADD BUTTON ──
        add_btn_wrap = tk.Frame(btn_row, bg=SILVER, padx=1, pady=1)
        add_btn_wrap.pack(side="left")

        add_btn = tk.Button(
            add_btn_wrap,
            text="+ ADD",
            font=("Consolas", 9, "bold"),
            fg=SILVER,
            bg=BORDER,
            activeforeground=SILVER,
            activebackground="#1a1a1a",
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=do_add
        )
        add_btn.pack()

        # ── CANCEL BUTTON ──
        cancel_btn_wrap = tk.Frame(btn_row, bg=SILVER, padx=1, pady=1)
        cancel_btn_wrap.pack(side="left", padx=(8, 0))

        cancel_btn = tk.Button(
            cancel_btn_wrap,
            text="CANCEL",
            font=("Consolas", 9, "bold"),
            fg=SILVER,
            bg=BORDER,
            activeforeground=SILVER,
            activebackground="#1a1a1a",
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=modal.destroy
        )
        cancel_btn.pack()

        # HOVER ANIMATION
        def on_enter(btn, wrapper):
            wrapper.config(bg="#E0E0E0")
            btn.config(bg="#1a1a1a")

        def on_leave(btn, wrapper):
            wrapper.config(bg=SILVER)
            btn.config(bg=BORDER)

        add_btn.bind("<Enter>", lambda e: on_enter(add_btn, add_btn_wrap))
        add_btn.bind("<Leave>", lambda e: on_leave(add_btn, add_btn_wrap))

        cancel_btn.bind("<Enter>", lambda e: on_enter(cancel_btn, cancel_btn_wrap))
        cancel_btn.bind("<Leave>", lambda e: on_leave(cancel_btn, cancel_btn_wrap))

        modal.bind("<Escape>", lambda _: modal.destroy())


    def _reset_idle_timer(self, event=None):
        if self._idle_restore_job:
            self.after_cancel(self._idle_restore_job)
            self._idle_restore_job = None
        self._exit_idle()
        # Don't restart idle timer if user is actively interacting with specific widgets
        focused = self.focus_get()
        # Check if focus is on any input widget (search, config entries, etc.)
        if focused and isinstance(focused, (tk.Entry, tk.Text)):
            # User is typing, don't start idle timer
            return
        # Also check if mouse is over any interactive area
        if hasattr(self, '_is_mouse_over_interactive'):
            self._idle_restore_job = self.after(5000, self._enter_idle)
        else:
            self._idle_restore_job = self.after(5000, self._enter_idle)

    def _enter_idle(self):
        # Don't enter idle if user is interacting with any input widget
        focused = self.focus_get()
        if focused and isinstance(focused, (tk.Entry, tk.Text)):
            # Reset timer instead
            self._reset_idle_timer()
            return
        
        if getattr(self, "_ui_hidden", False):
            return
        self._ui_hidden = True
        self._fade_out_header(steps=10, delay=30)

    def _check_mouse_over_interactive(self):
        """Check if mouse is over search bar or other interactive elements"""
        try:
            x, y = self.winfo_pointerxy()
            widget = self.winfo_containing(x, y)
            
            # Check if mouse is over search bar or its children
            if widget and (widget == self._search_entry or 
                        widget in self._search_entry.winfo_children() or
                        (hasattr(self, '_search_entry') and 
                            str(widget).startswith(str(self._search_entry)))):
                return True
            
            # Check if mouse is over any button in header
            if widget and hasattr(widget, 'winfo_parent'):
                parent = widget.winfo_parent()
                if parent and ('Button' in str(widget) or 'button' in str(widget).lower()):
                    return True
                    
            return False
        except Exception:
            return False


    def _fade_out_header(self, steps=10, delay=30, current=10):
        if not getattr(self, "_ui_hidden", False):
            return
        # Gradually dim status label as a visual cue before collapse
        ratio = current / steps
        r = int(0x63 * ratio)
        g = int(0x70 * ratio)
        b = int(0x80 * ratio)
        faded = f"#{r:02x}{g:02x}{b:02x}"
        try:
            self.status_lbl.config(fg=faded)
        except Exception:
            pass
        if current <= 0:
            self.hdr.pack_forget()
            if self._settings_visible:
                self._settings_frame.pack_forget()
            return
        self.after(delay, lambda: self._fade_out_header(steps, delay, current - 1))

    def _exit_idle(self):
        if not getattr(self, "_ui_hidden", False):
            return
        self._ui_hidden = False
        self.hdr.pack(fill="x", after=self._hdr_anchor)
        if self._settings_visible:
            self._settings_frame.pack(fill="x", after=self._settings_anchor,
                                      padx=18, pady=(0, 4))
        self._fade_in_header(steps=10, delay=30)

    def _fade_in_header(self, steps=10, delay=30, current=0):
        if getattr(self, "_ui_hidden", False):
            return
        ratio = current / steps
        # Interpolate from #000000 toward TEXT_DIM (#637080)
        r = int(0x63 * ratio)
        g = int(0x70 * ratio)
        b = int(0x80 * ratio)
        faded = f"#{r:02x}{g:02x}{b:02x}"
        try:
            self.status_lbl.config(fg=faded)
        except Exception:
            pass
        if current >= steps:
            self.status_lbl.config(fg=TEXT_DIM)
            return
        self.after(delay, lambda: self._fade_in_header(steps, delay, current + 1))
            

    def _start_blink_clock(self):
        def fast_tick():
            self._blink_fast_state = not self._blink_fast_state
            state = self._blink_fast_state
            for cb in list(self._blink_fast_subs):
                try:
                    cb(state)
                except Exception:
                    pass
            self.after(BLINK_FAST, fast_tick)
        def mild_tick():
            self._blink_mild_state = not self._blink_mild_state
            state = self._blink_mild_state
            for cb in list(self._blink_mild_subs):
                try:
                    cb(state)
                except Exception:
                    pass
            self.after(BLINK_MILD, mild_tick)
        self.after(BLINK_FAST, fast_tick)
        self.after(BLINK_MILD, mild_tick)


    def _build_ui(self):
        # ── Header ──
        self._hdr_anchor = tk.Frame(self, bg=BG, height=0)
        self._hdr_anchor.pack(fill="x")
        self.hdr = tk.Frame(self, bg=BG, pady=14, padx=18)
        self.hdr.pack(fill="x")
        hdr = self.hdr

        left_hdr = tk.Frame(hdr, bg=BG)

        icon_container = tk.Frame(left_hdr, bg=BG, cursor="hand2")
        icon_container.pack(side="left", padx=(0, 8))
        icon_container.bind("<Button-1>", lambda e: self._open_branding_modal())

        # Always create the label (empty initially)
        self.header_icon_label = tk.Label(icon_container, bg=BG, width=32, height=32)
        self.header_icon_label.pack()
        self.header_icon_label.bind("<Button-1>", lambda e: self._open_branding_modal())

        # Try to load the main icon
        try:
            img = Image.open(_asset(_branding.get("icon_path", "assets/images/icon.png"))).resize((32, 32), Image.LANCZOS)
            self._header_icon = ImageTk.PhotoImage(img)
            self.header_icon_label.config(image=self._header_icon)
        except Exception:
            # Try backup icon
            try:
                backup_img = Image.open(BACKUP_ICON_PATH).resize((32, 32), Image.LANCZOS)
                self._header_icon = ImageTk.PhotoImage(backup_img)
                self.header_icon_label.config(image=self._header_icon)
            except Exception:
                # No icon, label remains empty (but exists)
                pass

        title_frame = tk.Frame(left_hdr, bg=BG)
        title_frame.pack(anchor="w")

        # Part 1 (clickable)
        self.title_part1_label = tk.Label(
            title_frame,
            text=_branding.get("title_part1", "NAME"),
            font=("Consolas", 15, "bold"),
            fg=_branding.get("title_part1_color", SILVER),
            bg=BG,
            cursor="hand2"
        )
        self.title_part1_label.pack(side="left")
        self.title_part1_label.bind("<Button-1>", lambda e: self._open_branding_modal())

        # Part 2 (clickable)
        self.title_part2_label = tk.Label(
            title_frame,
            text=_branding.get("title_part2", "ME"),
            font=("Consolas", 15, "bold"),
            fg=_branding.get("title_part2_color", SILVER),
            bg=BG,
            cursor="hand2"
        )
        self.title_part2_label.pack(side="left")
        self.title_part2_label.bind("<Button-1>", lambda e: self._open_branding_modal())

        left_hdr.pack(side="left")

  
        self.status_lbl = tk.Label(left_hdr, text="INITIALIZING...",
                                   font=("Consolas", 8), fg=TEXT_DIM, bg=BG)
        self.status_lbl.pack(anchor="w")

        right_hdr = tk.Frame(hdr, bg=BG)
        right_hdr.pack(side="right")

        # ── Settings panel (collapsible) ──
        self._settings_visible = False
        self._settings_frame   = tk.Frame(self, bg=BG, padx=18, pady=6)

        sf = self._settings_frame
        tk.Label(sf, text="RE-PING INTERVAL", font=("Consolas", 7),
                 fg=TEXT_DIM, bg=BG).pack(side="left", padx=(0, 6))
        iv_btns = tk.Frame(sf, bg=BG)
        iv_btns.pack(side="left", padx=(0, 16))
        self._iv_btns = {}
        for label, secs in INTERVAL_CYCLE:
            wrap = tk.Frame(iv_btns, bg=BORDER, padx=1, pady=1)
            wrap.pack(side="left", padx=2)
            b = tk.Button(wrap, text=label,
                          font=("Consolas", 8, "bold"),
                          fg=TEXT_DIM, bg=CARD_BG,
                          activeforeground=TEXT, activebackground=ACCENT_DIM,
                          relief="flat", bd=0, cursor="hand2",
                          height=1, width=6,
                          command=lambda l=label: self._user_set_interval(l))
            b.pack(padx=2, pady=2)
            b._wrap = wrap
            self._iv_btns[label] = b


                # Search bar (in right_hdr, before the ⚙ button)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)

        

        search_inner = tk.Frame(right_hdr, bg=CARD_BG,
                                highlightbackground=BORDER, highlightthickness=0)
        search_inner.pack(side="left", padx=(0, 8))

        tk.Label(search_inner, text="⌕", font=("Consolas", 11),
                fg=TEXT_DIM, bg=CARD_BG).pack(side="left", padx=(8, 4))

        self._search_entry = tk.Entry(
            search_inner,
            textvariable=self._search_var,
            font=("Consolas", 9),
            fg=TEXT, bg=CARD_BG,
            insertbackground=TEXT,
            relief="flat", bd=0,
            highlightthickness=0,
            width=25
        )
        self._search_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self._search_entry.bind("<FocusOut>", self._reset_idle_timer)

        self._search_clear = tk.Button(
            search_inner, text="✕",
            font=("Consolas", 8),
            fg=TEXT_DIM, bg=CARD_BG,
            activeforeground=RED, activebackground=CARD_BG,
            relief="flat", bd=0, padx=8, cursor="hand2",
            command=self._clear_search
        )
        self._search_clear.pack(side="right")
        self._search_clear.pack_forget()

        # Header buttons
        tk.Button(right_hdr, text="⏱",
                font=("Consolas", 11), 
                fg="#E0E0E0",               # Brighter silver for the normal state
                bg=BG,
                activeforeground="#F5F5F5", # Even brighter silver/white when clicked
                activebackground=BG,
                relief="flat", bd=0, padx=6, pady=5, cursor="hand2",
                command=self._toggle_settings).pack(side="left", padx=(0, 4))
        

        logs_wrap = tk.Frame(right_hdr, bg=TEXT, padx=2, pady=4)
        logs_wrap.pack(side="left", padx=(0, 10))
        logs_btn = tk.Button(logs_wrap, text="LOGS",
                        font=("Consolas", 9, "bold"), fg=TEXT, bg=CARD_BG,
                        activeforeground=TEXT, activebackground=ACCENT_DIM,
                        relief="flat", bd=0, padx=18, pady=6, cursor="hand2",
                        command=self._open_log_modal)
        logs_btn.pack()

        # ADD HOST button with hover effect
        # ADD HOST — real cyan border via wrapper frame
        add_host_wrap = tk.Frame(right_hdr, bg=TEXT, padx=2, pady=4)
        add_host_wrap.pack(side="left", padx=(0, 10))
        add_host_btn = tk.Button(add_host_wrap, text="+ HOST",
                  font=("Consolas", 9), fg=TEXT, bg=CARD_BG,
                  activeforeground=TEXT, activebackground=ACCENT_DIM,
                  relief="flat", bd=0, padx=18, pady=6, cursor="hand2",
                  command=self._toggle_add_host)
        add_host_btn.pack()

        def add_host_enter(e):
            add_host_btn.config(bg=ACCENT_DIM)
        def add_host_leave(e):
            add_host_btn.config(bg=CARD_BG)
        add_host_btn.bind("<Enter>", add_host_enter)
        add_host_btn.bind("<Leave>", add_host_leave)

        
        console_wrap = tk.Frame(right_hdr, bg=TEXT, padx=2, pady=4)
        console_wrap.pack(side="left", padx=(0, 10))
        console_btn = tk.Button(
            console_wrap,
            text="</>",
            font=("Consolas", 9), fg=TEXT, bg=CARD_BG,
            activeforeground=TEXT, activebackground=ACCENT_DIM,
            relief="flat", bd=0, padx=20, pady=6, cursor="hand2",
            command=self._open_console_modal
        )
        console_btn.pack()

        # + BIO — real cyan border via wrapper frame
        bio_wrap = tk.Frame(right_hdr, bg=TEXT, padx=2, pady=4)
        bio_wrap.pack(side="left", padx=(0, 10))
        bio_btn = tk.Button(bio_wrap, text="+ BIO",
                  font=("Consolas", 9), fg=TEXT, bg=CARD_BG,
                  activeforeground=TEXT, activebackground=ACCENT_DIM,
                  relief="flat", bd=0, padx=18, pady=6, cursor="hand2",
                  command=lambda: self.misc._open_add_misc_modal())
        bio_btn.pack()

        def bio_enter(e):
            bio_btn.config(bg=ACCENT_DIM)
        def bio_leave(e):
            bio_btn.config(bg=CARD_BG)
        bio_btn.bind("<Enter>", bio_enter)
        bio_btn.bind("<Leave>", bio_leave)

        # PING ALL — real cyan border via wrapper frame
        # PING ALL — real cyan border via wrapper frame
        self.ping_all_wrap = tk.Frame(right_hdr, bg=TEXT, padx=2, pady=4)
        self.ping_all_wrap.pack(side="left", padx=(0, 10))
        self.ping_all_btn = tk.Button(
            self.ping_all_wrap,
            text="SCAN ALL",
            font=("Consolas", 9), fg=TEXT, bg=CARD_BG,
            activeforeground=TEXT, activebackground=ACCENT_DIM,
            relief="flat", bd=0, padx=20, pady=6, cursor="hand2",
            command=self._ping_all,
        )
        self.ping_all_btn.pack()

        def ping_all_enter(e):
            if self._ui_hidden or self.ping_all_btn.cget("state") == "disabled":
                return
            self.ping_all_btn.config(bg=ACCENT_DIM)
        def ping_all_leave(e):
            if self._ui_hidden or self.ping_all_btn.cget("state") == "disabled":
                return
            self.ping_all_btn.config(bg=CARD_BG)
        self.ping_all_btn.bind("<Enter>", ping_all_enter)
        self.ping_all_btn.bind("<Leave>", ping_all_leave)
        
        tk.Button(right_hdr, text="◑",
                  font=("Consolas", 13), fg=SILVER, bg=BG,
                  activeforeground=TEXT, activebackground=BG,
                  relief="flat", bd=0, padx=6, pady=5, cursor="hand2",
                  command=self._open_theme_modal).pack(side="left", padx=(0, 0))
        
        tk.Button(right_hdr, text="⛶",
                  font=("Consolas", 13), fg=SILVER, bg=BG,
                  activeforeground=TEXT, activebackground=BG,
                  relief="flat", bd=0, padx=6, pady=5, cursor="hand2",
                  command=self._toggle_fullscreen).pack(side="left", padx=(6, 0))

        self.log_lbl = tk.Label(right_hdr, text="", font=("Consolas", 7),
                                fg=TEXT_DIM, bg=BG)
        self.log_lbl.pack(side="left", padx=(8, 0))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    

        self._settings_anchor = tk.Frame(self, bg=BG, height=0)
        self._settings_anchor.pack(fill="x")

        # ── Add host panel (collapsible, above body) ──
        self._add_visible = False
        self.add_panel = tk.Frame(self, bg=CARD_BG,
                                  highlightbackground=BORDER, highlightthickness=0,
                                  padx=18, pady=10)

        tk.Label(self.add_panel, text="+ HOST",
                 font=("Consolas", 8, "bold"), fg=TEXT_DIM, bg=CARD_BG
                 ).pack(anchor="w", pady=(0, 5))

        add_row = tk.Frame(self.add_panel, bg=CARD_BG)
        add_row.pack(fill="x")
        fields = [("VM Name", 14), ("IP", 14), ("Physical Name", 16), ("System Name", 16), ("Port", 8), ("Endpoint", 14)]
        self._add_vars = []
        for ph, w in fields:
            e = self._ph_entry(add_row, ph, w)
            e.pack(side="left", ipady=4, padx=(0, 6))
            self._add_vars.append((e, ph))
        tk.Button(add_row, text="+ ADD",
                  font=("Consolas", 9, "bold"), fg=BG, bg=ACCENT,
                  activeforeground=BG, activebackground="#79b8ff",
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
                  command=self._add_host).pack(side="left")

        # ── Body: left card grid + divider + right misc sidebar ──
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # Left side
        left_body = tk.Frame(body, bg=BG)
        left_body.pack(side="left", fill="both", expand=True)

        self.scroll = ScrollableFrame(left_body, bg=BG)
        self.scroll.pack(fill="both", expand=True)
        self.grid_f = self.scroll.inner
        self.grid_f.configure(padx=14, pady=14)
        for col in range(3):
            self.grid_f.columnconfigure(col, weight=1, uniform="col")

        for i, host in enumerate(self._hosts_data):
            self._add_card(host, i)

        # Vertical divider
        tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y")

        # Right side: misc sidebar (fixed width)
        sidebar_outer = tk.Frame(body, bg=BG, width=220)
        sidebar_outer.pack(side="left", fill="y")
        sidebar_outer.pack_propagate(False)

        self.misc = MiscSidebar(sidebar_outer)
        self.misc.pack(fill="both", expand=True, padx=12, pady=12)


        self.bind_all("<Button-1>", lambda e: self.focus_set() if e.widget not in (
            self.grid_f, *[w for card in self.cards for w in card.winfo_children()]
        ) else None)

        self.bind_all("<Button-1>", self._defocus)

        self._refresh_interval_buttons()

    def _ph_entry(self, parent, placeholder, width):
        e = tk.Entry(
            parent,
            font=("Consolas", 9),
            fg=TEXT,
            bg=BG,
            insertbackground=TEXT,
            relief="flat",
            highlightbackground=BORDER,
            highlightthickness=0,
            width=width
        )
        
        # Add 1 space at start, 1 space at end
        e.insert(0, " ")
        e.insert(tk.END, " ")
        
        # Move cursor to position 1 (after the first space)
        e.icursor(1)
        
        return e

    def _add_card(self, host, idx):
        card = HostCard(self.grid_f, host, self)
        r, c = divmod(idx, 3)
        pad_l = (0, 5) if c == 0 else (5, 5) if c == 1 else (5, 0)
        card.grid(row=r, column=c, sticky="nsew", padx=pad_l, pady=(0, 10))
        card._original_grid_info = card.grid_info()  # ← stamp it
        self.cards.append(card)
        self.scroll.bind_mw(card)

    def _set_status(self, msg, color=TEXT_DIM):
        self.status_lbl.config(text=msg, fg=color)

    def _refresh_interval_buttons(self):
        cur_label = self._interval_label
        for lbl, btn in self._iv_btns.items():
            if lbl == cur_label:
                btn.config(fg=BG, bg=TEXT)
                if hasattr(btn, "_wrap"):
                    btn._wrap.config(bg=TEXT)
            else:
                btn.config(fg=TEXT_DIM, bg=CARD_BG)
                if hasattr(btn, "_wrap"):
                    btn._wrap.config(bg=BORDER)

    def _user_set_interval(self, label):
        idx = next(i for i, (l, _) in enumerate(INTERVAL_CYCLE) if l == label)
        self._interval_idx = idx
        self._refresh_interval_buttons()
        if self._auto_job:
            self.after_cancel(self._auto_job)
            self._auto_job = None
        if self._interval == 0:
            self._set_status("AUTO UPDATE OFF", TEXT_DIM)
            return
        self._set_status(f"AUTO UPDATE EVERY: {label}", SILVER)
        self._auto_job = self.after(self._interval * 1000, self._schedule_auto)


    def _suspend_all(self):
        for card in self.cards:
            card._stop_blink()
            if getattr(card, "_webview_showing", False):
                card._hide_webview()
            if getattr(card, "_graph_showing", False):
                card._hide_latency_graph()
            if hasattr(card, "_webview_show_job") and card._webview_show_job:
                card.after_cancel(card._webview_show_job)
                card._webview_show_job = None
            if hasattr(card, "_webview_hide_job") and card._webview_hide_job:
                card.after_cancel(card._webview_hide_job)
                card._webview_hide_job = None
            if hasattr(card, "_graph_hide_job") and card._graph_hide_job:
                card.after_cancel(card._graph_hide_job)
                card._graph_hide_job = None
            if hasattr(card, "_lp_job") and card._lp_job:
                card.after_cancel(card._lp_job)
                card._lp_job = None
        for row in self.misc.rows:
            row._stop_blink()
            if hasattr(row, "_ping_job") and row._ping_job:
                row.after_cancel(row._ping_job)
                row._ping_job = None

                
    def _ping_all(self):
        if self._running:
            return
        
        active_cards = [c for c in self.cards if c.host.get("ip")]
        active_misc = [r for r in self.misc.rows if r.entry.get("ip")]
        
        if not active_cards and not active_misc:
            return
        
        self._suspend_all()
        self._running = True
        self.ping_all_btn.config(state="disabled", bg=CARD_BG, fg=TEXT_DIM, cursor="")
        self.ping_all_wrap.config(bg=BORDER)
        self._set_status("[ANALYZING ALL NETWORKS]", SILVER)
        
        # Combine all devices to ping
        all_devices = []
        for card in active_cards:
            all_devices.append(('card', card))
        for row in active_misc:
            all_devices.append(('misc', row))
        
        # Set cards to probing state
        for card in active_cards:
            card.set_pinging()
        
        # Track completion
        self._ping_completed_count = 0
        self._ping_total_count = len(all_devices)
        
        def start_next_ping(index):
            if index >= len(all_devices):
                return
            
            device_type, device = all_devices[index]
            
            if device_type == 'card':
                # Start card ping in thread
                threading.Thread(target=self._ping_single_card, args=(device,), daemon=True).start()
            else:  # misc
                # For misc, ping it with tracking
                self._ping_single_misc(device)
            
            # Schedule next device with delay
            self.after(300, lambda: start_next_ping(index + 1))
        
        # Start the staggered pings
        start_next_ping(0)
        
        # Set a timeout to ensure _ping_done gets called even if some pings fail
        self.after((len(all_devices) * 300) + 15000, self._check_pings_complete)

    def _ping_single_card(self, card):
        """Ping a single card and track completion"""
        def on_complete():
            self._ping_completed_count += 1
            if self._ping_completed_count >= self._ping_total_count:
                self.after(500, self._ping_done)
        
        # Store original update_result
        original_update = card.update_result
        
        def wrapped_update(stats):
            original_update(stats)
            on_complete()
        
        card.update_result = wrapped_update
        card._ping_single()
        
        # Restore original after a delay (in case it never gets called)
        self.after(30000, lambda: setattr(card, 'update_result', original_update))

    def _ping_single_misc(self, row):
        """Ping a single misc device and track completion"""
        def on_complete():
            self._ping_completed_count += 1
            if self._ping_completed_count >= self._ping_total_count:
                self.after(500, self._ping_done)
        
        # Store the original callback
        original_apply = row._apply_result
        
        def wrapped_apply(res):
            original_apply(res)
            on_complete()
        
        row._apply_result = wrapped_apply
        row.ping_now()
        # Restore original after a delay
        self.after(10000, lambda: setattr(row, '_apply_result', original_apply))

    def _check_pings_complete(self):
        """Fallback to ensure _ping_done gets called"""
        if self._running:
            self._ping_done()


    def _ping_done(self):
        self._running = False
        self.ping_all_btn.config(state="normal", bg=CARD_BG, fg=TEXT, cursor="hand2")
        self.ping_all_wrap.config(bg=TEXT)
        now = datetime.datetime.now().strftime("%H:%M:%S")

        up   = sum(1 for c in self.cards if c.host.get("ip") and c._cur_sev == "green")
        down = sum(1 for c in self.cards if c.host.get("ip") and c._cur_sev in ("red_blink",))
        warn = sum(1 for c in self.cards if c.host.get("ip") and c._cur_sev in ("yellow_blink", "yellow", "orange_blink"))

        misc_up   = sum(1 for r in self.misc.rows if r.entry.get("ip") and r.status_lbl.cget("text") in ("OK",))
        misc_down = sum(1 for r in self.misc.rows if r.entry.get("ip") and r.status_lbl.cget("text") in ("DOWN",))

        total_up   = up + misc_up
        total_down = down + misc_down

        parts = [f"Last run: {now}"]
        if total_up:   parts.append(f"✓ {total_up} UP")
        if warn:       parts.append(f"⚠ {warn} WARN")
        if total_down: parts.append(f"✗ {total_down} DOWN")

        summary_color = RED if down else YELLOW if warn else GREEN
        self._set_status("   ".join(parts), SILVER)

        # Flash the status label once to draw attention
        def _flash(count=0):
            if count >= 4:
                self._set_status("   ".join(parts), SILVER)
                return
            color = BG if count % 2 == 0 else SILVER
            self.status_lbl.config(fg=color)
            self.after(200, lambda: _flash(count + 1))
        _flash()

        if os.path.exists(LOG_PATH):
            self.log_lbl.config(text="", fg=ORANGE)

        # Schedule next auto ping reminder in status
        if self._interval > 0:
            self.after(3000, lambda: self._set_status(
                f"NEXT UPDATE IN: {self._interval_label} — {now}", TEXT_DIM
            ))

    def _open_log_modal(self):
        import csv as _csv
        modal = tk.Toplevel(self)
        modal.title("")
        modal.configure(bg=BG)
        modal.resizable(True, True)
        modal.transient(self)
        modal.grab_set()
        w, h = 980, 560
        x = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        modal.geometry(f"1200x560+{x}+{y}")
        modal.configure(highlightbackground=BORDER, highlightthickness=0)
        self.after(100, lambda: self._dark_titlebar_for(modal))
        modal.update_idletasks()
        self._dark_titlebar_for(modal)
        modal.after(100, lambda: self._dark_titlebar_for(modal))
        modal.after(500, lambda: self._dark_titlebar_for(modal))

        # ── Load CSV ──
        all_rows = []
        if os.path.exists(LOG_PATH):
            try:
                with open(LOG_PATH, newline="", encoding="utf-8", errors="replace") as f:
                    all_rows = list(_csv.DictReader(f))
            except Exception:
                pass
        all_rows = list(reversed(all_rows))

        def sev_of(row):
            diag = row.get("diagnostic", "")
            what = row.get("what", "")
            if "red_blink"    in diag or "loss=100" in what: return "red"
            if "orange_blink" in diag:                        return "orange"
            if "yellow"       in diag:                        return "yellow"
            return "dim"

        card = tk.Frame(modal, bg=CARD_BG)
        card.pack(fill="both", expand=True)

        # ── Top bar ──
        topbar = tk.Frame(card, bg="#060a10", padx=16, pady=10)
        topbar.pack(fill="x")

        tk.Label(topbar, text="EVENT", font=("Consolas", 11, "bold"),
                fg=SILVER, bg="#060a10").pack(side="left")
        tk.Label(topbar, text="LOG",  font=("Consolas", 11, "bold"),
                fg=SILVER, bg="#060a10").pack(side="left")
        self._log_count_lbl = tk.Label(topbar, text=f"  {len(all_rows)} entries",
                font=("Consolas", 8), fg=TEXT_DIM, bg="#060a10")
        self._log_count_lbl.pack(side="left", padx=(8,0))
        close_btn = tk.Button(topbar, text="✕", font=("Consolas", 10),
                fg=TEXT_DIM, bg="#060a10",
                activeforeground=RED, activebackground="#060a10",
                relief="flat", bd=0, cursor="hand2",
                command=modal.destroy)
        close_btn.pack(side="right")
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=RED))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=TEXT_DIM))
        tk.Frame(card, bg=SILVER, height=2).pack(fill="x")

        # ── Search bar ──
        search_bar = tk.Frame(card, bg="#080d14", padx=16, pady=7)
        search_bar.pack(fill="x")
        tk.Label(search_bar, text="⌕", font=("Consolas", 11),
                fg=TEXT_DIM, bg="#080d14").pack(side="left", padx=(0,6))
        search_var = tk.StringVar()
        search_e = tk.Entry(search_bar, textvariable=search_var,
                            font=("Consolas", 9), fg=TEXT, bg="#080d14",
                            insertbackground=TEXT, relief="flat",
                            bd=0, highlightthickness=0)
        search_e.pack(side="left", fill="x", expand=True, ipady=2)
        clr_btn = tk.Button(search_bar, text="✕", font=("Consolas", 8),
                            fg=TEXT_DIM, bg="#080d14",
                            activeforeground=RED, activebackground="#080d14",
                            relief="flat", bd=0, cursor="hand2",
                            command=lambda: search_var.set(""))
        clr_btn.pack(side="right")
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x")

        # ── Fixed-width column spec (pixels, adjusted for longer timestamp) ──
        TABS = ("340", "540", "720", "880", "960", "1020", "1090")

        # ── Column header ──
        hdr_bar = tk.Frame(card, bg="#0a0e16", padx=16, pady=6)
        hdr_bar.pack(fill="x")
        hdr_txt = tk.Text(hdr_bar, bg="#0a0e16", fg=TEXT_DIM,
                        font=("Consolas", 8, "bold"),
                        relief="flat", bd=0, highlightthickness=0,
                        wrap="none", cursor="arrow", height=1,
                        tabs=TABS, tabstyle="wordprocessor")
        hdr_txt.insert("end", "TIMESTAMP\tEVENT\tSERVER\tIP\tAVG\tRECV\tSTATUS")
        hdr_txt.configure(state="disabled")
        hdr_txt.pack(fill="x")
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x")

        # ── Text widget ──
        txt = tk.Text(card, bg=CARD_BG, fg=TEXT, font=("Consolas", 8),
                    relief="flat", bd=0, highlightthickness=0,
                    wrap="none", cursor="arrow", padx=16, pady=4,
                    tabs=TABS, tabstyle="wordprocessor")
        txt.pack(fill="both", expand=True)

        txt.bind("<MouseWheel>",
                lambda e: txt.yview_scroll(int(-1*(e.delta/120)), "units"))
        modal.bind("<MouseWheel>",
                lambda e: txt.yview_scroll(int(-1*(e.delta/120)), "units"))

        txt.tag_config("red",      foreground=RED)
        txt.tag_config("orange",   foreground=ORANGE)
        txt.tag_config("yellow",   foreground=YELLOW)
        txt.tag_config("dim",      foreground=TEXT_DIM)
        txt.tag_config("txt",      foreground=TEXT)
        txt.tag_config("accent",   foreground=ACCENT)
        txt.tag_config("stripe",   background="#0b0f18")
        txt.tag_config("ts",       foreground="#FFFFFF", font=("Consolas", 8, "bold"))
        txt.tag_config("sev_crit", foreground=RED,    font=("Consolas", 8, "bold"))
        txt.tag_config("sev_warn", foreground=ORANGE, font=("Consolas", 8, "bold"))
        txt.tag_config("sev_mild", foreground=YELLOW, font=("Consolas", 8, "bold"))
        txt.tag_config("sev_ok",   foreground=GREEN,  font=("Consolas", 8, "bold"))

        def sev_tag(sev):
            return {"red": "sev_crit", "orange": "sev_warn",
                    "yellow": "sev_mild", "dim": "sev_ok"}.get(sev, "dim")

        def render(rows):
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            if not rows:
                txt.insert("end", "  No matching entries.", "dim")
            else:
                for i, row in enumerate(rows):
                    sev   = sev_of(row)
                    base  = ("stripe",) if i % 2 == 0 else ()
                    fc    = sev_tag(sev)

                    # Format timestamp with day of week
                    # Inside render(rows), replace the timestamp formatting block with:

                    ts_raw = row.get("timestamp", "—")
                    try:
                        dt = datetime.datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S")
                        hour = dt.hour % 12
                        if hour == 0:
                            hour = 12
                        minute = dt.minute
                        ampm = "AM" if dt.hour < 12 else "PM"
                        day_name = dt.strftime("%A").upper()
                        # Format: 2026-06-04, 2:30 PM, THURSDAY
                        ts_display = f"{dt.strftime('%Y-%m-%d')}, {hour}:{minute:02d} {ampm}, {day_name}"
                    except Exception:
                        ts_display = ts_raw[:19]   # fallback to original

                    what = row.get("what",      "—")[:18]
                    srv  = row.get("server",    "—")[:16]
                    ip   = row.get("ip",        "—")

                    raw   = row.get("diagnostic", "")
                    avg_m = re.search(r"avg=([^\s,]+)", raw)
                    rec_m = re.search(r"recv=(\d+)/",  raw)
                    sev_m = re.search(r"sev=([^\s,]+)", raw)
                    avg_v = avg_m.group(1) if avg_m else "—"
                    rec_v = rec_m.group(1) if rec_m else "—"
                    sev_map = {"red_blink":"● CRITICAL","orange_blink":"▲ WARNING",
                            "yellow_blink":"◆ MILD","yellow":"◆ MILD","green":"✓ OK"}
                    sev_v = sev_map.get(sev_m.group(1) if sev_m else "", "—")
                    if not any(c.isdigit() for c in avg_v):
                        avg_v = "—"
                    ip_tag = "accent" if sev == "dim" else fc

                    txt.insert("end", ts_display + "\t", base + ("ts",))
                    txt.insert("end", what + "\t", base + (fc,))
                    txt.insert("end", srv  + "\t", base + ("txt",))
                    txt.insert("end", ip   + "\t", base + (ip_tag,))
                    txt.insert("end", avg_v + "\t", base + ("txt",))
                    txt.insert("end", rec_v + "\t", base + ("txt",))
                    txt.insert("end", sev_v + "\n", base + (fc,))

            txt.configure(state="disabled")
            self._log_count_lbl.config(text=f"  {len(rows)} of {len(all_rows)} entries")

        render(all_rows)

        # ── Search filter ──
        def on_search(*_):
            q = search_var.get().strip().lower()
            clr_btn.pack(side="right") if q else clr_btn.pack_forget()
            if not q:
                render(all_rows)
                return
            
            filtered = []
            for row in all_rows:
                # Build the same formatted timestamp as used in render
                ts_raw = row.get("timestamp", "—")
                try:
                    dt = datetime.datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S")
                    hour = dt.hour % 12
                    if hour == 0:
                        hour = 12
                    minute = dt.minute
                    ampm = "AM" if dt.hour < 12 else "PM"
                    day_name = dt.strftime("%A").upper()
                    ts_display = f"{dt.strftime('%Y-%m-%d')}, {hour}:{minute:02d} {ampm}, {day_name}"
                except Exception:
                    ts_display = ts_raw[:19]
                
                # Combine all searchable text (original values + formatted timestamp)
                searchable = " ".join([
                    ts_display,
                    row.get("what", ""),
                    row.get("server", ""),
                    row.get("ip", ""),
                    row.get("diagnostic", "")
                ]).lower()
                
                if q in searchable:
                    filtered.append(row)
            
            render(filtered)

        search_var.trace_add("write", on_search)
        clr_btn.pack_forget()

        # ── Footer ──
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x")
        foot = tk.Frame(card, bg="#060a10", padx=16, pady=8)
        foot.pack(fill="x")
        red_c    = sum(1 for r in all_rows if sev_of(r) == "red")
        orange_c = sum(1 for r in all_rows if sev_of(r) == "orange")
        up_c     = sum(1 for r in all_rows if sev_of(r) == "dim")
        for label, val, col in [
            ("CRIT ", red_c,    RED),
            ("  WARN ", orange_c, ORANGE),
            ("  OK ",   up_c,    GREEN),
        ]:
            tk.Label(foot, text=label, font=("Consolas", 7),
                    fg=TEXT_DIM, bg="#060a10").pack(side="left")
            tk.Label(foot, text=str(val), font=("Consolas", 7, "bold"),
                    fg=col, bg="#060a10").pack(side="left")

        search_e.focus_set()

    def _toggle_settings(self):
        if self._settings_visible:
            self._settings_frame.pack_forget()
            self._settings_visible = False
        else:
            self._settings_frame.pack(fill="x", after=self._settings_anchor,
                                      padx=18, pady=(0, 4))
            self._settings_visible = True

    def _toggle_fullscreen(self):
        fs = self.attributes("-fullscreen")
        self.attributes("-fullscreen", not fs)
        if not fs:
            self.bind("<Escape>", lambda _: self._exit_fullscreen())
        else:
            self.after(100, self._dark_titlebar)

    def _exit_fullscreen(self):
        self.attributes("-fullscreen", False)
        self.after(100, self._dark_titlebar)

    def _schedule_auto(self):
        if self._running:
            self._auto_job = self.after(self._interval * 1000, self._schedule_auto)
            return
        self._set_status(f"Scheduled ping starting… ({self._interval_label})", ACCENT)
        self._suspend_all()
        self._ping_all()
        if self._interval > 0:
            self._auto_job = self.after(self._interval * 1000, self._schedule_auto)

    def _add_host(self):
        vals     = [e.get().strip() for e, ph in self._add_vars]
        defaults = [ph for _, ph in self._add_vars]
        vm, ip, phys, sys_n, port, endpoint = [
            "" if v == defaults[i] else v for i, v in enumerate(vals)
        ]
        if ip:
            cleaned_ip = clean_host(ip)
            if not is_valid_host(cleaned_ip):
                self._set_status("Invalid IP format", RED)
                return
            ip = cleaned_ip
        host = {
            "vm_name":       vm or f"VM {len(self.cards)+1:02d}",
            "ip":            ip,
            "physical_name": phys,
            "system_name":   sys_n,
            "port":          port,
            "endpoint":      endpoint,
        }
        self._add_card(host, len(self.cards))
        save_hosts([c.host for c in self.cards])
        self.after(100, lambda: self.scroll.canvas.yview_moveto(1.0))
        for e, ph in self._add_vars:
            e.config(fg=TEXT_DIM)
            e.delete(0, "end")
            e.insert(0, ph)
        self._set_status(f"Added {host['vm_name']} ({ip or 'no IP'})", GREEN)


if __name__ == "__main__":
    app = PingApp()
    app.mainloop()
