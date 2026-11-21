"""Entry point of the packaged app (DatabaseExplorer.exe).

Runs without a console window: starts the server on this computer only (127.0.0.1), opens the
app in its own window (Microsoft Edge app mode, or the default browser as a fallback), and exits
by itself once that window is closed (see lifecycle.py). Starting it again while it's running
just opens another window.

Log file: %LOCALAPPDATA%\\DatabaseExplorer\\logs\\app.log
"""
import json
import logging
import logging.handlers
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

PORTS = range(52300, 52311)  # an uncommon range, to avoid clashing with other local servers
TITLE = "Database Explorer"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "DatabaseExplorer"
log = logging.getLogger("database-explorer")


def setup_logging():
    (DATA_DIR / "logs").mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        DATA_DIR / "logs" / "app.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("waitress").setLevel(logging.WARNING)


def message_box(text, error=True):
    """A normal Windows dialog (there's no console to print to)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10 if error else 0x40)
            return
        except Exception:
            pass
    sys.stderr and sys.stderr.write(text + "\n")


def already_running(port, app_name):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as r:
            return json.load(r).get("app") == app_name
    except Exception:
        return False


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def find_edge():
    if sys.platform != "win32":
        return None
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe") as k:
                    path = winreg.QueryValue(k, None)
                    if path and Path(path).is_file():
                        return path
            except OSError:
                pass
    except ImportError:
        pass
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base and (Path(base) / "Microsoft/Edge/Application/msedge.exe").is_file():
            return str(Path(base) / "Microsoft/Edge/Application/msedge.exe")
    return shutil.which("msedge")


def open_window(url):
    """Open the app in its own window without address bar or tabs; else a normal browser tab."""
    if os.environ.get("DBX_NO_BROWSER"):  # set for automated tests
        return
    edge = find_edge()
    if edge:
        try:
            # A separate Edge profile keeps the app window independent of the user's own browsing,
            # and remembers its size and the app's saved settings
            subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={DATA_DIR / 'window'}",
                              "--no-first-run", "--no-default-browser-check", "--window-size=1300,860"],
                             close_fds=True)
            return
        except OSError:
            log.exception("Couldn't start Edge; using the default browser")
    webbrowser.open(url)


def shutdown():
    logging.shutdown()
    os._exit(0)


def main():
    from waitress import create_server
    from app import app, APP_NAME, VERSION
    from lifecycle import Watchdog

    # Only ports something is listening on can hold a running copy. (Asking a free port is slow on
    # Windows, which retries refused connections for about a second.)
    free = [p for p in PORTS if port_free(p)]
    for port in (p for p in PORTS if p not in free):
        if already_running(port, APP_NAME):
            log.info("Already running on port %s: opening another window", port)
            open_window(f"http://127.0.0.1:{port}/")
            return
    port = free[0] if free else None
    if port is None:
        raise RuntimeError(f"All ports from {PORTS.start} to {PORTS.stop - 1} are in use by other programs.")

    server = create_server(app, host="127.0.0.1", port=port, threads=8)
    app.config["WATCHDOG"] = Watchdog(on_idle=shutdown).start()
    url = f"http://127.0.0.1:{port}/"
    log.info("Database Explorer %s running at %s", VERSION, url)
    open_window(url)
    server.run()


if __name__ == "__main__":
    setup_logging()
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.exception("Startup failed")
        message_box(f"Database Explorer could not start:\n\n{e}\n\n"
                    f"Details are in {DATA_DIR / 'logs' / 'app.log'}")
        sys.exit(1)
