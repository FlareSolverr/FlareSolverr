import unittest
from unittest.mock import MagicMock, patch

import flaresolverr_service as service
from flaresolverr_service import click_verify
from turnstile import locate_turnstile
import turnstile


def _attrs(**values):
    return [item for pair in values.items() for item in pair]


def _iframe(frame_id="frame-a", src="https://challenge.example.test/cdn-cgi/challenge-platform/widget"):
    return {
        "nodeName": "IFRAME",
        "nodeId": 10,
        "frameId": frame_id,
        "attributes": _attrs(src=src),
    }


class TurnstileTests(unittest.TestCase):
    def setUp(self):
        host = patch.object(turnstile, "_TURNSTILE_HOST", "challenge.example.test")
        host.start()
        self.addCleanup(host.stop)

    def _driver(self, root):
        driver = MagicMock()
        driver.capabilities = {"goog:chromeOptions": {"debuggerAddress": "127.0.0.1:9222"}}
        driver.execute_cdp_cmd.side_effect = lambda method, params: {
            "DOM.getDocument": {"root": root},
            "DOM.getBoxModel": {"model": {"content": [10, 20, 110, 20, 110, 120, 10, 120]}},
        }[method]
        return driver

    @patch("flaresolverr_service.locate_turnstile", return_value=False)
    @patch("flaresolverr_service.ActionChains")
    def test_pending_widget_skips_legacy_keyboard(self, actions, _locate):
        click_verify(MagicMock(title=service.CHALLENGE_TITLES[0]))
        actions.assert_not_called()

    @patch("flaresolverr_service.locate_turnstile")
    @patch("flaresolverr_service.ActionChains")
    @patch("flaresolverr_service._handle_recaptcha_challenge")
    @patch("flaresolverr_service.time.sleep")
    def test_custom_page_title_keeps_legacy_path(self, _sleep, _recaptcha, actions, locate):
        driver = MagicMock(title="Fixture")
        driver.find_element.side_effect = RuntimeError("no verify button")
        chain = actions.return_value
        chain.pause.return_value = chain
        chain.send_keys.return_value = chain

        click_verify(driver)

        locate.assert_not_called()
        self.assertEqual(2, chain.send_keys.call_count)

    @patch("flaresolverr_service.locate_turnstile", side_effect=RuntimeError("CDP unavailable"))
    @patch("flaresolverr_service.ActionChains")
    @patch("flaresolverr_service._handle_recaptcha_challenge")
    @patch("flaresolverr_service.time.sleep")
    def test_unsupported_cdp_falls_back_to_legacy_path(self, _sleep, _recaptcha, actions, _locate):
        driver = MagicMock(title=service.CHALLENGE_TITLES[0])
        driver.find_element.side_effect = RuntimeError("no verify button")
        chain = actions.return_value
        chain.pause.return_value = chain
        chain.send_keys.return_value = chain

        click_verify(driver)

        self.assertEqual(2, chain.send_keys.call_count)

    @patch("turnstile.connect")
    @patch("turnstile.requests.get")
    @patch("turnstile._cdp")
    def test_finds_checkbox_in_closed_shadow_tree_and_maps_geometry(self, cdp, get, connect):
        checkbox = {"nodeName": "INPUT", "nodeId": 7, "attributes": _attrs(type="checkbox")}
        root = {"nodeName": "#document", "children": [_iframe()]}
        driver = self._driver(root)
        get.return_value.json.return_value = [
            {"id": "other", "webSocketDebuggerUrl": "ws://debugger.example.test/other"},
            {"id": "frame-a", "webSocketDebuggerUrl": "ws://debugger.example.test/frame-a"},
        ]
        cdp.side_effect = [
            {"root": {"nodeName": "#document", "children": [{"nodeName": "DIV", "shadowRoots": [{"nodeName": "#shadow-root", "children": [checkbox]}]}]}},
            {"model": {"content": [5, 8, 15, 8, 15, 18, 5, 18]}},
            {"object": {"objectId": "checkbox-object"}},
            {"result": {"value": {"checked": False, "disabled": False}}},
        ]

        self.assertEqual((20, 33), locate_turnstile(driver))
        connect.assert_called_once_with("ws://debugger.example.test/frame-a", open_timeout=1, close_timeout=1)
        self.assertEqual("http://127.0.0.1:9222/json/list", get.call_args.args[0])

    @patch("turnstile.connect")
    @patch("turnstile.requests.get")
    @patch("turnstile._cdp")
    def test_checked_or_disabled_checkbox_is_not_clicked(self, cdp, get, connect):
        for state in ({"checked": True, "disabled": False}, {"checked": False, "disabled": True}):
            with self.subTest(state=state):
                cdp.reset_mock()
                connect.reset_mock()
                driver = self._driver({"nodeName": "#document", "children": [_iframe()]})
                get.return_value.json.return_value = [{"id": "frame-a", "webSocketDebuggerUrl": "ws://debugger.example.test/frame-a"}]
                cdp.side_effect = [
                    {"root": {"nodeName": "#document", "children": [{"nodeName": "INPUT", "nodeId": 7, "attributes": _attrs(type="checkbox")}]}},
                    {"model": {"content": [5, 8, 15, 8, 15, 18, 5, 18]}},
                    {"object": {"objectId": "checkbox-object"}},
                    {"result": {"value": state}},
                ]
                self.assertIs(locate_turnstile(driver), False)
                self.assertEqual(4, cdp.call_count)
                connect.assert_called_once_with("ws://debugger.example.test/frame-a", open_timeout=1, close_timeout=1)

    def test_exact_frame_id_selects_target_among_multiple_frames(self):
        driver = self._driver({"nodeName": "#document", "children": [_iframe("wanted"), _iframe("other")]})
        with patch("turnstile.requests.get") as get:
            get.return_value.json.return_value = [
                {"id": "other", "webSocketDebuggerUrl": "ws://debugger.example.test/other"},
                {"id": "wanted", "webSocketDebuggerUrl": "ws://debugger.example.test/wanted"},
            ]
            with patch("turnstile.connect") as connect, patch("turnstile._cdp", side_effect=RuntimeError("frame probe")):
                self.assertIs(locate_turnstile(driver), False)
                connect.assert_called_once_with("ws://debugger.example.test/wanted", open_timeout=1, close_timeout=1)

    def test_unrelated_iframe_host_is_not_recognized(self):
        driver = self._driver({"nodeName": "#document", "children": [
            _iframe("other", "https://elsewhere.example.test/cdn-cgi/challenge-platform/widget")
        ]})
        self.assertIsNone(locate_turnstile(driver))

    def test_pending_hidden_response_input_is_recognized_without_iframe(self):
        driver = self._driver({"nodeName": "#document", "children": [
            {"nodeName": "INPUT", "attributes": _attrs(name="cf-turnstile-response")}
        ]})
        self.assertIs(locate_turnstile(driver), False)

    def test_websocket_closes_when_cdp_fails(self):
        driver = self._driver({"nodeName": "#document", "children": [_iframe()]})
        with patch("turnstile.requests.get") as get, patch("turnstile.connect") as connect:
            get.return_value.json.return_value = [{"id": "frame-a", "webSocketDebuggerUrl": "ws://debugger.example.test/frame-a"}]
            context = MagicMock()
            context.__enter__.return_value = MagicMock()
            connect.return_value = context
            with patch("turnstile._cdp", side_effect=RuntimeError("probe failed")):
                self.assertIs(locate_turnstile(driver), False)
            context.__exit__.assert_called_once()

    @patch("flaresolverr_service.locate_turnstile")
    @patch("flaresolverr_service.ActionChains")
    @patch("flaresolverr_service.time.sleep")
    def test_custom_tab_count_keeps_legacy_path(self, _sleep, actions, locate):
        chain = actions.return_value
        chain.pause.return_value = chain
        chain.send_keys.return_value = chain
        click_verify(MagicMock(), num_tabs=2)
        locate.assert_not_called()
        self.assertEqual(3, chain.send_keys.call_count)


if __name__ == "__main__":
    unittest.main()
