"""
Unit tests for the engine seam and the Scrapling engine's pure logic.

These need neither a browser nor a network, so they are safe to run in CI. The
browser-driven coverage stays in `tests.py` / `tests_sites.py`.

    python -m unittest tests_engines -v
"""

import os
import unittest
from unittest.mock import patch

from dtos import V1RequestBase
from engines import create_engine
from engines.challenges import (CHALLENGE_SELECTOR_CSS, title_is_access_denied,
                                title_is_challenge)


class TestEngineRegistry(unittest.TestCase):

    def test_default_engine_is_undetected_chromedriver(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('BROWSER_ENGINE', None)
            self.assertEqual('uc', create_engine().name)

    def test_aliases_resolve(self):
        for alias in ('uc', 'undetected', 'selenium', 'UC', '  uc  '):
            with patch.dict(os.environ, {'BROWSER_ENGINE': alias}):
                self.assertEqual('uc', create_engine().name)

    def test_unknown_engine_is_rejected(self):
        with patch.dict(os.environ, {'BROWSER_ENGINE': 'nope'}):
            with self.assertRaises(Exception) as ctx:
                create_engine()
            self.assertIn('Unknown BROWSER_ENGINE', str(ctx.exception))

    def test_empty_engine_falls_back_to_default(self):
        with patch.dict(os.environ, {'BROWSER_ENGINE': ''}):
            self.assertEqual('uc', create_engine().name)

    def test_both_engines_satisfy_the_protocol(self):
        required = ('startup', 'shutdown', 'user_agent', 'create_session',
                    'list_sessions', 'destroy_session', 'solve')
        for engine_name in ('uc', 'scrapling'):
            with patch.dict(os.environ, {'BROWSER_ENGINE': engine_name}):
                try:
                    engine = create_engine()
                except Exception as e:  # pragma: no cover - scrapling extras absent
                    self.skipTest(f'{engine_name} engine unavailable: {e}')
                for attribute in required:
                    self.assertTrue(callable(getattr(engine, attribute, None)),
                                    f'{engine_name}.{attribute} missing')


class TestChallengeFingerprints(unittest.TestCase):

    def test_access_denied_matches_on_prefix(self):
        self.assertTrue(title_is_access_denied('Access denied | example.com'))
        self.assertFalse(title_is_access_denied('Totally fine'))

    def test_challenge_title_match_is_exact_and_case_insensitive(self):
        self.assertTrue(title_is_challenge('just a moment...'))
        self.assertTrue(title_is_challenge('DDoS-Guard'))
        # Exact match only, so a page merely mentioning it is not a challenge
        self.assertFalse(title_is_challenge('Just a moment... | Blog post'))
        self.assertFalse(title_is_challenge(''))
        self.assertFalse(title_is_challenge(None))

    def test_selector_css_is_a_single_locator_expression(self):
        self.assertIn(',', CHALLENGE_SELECTOR_CSS)
        self.assertNotIn(',,', CHALLENGE_SELECTOR_CSS)


def _scrapling_or_skip(test):
    try:
        import engines.scrapling_engine as mod
    except ImportError as e:  # pragma: no cover
        test.skipTest(f'Scrapling not installed: {e}')
    return mod


class TestPostForm(unittest.TestCase):
    """The generated form must stay identical to the Selenium engine's."""

    def test_matches_selenium_engine_output(self):
        mod = _scrapling_or_skip(self)
        import engines.undetected as uc_engine

        captured = {}

        class FakeDriver:
            def get(self, url):
                captured['url'] = url

        for post_data in ('a=b&c=d%20e',
                          'nm=&pn=&submit=%CF%EE%E8%F1%EA',
                          '?a=b',
                          'q=a%22b&empty=',
                          'f%5B%5D=-1&o=1&s=2'):
            req = V1RequestBase({'url': 'https://t.example/p', 'postData': post_data})
            uc_engine._post_request(req, FakeDriver())
            theirs = captured['url']
            mine = mod._build_post_form(req).replace(f'id="{mod._POST_FORM_ID}"', 'id="hackForm"')
            self.assertIn(mine, theirs, f'form diverged for {post_data!r}')

    def test_submit_field_is_dropped(self):
        mod = _scrapling_or_skip(self)
        req = V1RequestBase({'url': 'https://t.example/p', 'postData': 'a=b&submit=go'})
        form = mod._build_post_form(req)
        self.assertIn('name="a"', form)
        self.assertNotIn('name="submit"', form)

    def test_empty_post_data_produces_an_empty_form(self):
        mod = _scrapling_or_skip(self)
        req = V1RequestBase({'url': 'https://t.example/p', 'postData': ''})
        self.assertIn('</form>', mod._build_post_form(req))


class TestCookieMapping(unittest.TestCase):

    def test_session_cookie_keeps_expires_and_omits_expiry(self):
        mod = _scrapling_or_skip(self)
        out = mod._normalize_out_cookies([{'name': 'a', 'value': '1', 'expires': -1}])[0]
        self.assertEqual(-1.0, out['expires'])
        self.assertTrue(out['session'])
        self.assertNotIn('expiry', out)

    def test_persistent_cookie_gets_both_expires_and_expiry(self):
        mod = _scrapling_or_skip(self)
        out = mod._normalize_out_cookies([{'name': 'b', 'value': '2', 'expires': 1893456000.5}])[0]
        self.assertEqual(1893456000, out['expiry'])
        self.assertEqual(1893456000.5, out['expires'])
        self.assertFalse(out['session'])

    def test_missing_or_bad_expires_is_treated_as_a_session_cookie(self):
        mod = _scrapling_or_skip(self)
        for raw in ({'name': 'c', 'value': '3'}, {'name': 'c', 'value': '3', 'expires': 'soon'}):
            out = mod._normalize_out_cookies([raw])[0]
            self.assertTrue(out['session'])
            self.assertEqual(-1.0, out['expires'])

    def test_inbound_cookie_gets_a_url_when_it_has_no_domain(self):
        mod = _scrapling_or_skip(self)
        out = mod._sanitize_in_cookie({'name': 'x', 'value': 'y'}, 'https://t.example/p')
        self.assertEqual('https://t.example/p', out['url'])

    def test_inbound_cookie_with_a_domain_is_left_alone(self):
        mod = _scrapling_or_skip(self)
        out = mod._sanitize_in_cookie(
            {'name': 'z', 'value': 'w', 'domain': '.t.example', 'path': '/'}, 'https://t.example/p')
        self.assertNotIn('url', out)
        self.assertEqual('.t.example', out['domain'])

    def test_inbound_expiry_is_mapped_to_expires(self):
        mod = _scrapling_or_skip(self)
        out = mod._sanitize_in_cookie(
            {'name': 'z', 'value': 'w', 'domain': 'x', 'expiry': 1893456000}, 'https://t.example/p')
        self.assertEqual(1893456000.0, out['expires'])

    def test_keys_playwright_rejects_are_dropped(self):
        mod = _scrapling_or_skip(self)
        out = mod._sanitize_in_cookie(
            {'name': 'j', 'value': 'k', 'size': 12, 'session': False, 'junk': 'x'},
            'https://t.example/p')
        for key in ('size', 'session', 'junk'):
            self.assertNotIn(key, out)

    def test_nameless_cookie_is_rejected(self):
        mod = _scrapling_or_skip(self)
        self.assertIsNone(mod._sanitize_in_cookie({'value': 'orphan'}, 'https://t.example/p'))


class TestProxyMapping(unittest.TestCase):

    def test_url_becomes_server(self):
        mod = _scrapling_or_skip(self)
        self.assertEqual({'server': 'http://127.0.0.1:8888'},
                         mod._proxy_to_scrapling({'url': 'http://127.0.0.1:8888'}))

    def test_credentials_are_passed_through_natively(self):
        mod = _scrapling_or_skip(self)
        converted = mod._proxy_to_scrapling(
            {'url': 'socks5://h:1080', 'username': 'u', 'password': 'p'})
        self.assertEqual({'server': 'socks5://h:1080', 'username': 'u', 'password': 'p'}, converted)

    def test_absent_or_empty_proxy_is_none(self):
        mod = _scrapling_or_skip(self)
        for value in (None, {}, {'url': ''}):
            self.assertIsNone(mod._proxy_to_scrapling(value))

    def test_key_separates_sessions_by_proxy_and_user(self):
        mod = _scrapling_or_skip(self)
        self.assertEqual('direct', mod._proxy_key(None))
        first = mod._proxy_key({'url': 'http://p:1', 'username': 'a'})
        second = mod._proxy_key({'url': 'http://p:1', 'username': 'b'})
        self.assertNotEqual(first, second)


class TestDisplayMode(unittest.TestCase):

    def test_headless_false_never_starts_a_virtual_display(self):
        mod = _scrapling_or_skip(self)
        with patch.dict(os.environ, {'HEADLESS': 'false'}):
            self.assertEqual((False, False), mod.resolve_display_mode())

    def test_linux_runs_head_full_under_xvfb(self):
        mod = _scrapling_or_skip(self)
        with patch.dict(os.environ, {'HEADLESS': 'true'}), \
                patch.object(mod.sys, 'platform', 'linux'):
            self.assertEqual((False, True), mod.resolve_display_mode())

    def test_platforms_without_xvfb_use_real_headless(self):
        mod = _scrapling_or_skip(self)
        for platform_name in ('darwin', 'win32'):
            with patch.dict(os.environ, {'HEADLESS': 'true'}), \
                    patch.object(mod.sys, 'platform', platform_name):
                self.assertEqual((True, False), mod.resolve_display_mode())


class TestMediaBlocking(unittest.TestCase):

    def test_stylesheets_are_never_blocked(self):
        """The Turnstile solver clicks a bounding box, so it needs layout."""
        mod = _scrapling_or_skip(self)
        self.assertNotIn('stylesheet', mod._MEDIA_RESOURCE_TYPES)
        for blocked in ('image', 'media', 'font'):
            self.assertIn(blocked, mod._MEDIA_RESOURCE_TYPES)


if __name__ == '__main__':
    unittest.main()
