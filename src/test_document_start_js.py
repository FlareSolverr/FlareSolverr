import unittest
from unittest.mock import Mock, patch

from dtos import V1RequestBase
from flaresolverr_service import (
    _evil_logic,
    _install_document_start_js,
    _remove_document_start_js,
    _resolve_challenge,
)
from func_timeout import FunctionTimedOut


class DocumentStartJsTests(unittest.TestCase):

    def test_registers_script_before_navigation(self):
        request = V1RequestBase({"documentStartJs": "window.blockAds = true;"})
        driver = Mock()
        driver.execute_cdp_cmd.return_value = {"identifier": "script-1"}

        result = _install_document_start_js(request, driver)

        self.assertEqual("script-1", result)
        driver.execute_cdp_cmd.assert_called_once_with(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "window.blockAds = true;"},
        )

    def test_skips_registration_without_script(self):
        request = V1RequestBase({})
        driver = Mock()

        result = _install_document_start_js(request, driver)

        self.assertIsNone(result)
        driver.execute_cdp_cmd.assert_not_called()

    def test_post_registration_skips_internal_data_document(self):
        request = V1RequestBase({"documentStartJs": "window.blockAds = true;"})
        driver = Mock()
        driver.execute_cdp_cmd.return_value = {"identifier": "script-1"}

        result = _install_document_start_js(
            request,
            driver,
            skip_data_documents=True,
        )

        self.assertEqual("script-1", result)
        driver.execute_cdp_cmd.assert_called_once_with(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "if (window.location.protocol !== 'data:') {\n"
                    "window.blockAds = true;\n"
                    "}"
                )
            },
        )

    def test_registration_failure_is_fatal(self):
        request = V1RequestBase({"documentStartJs": "window.blockAds = true;"})
        driver = Mock()
        driver.execute_cdp_cmd.side_effect = RuntimeError("synthetic failure")

        with self.assertRaisesRegex(
            Exception, "documentStartJs installation failed: synthetic failure"
        ):
            _install_document_start_js(request, driver)

    def test_removes_registered_script(self):
        driver = Mock()

        _remove_document_start_js(driver, "script-1")

        driver.execute_cdp_cmd.assert_called_once_with(
            "Page.removeScriptToEvaluateOnNewDocument",
            {"identifier": "script-1"},
        )

    def test_request_cleanup_runs_after_navigation_failure(self):
        request = V1RequestBase({"documentStartJs": "window.blockAds = true;"})
        driver = Mock()
        driver.execute_cdp_cmd.return_value = {"identifier": "script-1"}
        driver.get.side_effect = RuntimeError("synthetic navigation failure")

        with self.assertRaisesRegex(RuntimeError, "synthetic navigation failure"):
            _evil_logic(request, driver, "GET")

        self.assertEqual(
            [
                (
                    "Page.addScriptToEvaluateOnNewDocument",
                    {"source": "window.blockAds = true;"},
                ),
                (
                    "Page.removeScriptToEvaluateOnNewDocument",
                    {"identifier": "script-1"},
                ),
            ],
            [call.args for call in driver.execute_cdp_cmd.call_args_list],
        )

    @patch("flaresolverr_service.SESSIONS_STORAGE")
    @patch("flaresolverr_service.func_timeout", side_effect=FunctionTimedOut())
    def test_timeout_destroys_retained_session_before_reuse(
        self,
        timed_request,
        sessions_storage,
    ):
        request = V1RequestBase(
            {
                "documentStartJs": "window.blockAds = true;",
                "maxTimeout": 1000,
                "session": "retained-session",
            }
        )
        driver = Mock()
        driver.execute_cdp_cmd.return_value = {"identifier": "script-1"}
        sessions_storage.get.return_value = (Mock(driver=driver), False)

        with self.assertRaisesRegex(
            Exception,
            "Error solving the challenge. Timeout after 1.0 seconds.",
        ):
            _resolve_challenge(request, "GET")

        timed_request.assert_called_once()
        sessions_storage.destroy.assert_called_once_with("retained-session")
        driver.execute_cdp_cmd.assert_called_once_with(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "window.blockAds = true;"},
        )

    @patch("flaresolverr_service.utils.get_webdriver")
    @patch("flaresolverr_service.func_timeout", return_value=Mock())
    def test_cleanup_failure_still_destroys_stateless_driver(
        self,
        timed_request,
        get_webdriver,
    ):
        request = V1RequestBase(
            {
                "documentStartJs": "window.blockAds = true;",
                "maxTimeout": 1000,
            }
        )
        driver = Mock()
        driver.execute_cdp_cmd.side_effect = [
            {"identifier": "script-1"},
            RuntimeError("synthetic cleanup failure"),
        ]
        get_webdriver.return_value = driver

        with self.assertRaisesRegex(
            Exception,
            "documentStartJs cleanup failed: synthetic cleanup failure",
        ):
            _resolve_challenge(request, "GET")

        timed_request.assert_called_once()
        driver.quit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
