import threading
import time
import unittest
from unittest import mock

from dtos import V1RequestBase
import flaresolverr_service
from sessions import SessionsStorage


def _slow_get_webdriver(proxy=None):
    time.sleep(0.2)
    return mock.MagicMock()


def _run_concurrently(target, args_list):
    threads = [threading.Thread(target=target, args=args) for args in args_list]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


class TestSessions(unittest.TestCase):

    @mock.patch('sessions.utils.get_webdriver', side_effect=_slow_get_webdriver)
    def test_concurrent_create_same_session_id(self, get_webdriver):
        storage = SessionsStorage()
        _run_concurrently(storage.create, [('test',)] * 3)

        self.assertEqual(get_webdriver.call_count, 1)
        self.assertEqual(storage.session_ids(), ['test'])

    @mock.patch('sessions.utils.get_webdriver', side_effect=_slow_get_webdriver)
    def test_concurrent_requests_same_session_are_serialized(self, _):
        active = 0
        max_active = 0
        counter_lock = threading.Lock()

        def fake_evil_logic(req, driver, method):
            nonlocal active, max_active
            with counter_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.2)
            with counter_lock:
                active -= 1

        storage = SessionsStorage()
        with mock.patch.object(flaresolverr_service, 'SESSIONS_STORAGE', storage), \
                mock.patch.object(flaresolverr_service, '_evil_logic', side_effect=fake_evil_logic):
            reqs = [V1RequestBase({'cmd': 'request.get', 'url': f'https://example.com/?v={i}',
                                   'session': 'test', 'maxTimeout': 60000}) for i in range(3)]
            _run_concurrently(flaresolverr_service._resolve_challenge, [(r, 'GET') for r in reqs])

        self.assertEqual(max_active, 1)


if __name__ == '__main__':
    unittest.main()
