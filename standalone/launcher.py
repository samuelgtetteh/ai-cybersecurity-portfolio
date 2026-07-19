#!/usr/bin/env python3
"""
RegMap standalone launcher.

Runs the RegMap API from a self-contained folder on Windows, Linux, or macOS.
On first run it creates a private virtual environment and installs the pinned
dependencies; on later runs it just starts the API. If the application code is
missing it will try to fetch it from the GitHub repository.

You normally do not call this directly — double-click run.cmd (Windows) or run
./run.sh (Linux/macOS), which locate Python and hand off to this script.
"""
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def _resolve_layout():
    """Support two layouts so this runs from the packaged folder OR the repo source folder.
    Packaged:  <folder>/app/backend + <folder>/requirements.txt
    Dev/repo:  <repo>/standalone/launcher.py  ->  <repo>/backend + <repo>/backend/requirements.txt
    """
    app = os.path.join(HERE, "app")
    if os.path.isfile(os.path.join(app, "backend", "app.py")):
        return app, os.path.join(app, "backend"), os.path.join(HERE, "requirements.txt")
    repo = os.path.dirname(HERE)
    if os.path.isfile(os.path.join(repo, "backend", "app.py")):
        return repo, os.path.join(repo, "backend"), os.path.join(repo, "backend", "requirements.txt")
    return app, os.path.join(app, "backend"), os.path.join(HERE, "requirements.txt")


APP, BACKEND, REQ = _resolve_layout()           # bundle root, backend dir, requirements file
VENV = os.path.join(HERE, ".venv")
MARKER = os.path.join(VENV, ".deps_ok")
PORT = int(os.environ.get("REGMAP_PORT", "8000"))
REPO = "https://github.com/samuelgtetteh/ai-cybersecurity-portfolio.git"
IS_WIN = platform.system() == "Windows"


def log(msg):
    print("[regmap] " + msg, flush=True)


def die(msg, code=1):
    log("ERROR: " + msg)
    if IS_WIN:
        input("Press Enter to close...")
    sys.exit(code)


def venv_python():
    return os.path.join(VENV, "Scripts", "python.exe") if IS_WIN else os.path.join(VENV, "bin", "python")


def ensure_app():
    """Make sure the application code is present; if not, try to clone it from GitHub."""
    if os.path.isfile(os.path.join(BACKEND, "app.py")):
        return
    log("application code not found in this folder.")
    from shutil import which, copytree
    if not which("git"):
        die("app/ is missing and 'git' is not installed to download it. Re-download the full "
            "standalone folder (it must include the app/ directory with models).")
    log("downloading application code from GitHub ...")
    tmp = os.path.join(HERE, "_repo")
    subprocess.check_call(["git", "clone", "--depth", "1", REPO, tmp])
    os.makedirs(APP, exist_ok=True)
    copytree(os.path.join(tmp, "backend"), BACKEND, dirs_exist_ok=True)
    copytree(os.path.join(tmp, "control-advisor", "scanner"),
             os.path.join(APP, "control-advisor", "scanner"), dirs_exist_ok=True)
    log("NOTE: trained models/data are NOT in the git repo. If the app fails to start, this "
        "folder was distributed without its app/models and app/data — get the full bundle.")


def _nmap_dir():
    """Find nmap's directory even when PATH is stale (common on Windows right after install)."""
    p = shutil.which("nmap")
    if p:
        return os.path.dirname(p)
    for d in (r"C:\Program Files (x86)\Nmap", r"C:\Program Files\Nmap",
              "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin"):
        exe = "nmap.exe" if IS_WIN else "nmap"
        if os.path.isfile(os.path.join(d, exe)):
            return d
    return None


def ensure_nmap():
    """Best-effort install of the nmap binary (NOT a pip package). nmap gives real host discovery
    and service/version detection -> CVE/KEV mapping. It is optional: if this can't install it,
    we log how and keep going with the built-in TCP scanner. Never blocks startup."""
    if _nmap_dir():
        return
    sysname = platform.system()
    log("nmap not found -> built-in TCP scanner will be used (fewer hosts, no version/CVE detection).")
    try:
        if sysname == "Linux":
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                if shutil.which("apt-get"):
                    log("installing nmap via apt ...")
                    subprocess.check_call(["apt-get", "update"])
                    subprocess.check_call(["apt-get", "install", "-y", "nmap"])
                elif shutil.which("dnf"):
                    subprocess.check_call(["dnf", "install", "-y", "nmap"])
                elif shutil.which("apk"):
                    subprocess.check_call(["apk", "add", "--no-cache", "nmap"])
                else:
                    log("no supported package manager found; install nmap manually for full scanning.")
            else:
                log("re-run as root (or: sudo apt install nmap) to enable the richer nmap engine.")
        elif sysname == "Darwin":
            if shutil.which("brew"):
                log("installing nmap via Homebrew ...")
                subprocess.check_call(["brew", "install", "nmap"])
            else:
                log("install Homebrew, then 'brew install nmap', for full scanning.")
        elif sysname == "Windows":
            if shutil.which("winget"):
                log("installing nmap via winget (may prompt to install the Npcap driver) ...")
                subprocess.call(["winget", "install", "--id", "Insecure.Nmap", "-e",
                                 "--accept-package-agreements", "--accept-source-agreements"])
                log("if nmap was just installed, RESTART this launcher so it is picked up.")
            else:
                log("install nmap from https://nmap.org/download.html (keep Npcap checked) for "
                    "host discovery + CVE detection.")
    except Exception as e:
        log("automatic nmap install did not complete (%s). Continuing with the built-in scanner." % e)
    if _nmap_dir():
        log("nmap is now available -> richer scan engine enabled.")


def ensure_venv():
    """Create the venv and install dependencies once."""
    py = venv_python()
    if not os.path.isfile(py):
        log("creating virtual environment (one-time) ...")
        import venv as _venv
        _venv.EnvBuilder(with_pip=True).create(VENV)
    if os.path.isfile(MARKER) and _imports_ok(py):
        return
    log("installing dependencies — first run only, this can take several minutes ...")
    subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip"])
    # CPU-only torch first so we don't pull ~2 GB of CUDA on a headless/CPU box.
    subprocess.check_call([py, "-m", "pip", "install", "torch==2.12.1",
                           "--index-url", "https://download.pytorch.org/whl/cpu"])
    subprocess.check_call([py, "-m", "pip", "install", "-r", REQ])
    open(MARKER, "w").close()


def _imports_ok(py):
    check = ("import fastapi, uvicorn, torch, sentence_transformers, sklearn, "
             "pandas, docx, openpyxl, boto3, psutil")
    return subprocess.call([py, "-c", check],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def _port_free(p):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", p))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _is_regmap(p):
    """True only if RegMap itself is answering on this port (checks a RegMap endpoint, so we
    don't mistake some other program on the port for our API)."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/decision/stats" % p, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _find_free_port():
    """Ask the OS for any free port (bind to 0) — guaranteed to return something usable."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def _choose_port(pref):
    """Return (port, already_running). Never fail because a port is blocked:
      1) use the preferred port if it's free,
      2) if RegMap is already running there, reuse it,
      3) otherwise scan upward for the next available port,
      4) as a last resort let the OS assign any free port.
    No port is hard-coded except the preferred default (override with REGMAP_PORT)."""
    if _port_free(pref):
        return pref, False
    if _is_regmap(pref):
        return pref, True
    for cand in range(pref + 1, pref + 200):
        if _port_free(cand):
            return cand, False
    return _find_free_port(), False


def lan_ips():
    ips = []
    try:
        _, _, addrs = socket.gethostbyname_ex(socket.gethostname())
        ips = [a for a in addrs if not a.startswith("127.")]
    except Exception:
        pass
    return ips or ["<this-machine-ip>"]


def _open_browser_when_ready(port):
    for _ in range(90):
        if _is_regmap(port):
            import webbrowser
            webbrowser.open("http://localhost:%d" % port)
            return
        time.sleep(1)


def main():
    log("OS detected: %s %s (%s)" % (platform.system(), platform.release(), platform.machine()))
    port, already = _choose_port(PORT)
    if already:
        log("RegMap is already running at http://localhost:%d — opening it." % port)
        if IS_WIN or platform.system() == "Darwin":
            import webbrowser
            webbrowser.open("http://localhost:%d" % port)
        return
    if port != PORT:
        log("port %d is in use by another program; using free port %d instead." % (PORT, port))

    ensure_app()
    ensure_nmap()
    ensure_venv()

    env = dict(os.environ)
    env.setdefault("VERDICT_DB", os.path.join(HERE, "verdicts.db"))
    nd = _nmap_dir()
    if nd:
        env["PATH"] = nd + os.pathsep + env.get("PATH", "")
        log("nmap detected (%s) -> richer scan engine (versions + CVE/KEV) enabled." % nd)
    else:
        log("nmap not detected -> built-in TCP scanner only (no version/CVE detection).")
    urls = "   ".join("http://%s:%d" % (ip, port) for ip in lan_ips())
    log("starting RegMap API ...")
    log("when you see 'Application startup complete', open:  http://localhost:%d" % port)
    log("on your LAN, others can reach it at:  %s" % urls)

    if IS_WIN or platform.system() == "Darwin":
        threading.Thread(target=_open_browser_when_ready, args=(port,), daemon=True).start()

    cmd = [venv_python(), "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", str(port)]
    try:
        subprocess.call(cmd, cwd=BACKEND, env=env)
    except KeyboardInterrupt:
        log("stopped.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        die("a setup step failed (exit %s). See the output above." % e.returncode)
