import logging
import random
import time

from selenium.webdriver.chrome.webdriver import WebDriver

TURNSTILE_IFRAME_SRC = "challenges.cloudflare.com"


def _find_turnstile_iframes(node: dict, found: list):
    # DOM.getDocument with pierce=True includes closed shadow roots, where Turnstile hides its iframe
    if node.get("nodeName") == "IFRAME":
        attrs = node.get("attributes", [])
        src = dict(zip(attrs[::2], attrs[1::2])).get("src", "")
        if TURNSTILE_IFRAME_SRC in src:
            found.append(node["backendNodeId"])
    for key in ("children", "shadowRoots"):
        for child in node.get(key, []):
            _find_turnstile_iframes(child, found)
    if "contentDocument" in node:
        _find_turnstile_iframes(node["contentDocument"], found)


def _turnstile_iframes(driver: WebDriver) -> list:
    doc = driver.execute_cdp_cmd("DOM.getDocument", {"depth": -1, "pierce": True})
    iframes = []
    _find_turnstile_iframes(doc["root"], iframes)
    return iframes


def _iframe_rect(driver: WebDriver, backend_node_id: int):
    """Returns (x0, y0, x1, y1) in viewport CSS pixels, or None if the iframe is not visible."""
    try:
        quads = driver.execute_cdp_cmd("DOM.getContentQuads", {"backendNodeId": backend_node_id})["quads"]
    except Exception:
        return None
    if not quads:
        return None
    xs, ys = quads[0][0::2], quads[0][1::2]
    rect = (min(xs), min(ys), max(xs), max(ys))
    if rect[2] - rect[0] < 100 or rect[3] - rect[1] < 40:
        # not rendered yet, or an invisible (non-interactive) widget
        return None
    return rect


def _visible_turnstile_rect(driver: WebDriver):
    for backend_node_id in _turnstile_iframes(driver):
        try:
            driver.execute_cdp_cmd("DOM.scrollIntoViewIfNeeded", {"backendNodeId": backend_node_id})
        except Exception:
            pass
        rect = _iframe_rect(driver, backend_node_id)
        if rect:
            return backend_node_id, rect
    return None, None


def _checkbox_position(rect: tuple) -> tuple:
    x0, y0, x1, y1 = rect
    if x1 - x0 < 200:
        # compact widget (150x140): checkbox in the upper part
        x, y = x0 + 30, y0 + 35
    else:
        # normal widget (300x65): checkbox on the left, vertically centered
        x, y = x0 + 30, (y0 + y1) / 2
    return x + random.uniform(-3, 3), y + random.uniform(-3, 3)


def _mouse_event(driver: WebDriver, event_type: str, x: float, y: float):
    driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
        "type": event_type, "x": x, "y": y, "button": "left", "clickCount": 1
    })


def _human_click(driver: WebDriver, x: float, y: float):
    # approach the checkbox along a short path, like a real cursor
    start_x, start_y = x - random.uniform(60, 120), y + random.uniform(-30, 30)
    steps = random.randint(6, 10)
    for i in range(1, steps + 1):
        t = i / steps
        _mouse_event(driver, "mouseMoved",
                     start_x + (x - start_x) * t + random.uniform(-1.5, 1.5),
                     start_y + (y - start_y) * t + random.uniform(-1.5, 1.5))
        time.sleep(random.uniform(0.01, 0.04))
    time.sleep(random.uniform(0.08, 0.2))
    _mouse_event(driver, "mousePressed", x, y)
    time.sleep(random.uniform(0.05, 0.12))
    _mouse_event(driver, "mouseReleased", x, y)


def get_turnstile_response(driver: WebDriver):
    """Returns the current Turnstile token (from the JS API or any response input), or None."""
    try:
        return driver.execute_script("""
            try {
                if (window.turnstile && typeof window.turnstile.getResponse === 'function') {
                    const r = window.turnstile.getResponse();
                    if (r) return r;
                }
            } catch (e) {}
            for (const el of document.querySelectorAll("input[name='cf-turnstile-response']")) {
                if (el.value) return el.value;
            }
            return null;
        """)
    except Exception:
        return None


def reset_turnstile(driver: WebDriver) -> bool:
    """Asks the Turnstile JS API for a fresh challenge (needed when the widget ended in an error state)."""
    try:
        return bool(driver.execute_script("""
            if (window.turnstile && typeof window.turnstile.reset === 'function') {
                window.turnstile.reset();
                return true;
            }
            return false;
        """))
    except Exception:
        return False


def wait_for_turnstile(driver: WebDriver, timeout: float) -> bool:
    """Waits until a Turnstile iframe is present in the page (shadow roots included)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if _turnstile_iframes(driver):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def click_turnstile(driver: WebDriver, ready_timeout: float = 10) -> bool:
    """
    Clicks the Cloudflare Turnstile checkbox with real (trusted) mouse events sent through CDP.
    Waits until the widget is rendered and its position is stable before clicking.
    Returns True if a Turnstile checkbox was clicked.
    """
    deadline = time.time() + ready_timeout
    previous_rect = None
    try:
        while time.time() < deadline:
            backend_node_id, rect = _visible_turnstile_rect(driver)
            if rect and previous_rect and max(abs(a - b) for a, b in zip(rect, previous_rect)) < 1:
                # the widget shows a spinner while it loads, give it time to show the checkbox
                time.sleep(random.uniform(1.0, 2.0))
                rect = _iframe_rect(driver, backend_node_id) or rect
                x, y = _checkbox_position(rect)
                _human_click(driver, x, y)
                logging.debug(f"Turnstile checkbox clicked at ({x:.0f}, {y:.0f})")
                return True
            previous_rect = rect
            time.sleep(0.4)
        logging.debug("Turnstile widget not visible or not stable")
    except Exception as e:
        logging.debug(f"Turnstile click failed: {e}")
    return False
