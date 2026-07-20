import json
import shutil
import threading
import time
import unittest
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import unquote

import flaresolverr_service
import utils
from dtos import V1RequestBase
from sessions import SessionsStorage


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.action = attrs['action']
        if tag == 'input':
            self.inputs.append((attrs['name'], attrs['value']))


class FakeDriver:
    def __init__(self):
        self.url = None

    def get(self, url):
        self.url = url


class TestPostRequestEncoding(unittest.TestCase):
    def test_post_data_is_decoded_once_before_browser_form_submission(self):
        driver = FakeDriver()
        request = V1RequestBase({
            'url': 'https://example.test/form?source=FlareSolverr',
            'postData': 'space=hello+world&encoded=one%26two&empty=&submit=ignored',
        })

        flaresolverr_service._post_request(request, driver)

        self.assertTrue(driver.url.startswith('data:text/html;charset=utf-8,'))
        parser = FormParser()
        parser.feed(unquote(driver.url.split(',', 1)[1]))
        self.assertEqual('https://example.test/form?source=FlareSolverr', parser.action)
        self.assertEqual(
            [('space', 'hello world'), ('encoded', 'one&two'), ('empty', '')],
            parser.inputs,
        )

    def test_request_post_requires_a_url_before_creating_a_browser(self):
        request = V1RequestBase({'cmd': 'request.post', 'postData': 'one=two'})

        with patch('flaresolverr_service._resolve_challenge') as resolve_challenge:
            with self.assertRaisesRegex(Exception, "Request parameter 'url' is mandatory"):
                flaresolverr_service._cmd_request_post(request)
            resolve_challenge.assert_not_called()


class TestProxyExtension(unittest.TestCase):
    def test_credentials_with_quotes_create_valid_json_in_the_extension(self):
        username = 'user"; globalThis.injected = true; //'
        password = 'pass"; globalThis.injected = true; //'
        directory = utils.create_proxy_extension({
            'url': 'http://127.0.0.1:8080',
            'username': username,
            'password': password,
        })
        self.addCleanup(shutil.rmtree, directory)

        with open(f'{directory}/background.js', encoding='utf-8') as extension_file:
            extension = extension_file.read()

        self.assertIn(json.dumps({'username': username, 'password': password}), extension)
        self.assertNotIn(f'username: "{username}"', extension)


class TestSessionStorageConcurrency(unittest.TestCase):
    def test_simultaneous_create_with_one_id_starts_only_one_driver(self):
        storage = SessionsStorage()
        start = threading.Barrier(3)
        drivers = []

        def create_driver(_proxy):
            time.sleep(0.1)
            driver = object()
            drivers.append(driver)
            return driver

        def create_session():
            start.wait()
            return storage.create('same-session')

        with patch('sessions.utils.get_webdriver', side_effect=create_driver):
            first = threading.Thread(target=create_session)
            second = threading.Thread(target=create_session)
            first.start()
            second.start()
            start.wait()
            first.join()
            second.join()

        self.assertEqual(1, len(drivers))
        self.assertEqual(['same-session'], storage.session_ids())


class TestSensitiveLogging(unittest.TestCase):
    def test_sensitive_api_data_is_removed_before_logging(self):
        data = {
            'proxy': {'url': 'http://proxy.test', 'password': 'proxy-secret'},
            'cookies': [{'name': 'session', 'value': 'cookie-secret'}],
            'headers': {'Authorization': 'header-secret'},
            'postData': 'password=form-secret',
            'solution': {'response': 'response-secret', 'screenshot': 'image-secret'},
        }

        safe_data = utils.redact_sensitive_data(data)

        self.assertNotIn('proxy-secret', repr(safe_data))
        self.assertNotIn('cookie-secret', repr(safe_data))
        self.assertNotIn('header-secret', repr(safe_data))
        self.assertNotIn('form-secret', repr(safe_data))
        self.assertNotIn('response-secret', repr(safe_data))
        self.assertNotIn('image-secret', repr(safe_data))
        self.assertEqual('[REDACTED]', safe_data['proxy'])


if __name__ == '__main__':
    unittest.main()
