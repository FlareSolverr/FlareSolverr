"""Regression tests for the /v1 authentication gate (CWE-306).

These lock in the hardening that stops the command surface from being
driven anonymously: /v1 must reject requests without a valid
`Authorization: Bearer <token>` header, while /health and / stay open
for health checks and expose no commands.

Run with:  python -m unittest src/tests_auth.py   (from the repo root)
or:        python -m unittest tests_auth          (from src/)
"""
import unittest

from webtest import TestApp

import flaresolverr

TEST_API_TOKEN = 'test-api-token'


class TestAuthGate(unittest.TestCase):
    # Fixed token so the gate can be exercised deterministically.
    @classmethod
    def setUpClass(cls):
        flaresolverr.API_TOKEN = TEST_API_TOKEN
        cls.app = TestApp(flaresolverr.app)

    def test_health_remains_unauthenticated(self):
        self.assertEqual(self.app.get('/health').status_code, 200)

    def test_v1_rejects_missing_token(self):
        res = self.app.post_json(
            '/v1', {"cmd": "request.get", "url": "http://example.com"},
            status=401, expect_errors=True,
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json['status_code'], 401)
        self.assertIn('Unauthorized', res.json['error'])

    def test_v1_rejects_wrong_token(self):
        res = self.app.post_json(
            '/v1', {"cmd": "request.get", "url": "http://example.com"},
            headers={'Authorization': 'Bearer definitely-wrong'},
            status=401, expect_errors=True,
        )
        self.assertEqual(res.status_code, 401)

    def test_v1_rejects_token_without_bearer_prefix(self):
        res = self.app.post_json(
            '/v1', {"cmd": "request.get", "url": "http://example.com"},
            headers={'Authorization': TEST_API_TOKEN},
            status=401, expect_errors=True,
        )
        self.assertEqual(res.status_code, 401)

    def test_v1_accepts_valid_token(self):
        # A valid token must pass the gate and reach the command dispatcher;
        # an invalid command then yields the normal validation error (500),
        # not a 401.
        res = self.app.post_json(
            '/v1', {"cmd": "request.bad", "url": "http://example.com"},
            headers={'Authorization': 'Bearer ' + TEST_API_TOKEN},
            status=500, expect_errors=True,
        )
        self.assertEqual(res.status_code, 500)
        self.assertNotEqual(res.status_code, 401)

    def test_default_bind_uses_loopback(self):
        import inspect
        source = inspect.getsource(flaresolverr)
        self.assertIn("os.environ.get('HOST', '127.0.0.1')", source)
        self.assertNotIn("os.environ.get('HOST', '0.0.0.0')", source)

    def test_missing_api_token_generates_random_secret(self):
        import inspect
        source = inspect.getsource(flaresolverr)
        self.assertIn('_load_auth_token', source)
        self.assertIn('secrets.token_urlsafe', source)


if __name__ == '__main__':
    unittest.main()
