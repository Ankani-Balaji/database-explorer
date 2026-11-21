"""Entry point of the packaged app (DatabaseExplorer.exe).

Starts the server on this computer only (127.0.0.1) and opens the browser. If the app is
already running, it just opens another browser tab instead of starting a second copy.
"""
import json
import logging
import os
import socket
import sys
import threading
import urllib.request
import webbrowser

PORTS = range(52300, 52311)  # an uncommon range, to avoid clashing with other local servers


def set_title(title):
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:
            pass


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


def main():
    set_title("Database Explorer")
    print("Starting Database Explorer...")
    from waitress import create_server
    from app import app, APP_NAME, VERSION

    for port in PORTS:
        if already_running(port, APP_NAME):
            url = f"http://127.0.0.1:{port}/"
            print(f"Database Explorer is already running: opening {url}")
            if not os.environ.get("DBX_NO_BROWSER"):
                webbrowser.open(url)
            return
    port = next((p for p in PORTS if port_free(p)), None)
    if port is None:
        raise RuntimeError(f"No free port between {PORTS.start} and {PORTS.stop - 1}.")

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    server = create_server(app, host="127.0.0.1", port=port, threads=8)
    url = f"http://127.0.0.1:{port}/"
    print()
    print(f"  Database Explorer {VERSION} is running at {url}")
    print("  Your browser should open by itself. If it doesn't, open that address.")
    print("  Only this computer can use it.")
    print()
    print("  Keep this window open while you use the app. Close it to stop.")
    print()
    if not os.environ.get("DBX_NO_BROWSER"):  # set for automated tests
        threading.Timer(1.0, webbrowser.open, [url]).start()
    server.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nDatabase Explorer could not start: {e}")
        if getattr(sys, "frozen", False):
            input("Press Enter to close this window.")
        sys.exit(1)
