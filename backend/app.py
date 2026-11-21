import datetime, decimal, logging, os, sys, uuid
from pathlib import Path
from flask import Flask, abort, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from db_manager import ApiError
from routes.connection_routes import bp as connection_bp
from routes.table_routes import bp as table_bp

APP_NAME = "database-explorer"
VERSION = "1.1.0"
FROZEN = getattr(sys, "frozen", False)  # running from the packaged .exe

# The built React app (npm run build). Inside the .exe, PyInstaller unpacks it to sys._MEIPASS.
STATIC_DIR = (Path(sys._MEIPASS) / "frontend_dist" if FROZEN
              else Path(__file__).resolve().parent.parent / "frontend" / "dist")

# The app may only be opened as http://127.0.0.1 or http://localhost. Checking the Host header
# stops other websites from reaching it through "DNS rebinding" tricks.
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


class Provider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()
        if isinstance(o, (decimal.Decimal, uuid.UUID, datetime.timedelta)):  # Decimal as text keeps every digit
            return str(o)
        if isinstance(o, (bytes, bytearray, memoryview)):
            return "\\x" + bytes(o).hex()
        if isinstance(o, (set, frozenset)):
            return list(o)
        return DefaultJSONProvider.default(o)


app = Flask(__name__, static_folder=None)
app.json = Provider(app)
app.json.sort_keys = False  # keep column order
if not FROZEN:
    # Development only: the Vite dev server (another port) calls the API. The packaged app serves
    # the page and the API from the same address, so it needs no cross-origin access at all.
    CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173"],
         expose_headers=["X-Export-Truncated", "X-Export-Rows"])
app.register_blueprint(connection_bp)
app.register_blueprint(table_bp)


@app.before_request
def only_local():
    host = request.host.rsplit(":", 1)[0] if not request.host.endswith("]") else request.host
    if host.lower() not in LOCAL_HOSTS:
        return jsonify(success=False, error="This app only accepts connections from this computer."), 403
    return None


@app.get("/api/health")
def health():
    return jsonify(success=True, app=APP_NAME, version=VERSION)


# Set by launcher.py in the packaged app (see lifecycle.py); None in development.
app.config["WATCHDOG"] = None


def _page_id():
    # sendBeacon (used when a page closes) may send any content type, so parse leniently
    data = request.get_json(silent=True, force=True) or {}
    page = str(data.get("page") or "")
    return page if 8 <= len(page) <= 64 else ""


@app.post("/api/session/heartbeat")
def heartbeat():
    # JSON only: a cross-site request with this content type needs CORS, which isn't granted
    if not request.is_json:
        return jsonify(success=False, error="JSON required"), 415
    page, dog = _page_id(), app.config["WATCHDOG"]
    if page and dog:
        dog.beat(page)
    return jsonify(success=True, auto_close=bool(dog))


@app.post("/api/session/bye")
def bye():
    page, dog = _page_id(), app.config["WATCHDOG"]
    if dog:
        known = bool(page) and dog.bye(page)  # unknown (guessed) ids are ignored
        logging.getLogger("database-explorer").info(
            "Window closed" if known else "Ignored a close message for an unknown window")
    return ("", 204)


@app.get("/")
@app.get("/<path:path>")
def frontend(path=""):
    """Serve the React app. Unknown paths get index.html so page links like /tables/x work."""
    if path.startswith("api/"):
        abort(404)
    if not (STATIC_DIR / "index.html").exists():
        return ("The frontend isn't built yet. Run `npm run build` in the frontend folder, "
                "or use the dev server at http://localhost:5173."), 404
    if path and (STATIC_DIR / path).is_file():
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


@app.errorhandler(ApiError)
def api_error(e):
    return jsonify(success=False, error=str(e)), e.status


@app.errorhandler(Exception)
def server_error(e):
    if isinstance(e, HTTPException):
        if request.path.startswith("/api/"):
            return jsonify(success=False, error=e.description), e.code
        return e
    app.logger.exception("Unexpected error")  # full traceback in the backend terminal
    if app.debug:
        return jsonify(success=False, error=f"{type(e).__name__}: {e}"), 500
    return jsonify(success=False, error="Unexpected server error (details are in the backend terminal)"), 500


if __name__ == "__main__":
    # Debug mode (auto-reload + interactive debugger, which can run code) only when asked for:
    #   $env:FLASK_DEBUG = "1"; python app.py
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host="127.0.0.1", port=5000, debug=debug)
