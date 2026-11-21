"""Shut the packaged app down when nobody is using it any more.

Each open page (window or tab) picks a random id and calls /api/session/heartbeat every few
seconds, and /api/session/bye when it closes. The app exits:
  * a few seconds after the last page said bye (a reload says bye and comes straight back,
    so a short grace period keeps it alive), or
  * when the last page stopped sending heartbeats (browser crashed or killed), or
  * if no page ever opened within the startup timeout.

Only the packaged app turns this on; the dev server (python app.py) never shuts itself down.
"""
import logging
import os
import threading
import time

log = logging.getLogger("database-explorer")


def _env(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


class Watchdog:
    def __init__(self, on_idle, close_grace=None, heartbeat_timeout=None, startup_timeout=None,
                 clock=time.monotonic):
        self.on_idle = on_idle
        # Settings can be shortened through environment variables for testing
        self.close_grace = close_grace if close_grace is not None else _env("DBX_CLOSE_GRACE", 6)
        # Browsers slow timers in hidden/minimised windows to about once a minute, so this must be
        # comfortably longer than that
        self.heartbeat_timeout = (heartbeat_timeout if heartbeat_timeout is not None
                                  else _env("DBX_HEARTBEAT_TIMEOUT", 150))
        self.startup_timeout = (startup_timeout if startup_timeout is not None
                                else _env("DBX_STARTUP_TIMEOUT", 120))
        self.clock = clock
        self._lock = threading.Lock()
        self._pages = {}              # page id -> last heartbeat
        self._closed = set()          # ids of pages that said bye
        self._started = clock()
        self._empty_since = None      # when the last page went away
        self._fired = False

    def beat(self, page_id):
        with self._lock:
            if page_id in self._closed:  # a late heartbeat from a page that already closed
                return
            self._pages[page_id] = self.clock()
            self._empty_since = None

    def bye(self, page_id):
        """Returns False for an unknown page id (nothing changes)."""
        with self._lock:
            # Remember it: if the page closed right after opening, its first heartbeat may
            # still be on its way and must not bring it back
            self._closed.add(page_id)
            if len(self._closed) > 1000:
                self._closed.clear()
            if self._pages.pop(page_id, None) is None:
                return False
            if not self._pages:
                self._empty_since = self.clock()
            return True

    def should_stop(self):
        now = self.clock()
        with self._lock:
            expired = [p for p, seen in self._pages.items() if now - seen > self.heartbeat_timeout]
            for pid in expired:
                del self._pages[pid]
            if self._pages:
                return False
            if expired:
                # The last page went silent long ago: no reload grace needed
                self._empty_since = now
                return True
            if self._empty_since is None:  # no page has opened yet
                return now - self._started > self.startup_timeout
            return now - self._empty_since > self.close_grace

    def check(self):
        if not self._fired and self.should_stop():
            self._fired = True
            log.info("No open windows: shutting down")
            self.on_idle()

    def start(self, interval=1.0):
        def loop():
            while not self._fired:
                time.sleep(interval)
                self.check()
        threading.Thread(target=loop, name="watchdog", daemon=True).start()
        return self
