"""When the desktop app shuts itself down (and, just as important, when it doesn't)."""
import unittest
from app import app
from lifecycle import Watchdog


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class WatchdogRules(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.stopped = []
        self.dog = Watchdog(on_idle=lambda: self.stopped.append(True), close_grace=6,
                            heartbeat_timeout=150, startup_timeout=120, clock=self.clock)

    def at(self, t):
        self.clock.t = t
        self.dog.check()
        return bool(self.stopped)

    def test_stays_up_while_a_window_is_open(self):
        for t in range(0, 600, 5):
            self.dog.beat("page-1-abcdef")
            self.assertFalse(self.at(t))

    def test_closes_shortly_after_the_window_closes(self):
        self.dog.beat("page-1-abcdef")
        self.clock.t = 30
        self.dog.bye("page-1-abcdef")
        self.assertFalse(self.at(34))
        self.assertTrue(self.at(37))

    def test_reload_does_not_close(self):
        self.dog.beat("page-1-abcdef")
        self.clock.t = 30
        self.dog.bye("page-1-abcdef")      # the old page goes away...
        self.clock.t = 31
        self.dog.beat("page-2-abcdef")     # ...and the reloaded page arrives
        self.assertFalse(self.at(100))

    def test_other_window_keeps_it_open(self):
        self.dog.beat("page-1-abcdef")
        self.dog.beat("page-2-abcdef")
        self.dog.bye("page-1-abcdef")
        for t in range(0, 300, 5):
            self.dog.beat("page-2-abcdef")
            self.assertFalse(self.at(t))

    def test_slow_heartbeats_from_a_minimised_window_are_fine(self):
        for t in range(0, 600, 60):        # browsers slow hidden pages to about once a minute
            self.dog.beat("page-1-abcdef")
            self.assertFalse(self.at(t + 59))

    def test_closes_when_the_browser_vanishes_without_saying_bye(self):
        self.dog.beat("page-1-abcdef")
        self.assertFalse(self.at(149))
        self.assertTrue(self.at(160))

    def test_closes_if_no_window_ever_opens(self):
        self.assertFalse(self.at(119))
        self.assertTrue(self.at(121))

    def test_bye_arriving_before_the_first_heartbeat(self):
        # Window closed a split second after opening: bye overtakes the first heartbeat
        self.dog.bye("page-1-abcdef")
        self.dog.beat("page-1-abcdef")
        self.assertEqual(self.dog._pages, {})
        self.assertTrue(self.at(130))  # back to "no window ever opened"

    def test_unknown_page_bye_is_ignored(self):
        self.dog.beat("page-1-abcdef")
        self.assertFalse(self.dog.bye("guessed-id-123"))
        self.assertFalse(self.at(100))

    def test_fires_only_once(self):
        self.at(200)
        self.at(300)
        self.assertEqual(len(self.stopped), 1)


class SessionEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.clock = Clock()
        self.dog = Watchdog(on_idle=lambda: None, close_grace=6, heartbeat_timeout=150,
                            startup_timeout=120, clock=self.clock)
        app.config["WATCHDOG"] = self.dog
        self.addCleanup(app.config.__setitem__, "WATCHDOG", None)

    def test_heartbeat_and_bye(self):
        r = self.client.post("/api/session/heartbeat", json={"page": "page-1-abcdef"})
        self.assertTrue(r.get_json()["auto_close"])
        self.assertIn("page-1-abcdef", self.dog._pages)
        # sendBeacon from a closing page
        r = self.client.post("/api/session/bye", data='{"page": "page-1-abcdef"}', content_type="text/plain")
        self.assertEqual(r.status_code, 204)
        self.assertNotIn("page-1-abcdef", self.dog._pages)

    def test_heartbeat_requires_json(self):
        # A cross-site form can't send JSON, so it can't keep the app running
        r = self.client.post("/api/session/heartbeat", data="page=page-1-abcdef")
        self.assertEqual(r.status_code, 415)
        self.assertEqual(self.dog._pages, {})

    def test_development_server_reports_no_auto_close(self):
        app.config["WATCHDOG"] = None
        r = self.client.post("/api/session/heartbeat", json={"page": "page-1-abcdef"})
        self.assertFalse(r.get_json()["auto_close"])


if __name__ == "__main__":
    unittest.main()
