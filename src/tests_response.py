import json
import unittest

from selenium.common import WebDriverException

import utils

MAIN_FRAME = "MAIN"
CHILD_FRAME = "CHILD"


def _entry(method: str, **params) -> dict:
    message = {"message": {"method": method, "params": params}, "webview": "TARGET"}
    return {"level": "INFO", "message": json.dumps(message), "timestamp": 0}


def _frame_navigated(frame_id: str, parent_id: str = None) -> dict:
    frame = {"id": frame_id, "url": "https://example.com/"}
    if parent_id is not None:
        frame["parentId"] = parent_id
    return _entry("Page.frameNavigated", frame=frame)


def _response_received(frame_id: str, status: int, resource_type: str = "Document", headers: dict = None) -> dict:
    return _entry("Network.responseReceived", frameId=frame_id, type=resource_type,
                  response={"status": status, "headers": headers or {}})


class TestParseMainResponse(unittest.TestCase):

    def test_status_and_headers_of_main_document(self):
        entries = [
            _frame_navigated(MAIN_FRAME),
            _response_received(MAIN_FRAME, 404, headers={"content-type": "text/html"}),
        ]
        self.assertEqual((404, {"content-type": "text/html"}), utils.parse_main_response(entries))

    def test_last_main_document_wins(self):
        entries = [
            _frame_navigated(MAIN_FRAME),
            _response_received(MAIN_FRAME, 403, headers={"cf-mitigated": "challenge"}),
            _response_received(MAIN_FRAME, 200, headers={"server": "cloudflare"}),
        ]
        self.assertEqual((200, {"server": "cloudflare"}), utils.parse_main_response(entries))

    def test_redirect_reports_final_response(self):
        entries = [
            _frame_navigated(MAIN_FRAME),
            _entry("Network.requestWillBeSent", frameId=MAIN_FRAME, type="Document",
                   redirectResponse={"status": 301, "headers": {"location": "/final"}}),
            _response_received(MAIN_FRAME, 200),
        ]
        self.assertEqual((200, {}), utils.parse_main_response(entries))

    def test_ignores_child_frames_and_subresources(self):
        entries = [
            _frame_navigated(MAIN_FRAME),
            _frame_navigated(CHILD_FRAME, parent_id=MAIN_FRAME),
            _response_received(MAIN_FRAME, 404),
            _response_received(CHILD_FRAME, 200),
            _response_received(MAIN_FRAME, 200, resource_type="Script"),
        ]
        self.assertEqual((404, {}), utils.parse_main_response(entries))

    def test_skips_malformed_entries(self):
        entries = [
            {"level": "INFO", "message": "not json", "timestamp": 0},
            _frame_navigated(MAIN_FRAME),
            _response_received(MAIN_FRAME, 500),
        ]
        self.assertEqual((500, {}), utils.parse_main_response(entries))

    def test_none_without_main_document(self):
        self.assertIsNone(utils.parse_main_response([]))
        self.assertIsNone(utils.parse_main_response([_frame_navigated(MAIN_FRAME)]))
        self.assertIsNone(utils.parse_main_response([_response_received(MAIN_FRAME, 200)]))


class TestGetPerformanceLog(unittest.TestCase):

    def test_empty_when_log_is_not_available(self):
        class Driver:
            def get_log(self, log_type):
                raise WebDriverException("log type 'performance' not found")

        self.assertEqual([], utils.get_performance_log(Driver()))


if __name__ == "__main__":
    unittest.main()
