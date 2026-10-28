"""Offline regression tests: python -m unittest discover -s src -p test_performance.py."""
import logging
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from webtest import TestApp

import flaresolverr
import flaresolverr_service as service
import utils
from dtos import V1RequestBase


class PerformanceRegressionTests(unittest.TestCase):
    def setUp(self):
        self.driver = MagicMock()
        self.driver.title = 'Example'
        self.driver.current_url = 'https://example.com/'
        self.driver.page_source = '<html><body>Example</body></html>'
        self.driver.find_elements.return_value = []
        self.driver.get_cookies.return_value = [{'name': 'a', 'value': 'b'}]
        self.driver.get_screenshot_as_base64.return_value = 'aW1hZ2U='
        self.req = V1RequestBase({'url': 'https://example.com/', 'maxTimeout': 60000})
        self.patches = [
            patch.object(utils, 'get_user_agent', return_value='Chrome/test'),
            patch.object(utils, 'get_config_disable_media', return_value=False),
            patch.object(utils, 'get_config_log_html', return_value=False),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_no_challenge_uses_two_selector_round_trips(self):
        result = service._evil_logic(self.req, self.driver, 'GET')
        self.assertEqual('Challenge not detected!', result.message)
        self.assertEqual(2, self.driver.find_elements.call_count)
        self.assertEqual({
            'url': 'https://example.com/', 'status': 200,
            'userAgent': 'Chrome/test', 'turnstile_token': None,
            'headers': {}, 'response': self.driver.page_source,
            'cookies': [{'name': 'a', 'value': 'b'}],
        }, utils.object_to_dict(result.result))

    def test_access_denied_keeps_error(self):
        self.driver.find_elements.return_value = [object()]
        with self.assertRaisesRegex(Exception, 'Cloudflare has blocked this request'):
            service._evil_logic(self.req, self.driver, 'GET')

    def test_selector_challenge_keeps_individual_waits_and_redirect(self):
        self.driver.find_elements.side_effect = [[], [object()]]
        with patch.object(service, 'WebDriverWait') as wait:
            result = service._evil_logic(self.req, self.driver, 'GET')
        self.assertEqual('Challenge solved!', result.message)
        self.assertEqual(len(service.CHALLENGE_TITLES) + len(service.CHALLENGE_SELECTORS),
                         wait.return_value.until_not.call_count)
        wait.return_value.until.assert_called_once()

    def test_cookie_only_and_screenshot_keep_response_shape(self):
        self.req.returnOnlyCookies = True
        self.req.returnScreenshot = True
        result = utils.object_to_dict(service._evil_logic(self.req, self.driver, 'GET').result)
        self.assertNotIn('response', result)
        self.assertNotIn('headers', result)
        self.assertEqual('aW1hZ2U=', result['screenshot'])
        self.assertEqual([{'name': 'a', 'value': 'b'}], result['cookies'])

    def test_log_html_does_not_fetch_source_when_debug_disabled(self):
        self.req.returnOnlyCookies = True
        with patch.object(utils, 'get_config_log_html', return_value=True), \
                patch.object(logging.getLogger(), 'isEnabledFor', return_value=False), \
                patch.object(type(self.driver), 'page_source', new_callable=PropertyMock, create=True) as source:
            service._evil_logic(self.req, self.driver, 'GET')
        source.assert_not_called()

    def test_disabled_logs_do_not_serialize_request_or_response(self):
        with patch.object(logging.getLogger(), 'isEnabledFor', return_value=False), \
                patch.object(utils, 'object_to_dict') as serialize:
            result = service.controller_v1_endpoint(V1RequestBase({'cmd': 'sessions.list'}))
        serialize.assert_not_called()
        self.assertEqual('ok', result.status)

    def test_debug_keeps_request_and_response_logging(self):
        with patch.object(logging.getLogger(), 'isEnabledFor', return_value=True), \
                patch.object(utils, 'object_to_dict', wraps=utils.object_to_dict) as serialize, \
                patch.object(logging, 'debug') as debug:
            service.controller_v1_endpoint(V1RequestBase({'cmd': 'sessions.list'}))
        self.assertEqual(2, serialize.call_count)
        self.assertTrue(any(call.args[0] == 'Response => POST /v1 body: %s'
                            for call in debug.call_args_list))

    def test_log_html_still_fetches_source_with_debug(self):
        self.req.returnOnlyCookies = True
        with patch.object(utils, 'get_config_log_html', return_value=True), \
                patch.object(logging.getLogger(), 'isEnabledFor', return_value=True), \
                patch.object(logging, 'debug'), \
                patch.object(type(self.driver), 'page_source', new_callable=PropertyMock,
                             create=True, return_value='<html/>') as source:
            service._evil_logic(self.req, self.driver, 'GET')
        source.assert_called_once()

    def test_http_get_contract_and_ephemeral_browser_cleanup(self):
        with patch.object(utils, 'get_webdriver', return_value=self.driver):
            response = TestApp(flaresolverr.app).post_json('/v1', {
                'cmd': 'request.get', 'url': self.req.url,
            })
        self.assertEqual('ok', response.json['status'])
        self.assertEqual('Challenge not detected!', response.json['message'])
        self.assertEqual(self.driver.page_source, response.json['solution']['response'])
        self.assertEqual(200, response.json['solution']['status'])
        self.assertEqual({}, response.json['solution']['headers'])
        self.assertNotIn('__error_500__', response.json)
        self.assertGreaterEqual(response.json['endTimestamp'], response.json['startTimestamp'])
        self.driver.quit.assert_called_once()

    def test_http_error_contract(self):
        response = TestApp(flaresolverr.app).post_json('/v1', {'cmd': 'unknown'}, status=500)
        self.assertEqual('error', response.json['status'])
        self.assertEqual("Error: Request parameter 'cmd' = 'unknown' is invalid.",
                         response.json['message'])


if __name__ == '__main__':
    unittest.main()
