"""Offline unit tests for the captcha-solver integration.

These tests do not require a browser or network access. They cover the pure
detection logic (:func:`captcha.detect_captcha`), the adapter loader
(:func:`captcha.get_solver`) and the 2captcha adapter's type mapping (with a
fake 2captcha client).

Run with::

    python -m unittest tests_captcha        # from the src/ directory
"""
import os
import unittest
from unittest import mock

import captcha
from captcha import TURNSTILE, HCAPTCHA, RECAPTCHA


class TestDetectCaptcha(unittest.TestCase):

    def test_none_when_empty(self):
        self.assertIsNone(captcha.detect_captcha({}))
        self.assertIsNone(captcha.detect_captcha(None))

    def test_turnstile_widget(self):
        facts = {"turnstileWidgets": [{"sitekey": "0xAAAA", "action": "login", "cdata": "abc"}]}
        result = captcha.detect_captcha(facts)
        self.assertEqual(result["type"], TURNSTILE)
        self.assertEqual(result["sitekey"], "0xAAAA")
        self.assertEqual(result["action"], "login")
        self.assertEqual(result["data"], "abc")

    def test_turnstile_from_iframe(self):
        facts = {
            "hasTurnstileResponse": True,
            "iframeSrcs": [
                "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/"
                "turnstile/if/ov2/av0/rcv/0x4AAAAAAABkMYinukE8nzYS/light/normal"
            ],
        }
        result = captcha.detect_captcha(facts)
        self.assertEqual(result["type"], TURNSTILE)
        self.assertEqual(result["sitekey"], "0x4AAAAAAABkMYinukE8nzYS")

    def test_hcaptcha_widget(self):
        facts = {"hcaptchaWidgets": [{"sitekey": "10000000-ffff-ffff-ffff-000000000001"}]}
        result = captcha.detect_captcha(facts)
        self.assertEqual(result["type"], HCAPTCHA)
        self.assertEqual(result["sitekey"], "10000000-ffff-ffff-ffff-000000000001")

    def test_hcaptcha_from_iframe(self):
        facts = {
            "hasHcaptchaResponse": True,
            "iframeSrcs": ["https://newassets.hcaptcha.com/captcha/v1/foo/static/"
                           "hcaptcha.html#frame=challenge&id=x&sitekey=abcd-123&theme=light"],
        }
        result = captcha.detect_captcha(facts)
        self.assertEqual(result["type"], HCAPTCHA)
        self.assertEqual(result["sitekey"], "abcd-123")

    def test_recaptcha_v2_widget(self):
        facts = {"recaptchaWidgets": [{"sitekey": "6Lc_key", "action": None}]}
        result = captcha.detect_captcha(facts)
        self.assertEqual(result["type"], RECAPTCHA)
        self.assertEqual(result["sitekey"], "6Lc_key")
        self.assertEqual(result["version"], "v2")

    def test_recaptcha_v3_widget(self):
        facts = {"recaptchaWidgets": [{"sitekey": "6Lc_key", "action": "homepage"}]}
        result = captcha.detect_captcha(facts)
        self.assertEqual(result["type"], RECAPTCHA)
        self.assertEqual(result["version"], "v3")
        self.assertEqual(result["action"], "homepage")

    def test_recaptcha_from_iframe(self):
        facts = {
            "hasRecaptchaResponse": True,
            "iframeSrcs": ["https://www.google.com/recaptcha/api2/anchor?ar=1&k=6LcSITEKEY&co=abc"],
        }
        result = captcha.detect_captcha(facts)
        self.assertEqual(result["type"], RECAPTCHA)
        self.assertEqual(result["sitekey"], "6LcSITEKEY")

    def test_priority_turnstile_over_others(self):
        facts = {
            "turnstileWidgets": [{"sitekey": "0xTS"}],
            "hcaptchaWidgets": [{"sitekey": "hc"}],
            "recaptchaWidgets": [{"sitekey": "rc"}],
        }
        self.assertEqual(captcha.detect_captcha(facts)["type"], TURNSTILE)

    def test_widget_without_sitekey_is_ignored(self):
        facts = {"turnstileWidgets": [{"sitekey": None}], "hasTurnstileResponse": True,
                 "iframeSrcs": []}
        self.assertIsNone(captcha.detect_captcha(facts))


class TestSolverLoader(unittest.TestCase):

    def setUp(self):
        captcha._SOLVER_CACHE.clear()

    def tearDown(self):
        captcha._SOLVER_CACHE.clear()

    def test_config_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(captcha.get_config_captcha_solver())
        with mock.patch.dict(os.environ, {"CAPTCHA_SOLVER": "none"}):
            self.assertIsNone(captcha.get_config_captcha_solver())
        with mock.patch.dict(os.environ, {"CAPTCHA_SOLVER": "2captcha"}):
            self.assertEqual(captcha.get_config_captcha_solver(), "2captcha")

    def test_get_solver_returns_none_when_unset(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(captcha.get_solver())

    def test_get_solver_unknown_adapter_raises(self):
        with mock.patch.dict(os.environ, {"CAPTCHA_SOLVER": "does_not_exist"}):
            with self.assertRaises(Exception):
                captcha.get_solver()

    def test_get_solver_2captcha_requires_api_key(self):
        with mock.patch.dict(os.environ, {"CAPTCHA_SOLVER": "2captcha"}, clear=True):
            with self.assertRaises(Exception):
                captcha.get_solver()

    def test_get_solver_2captcha_loads_and_maps_types(self):
        env = {"CAPTCHA_SOLVER": "2captcha", "TWOCAPTCHA_API_KEY": "test-key"}
        with mock.patch.dict(os.environ, env, clear=True):
            solver = captcha.get_solver()
            self.assertIsNotNone(solver)

            # replace the real 2captcha network client with a fake
            calls = {}

            class FakeClient:
                def turnstile(self, **kwargs):
                    calls["turnstile"] = kwargs
                    return {"captchaId": "1", "code": "ts-token"}

                def hcaptcha(self, **kwargs):
                    calls["hcaptcha"] = kwargs
                    return {"captchaId": "2", "code": "hc-token"}

                def recaptcha(self, **kwargs):
                    calls["recaptcha"] = kwargs
                    return {"captchaId": "3", "code": "rc-token"}

            solver._client = FakeClient()

            self.assertEqual(
                solver.solve_turnstile(url="http://x", sitekey="0xTS", action="a",
                                       data="d", useragent="UA"),
                "ts-token")
            self.assertEqual(calls["turnstile"]["sitekey"], "0xTS")
            self.assertEqual(calls["turnstile"]["action"], "a")
            self.assertEqual(calls["turnstile"]["useragent"], "UA")

            self.assertEqual(solver.solve_hcaptcha(url="http://x", sitekey="hc"), "hc-token")
            self.assertEqual(calls["hcaptcha"]["sitekey"], "hc")

            self.assertEqual(
                solver.solve_recaptcha(url="http://x", sitekey="rc", version="v3", action="home"),
                "rc-token")
            self.assertEqual(calls["recaptcha"]["version"], "v3")

    def test_get_solver_is_cached(self):
        env = {"CAPTCHA_SOLVER": "2captcha", "TWOCAPTCHA_API_KEY": "test-key"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIs(captcha.get_solver(), captcha.get_solver())


class FakeDriver:
    """Minimal stand-in for a Selenium WebDriver used by the service tests."""

    def __init__(self, facts, url="http://example.test/"):
        self._facts = facts
        self.current_url = url
        self.injected = []

    def execute_script(self, script, *args):
        if script == captcha.CAPTCHA_DETECT_JS:
            return self._facts
        self.injected.append((script, args))
        return None


class TestServiceIntegration(unittest.TestCase):
    """Exercise the wiring in flaresolverr_service without a browser."""

    def setUp(self):
        import utils
        import flaresolverr_service as svc
        from dtos import V1RequestBase
        self.svc = svc
        self.V1RequestBase = V1RequestBase
        utils.USER_AGENT = "test-user-agent"  # avoid spawning a real webdriver
        self._sleep_patch = mock.patch("flaresolverr_service.time.sleep")
        self._sleep_patch.start()

    def tearDown(self):
        self._sleep_patch.stop()

    def test_no_solver_configured_returns_none(self):
        driver = FakeDriver({"turnstileWidgets": [{"sitekey": "0xTS"}]})
        with mock.patch.object(captcha, "get_solver", return_value=None):
            result = self.svc._solve_captcha_if_present(self.V1RequestBase({}), driver, set())
        self.assertIsNone(result)
        self.assertEqual(driver.injected, [])

    def test_turnstile_solved_and_injected(self):
        facts = {"turnstileWidgets": [{"sitekey": "0xTS", "action": None, "cdata": None}]}
        driver = FakeDriver(facts)
        fake_solver = mock.Mock()
        fake_solver.solve_turnstile.return_value = "ts-token"
        with mock.patch.object(captcha, "get_solver", return_value=fake_solver):
            result = self.svc._solve_captcha_if_present(self.V1RequestBase({}), driver, set())
        self.assertEqual(result, {"type": TURNSTILE, "token": "ts-token"})
        fake_solver.solve_turnstile.assert_called_once()
        self.assertIn(captcha.CAPTCHA_INJECT_JS[TURNSTILE], [s for s, _ in driver.injected])
        self.assertIn(("ts-token",), [a for _, a in driver.injected])

    def test_hcaptcha_solved_and_injected(self):
        facts = {"hcaptchaWidgets": [{"sitekey": "hc-key"}]}
        driver = FakeDriver(facts)
        fake_solver = mock.Mock()
        fake_solver.solve_hcaptcha.return_value = "hc-token"
        with mock.patch.object(captcha, "get_solver", return_value=fake_solver):
            result = self.svc._solve_captcha_if_present(self.V1RequestBase({}), driver, set())
        self.assertEqual(result["type"], HCAPTCHA)
        fake_solver.solve_hcaptcha.assert_called_once_with(url="http://example.test/", sitekey="hc-key")

    def test_same_sitekey_not_submitted_twice(self):
        facts = {"turnstileWidgets": [{"sitekey": "0xTS"}]}
        driver = FakeDriver(facts)
        fake_solver = mock.Mock()
        fake_solver.solve_turnstile.return_value = "ts-token"
        attempted = set()
        with mock.patch.object(captcha, "get_solver", return_value=fake_solver):
            first = self.svc._solve_captcha_if_present(self.V1RequestBase({}), driver, attempted)
            second = self.svc._solve_captcha_if_present(self.V1RequestBase({}), driver, attempted)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        fake_solver.solve_turnstile.assert_called_once()

    def test_no_captcha_present_returns_none(self):
        driver = FakeDriver({"iframeSrcs": []})
        fake_solver = mock.Mock()
        with mock.patch.object(captcha, "get_solver", return_value=fake_solver):
            result = self.svc._solve_captcha_if_present(self.V1RequestBase({}), driver, set())
        self.assertIsNone(result)
        fake_solver.solve_turnstile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
