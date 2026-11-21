"""HTTP behaviour that doesn't need a database."""
import unittest
from unittest import mock
import db_manager as dm
from app import app


class Api(unittest.TestCase):
    def setUp(self):
        dm._connections.clear()
        self.client = app.test_client()

    def test_not_connected_returns_401(self):
        for method, url in [("get", "/api/tables"), ("get", "/api/tables/x/data"),
                            ("post", "/api/query"), ("get", "/api/connection")]:
            r = getattr(self.client, method)(url, headers={"X-Connection-Id": "nope"})
            self.assertEqual(r.status_code, 401, url)
            self.assertFalse(r.get_json()["success"])

    def test_validation_errors_are_400(self):
        r = self.client.post("/api/connect", json={"db_type": "oracle"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("PostgreSQL or MySQL", r.get_json()["error"])

    def test_only_local_host_names_are_accepted(self):
        for host in ["127.0.0.1:52300", "localhost:52300", "localhost", "[::1]:52300"]:
            r = self.client.get("/api/health", headers={"Host": host})
            self.assertEqual(r.status_code, 200, host)
        # A website using DNS rebinding arrives with its own host name
        for host in ["evil.example.com", "evil.example.com:52300", "192.168.1.5:52300"]:
            r = self.client.get("/api/health", headers={"Host": host})
            self.assertEqual(r.status_code, 403, host)

    def test_form_posts_cannot_send_login_details(self):
        # A cross-site <form> can't send JSON; without JSON the request carries nothing
        r = self.client.post("/api/databases", data={"db_type": "mysql", "user": "root"})
        self.assertEqual(r.status_code, 400)

    def test_unknown_api_path_is_json_404(self):
        r = self.client.get("/api/nope")
        self.assertEqual(r.status_code, 404)
        self.assertFalse(r.get_json()["success"])

    def test_page_links_serve_the_app(self):
        import app as app_module
        if not (app_module.STATIC_DIR / "index.html").exists():
            self.skipTest("frontend not built")
        for path in ["/", "/tables/orders", "/query"]:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn(b'<div id="root">', r.data)
        # Paths outside the built app never return its files (they get the page or a 404)
        for path in ["/../backend/app.py", "/..%2Fbackend%2Fapp.py",
                     "/assets/..%2F..%2Fbackend%2Fapp.py", "/%2E%2E/%2E%2E/backend/app.py"]:
            self.assertNotIn(b"import", self.client.get(path).data, path)

    def test_unexpected_errors_hide_details_unless_debug(self):
        app.logger.disabled = True
        self.addCleanup(setattr, app.logger, "disabled", False)
        with mock.patch("routes.connection_routes.get_cfg", side_effect=RuntimeError("secret detail")):
            r = self.client.get("/api/connection")
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("secret detail", r.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
