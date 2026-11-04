import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from types import SimpleNamespace
from unittest.mock import patch

import flaresolverr_service as service


class SolveConcurrencyTests(unittest.TestCase):
    def test_four_callers_share_two_browser_slots_and_keep_timeout(self):
        slots = BoundedSemaphore(2)
        barrier = threading.Barrier(4)
        two_handlers_started = threading.Event()
        third_handler_started = threading.Event()
        release_handlers = threading.Event()
        lock = threading.Lock()
        active = 0
        maximum_active = 0
        calls = 0
        seen_requests = []
        request = SimpleNamespace(maxTimeout=23456)

        def browser_handler(req, method):
            nonlocal active, maximum_active, calls
            with lock:
                calls += 1
                active += 1
                maximum_active = max(maximum_active, active)
                call_number = calls
                seen_requests.append((req, req.maxTimeout, method))
                if call_number == 2:
                    two_handlers_started.set()
                elif call_number == 3:
                    third_handler_started.set()
            try:
                if not release_handlers.wait(2):
                    raise TimeoutError("test release event timed out")
                return "finished"
            finally:
                with lock:
                    active -= 1

        def queued_request():
            barrier.wait(timeout=1)
            return service._resolve_challenge(request, "GET")

        with patch.object(service, "_SOLVE_SLOTS", slots), patch.object(
            service, "_resolve_challenge_in_browser", side_effect=browser_handler
        ):
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(queued_request) for _ in range(4)]
                try:
                    self.assertTrue(two_handlers_started.wait(1))
                    self.assertFalse(third_handler_started.wait(0.1))
                    with lock:
                        self.assertEqual(2, active)
                        self.assertLessEqual(maximum_active, 2)
                finally:
                    release_handlers.set()
                self.assertEqual(["finished"] * 4, [future.result(timeout=1) for future in futures])

        self.assertEqual(4, len(seen_requests))
        self.assertTrue(all(req is request for req, _timeout, _method in seen_requests))
        self.assertEqual({23456}, {timeout for _req, timeout, _method in seen_requests})
        self.assertEqual({"GET"}, {method for _req, _timeout, method in seen_requests})
        self.assertLessEqual(maximum_active, 2)
        self.assertEqual(0, active)

    def test_handler_exception_releases_browser_slot(self):
        request = SimpleNamespace(maxTimeout=12345)
        calls = 0

        def browser_handler(req, method):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("synthetic browser failure")
            return "finished"

        slots = BoundedSemaphore(1)
        with patch.object(service, "_SOLVE_SLOTS", slots), patch.object(
            service, "_resolve_challenge_in_browser", side_effect=browser_handler
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic browser failure"):
                service._resolve_challenge(request, "GET")
            self.assertTrue(slots.acquire(blocking=False), "failed request leaked its browser slot")
            slots.release()
            self.assertEqual("finished", service._resolve_challenge(request, "GET"))

        self.assertEqual(2, calls)
        self.assertEqual(12345, request.maxTimeout)


if __name__ == "__main__":
    unittest.main()
