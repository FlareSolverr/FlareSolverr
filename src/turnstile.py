"""Locate a rendered Cloudflare Turnstile checkbox through Chrome DevTools."""

import json
import logging
import math
from urllib.parse import urlparse

import requests
from websockets.sync.client import connect


_TURNSTILE_HOST = "challenges.cloudflare.com"
_TURNSTILE_PATH = "/cdn-cgi/challenge-platform/"


def _walk_nodes(node):
    yield node
    for key in ("children", "shadowRoots"):
        for child in node.get(key) or ():
            yield from _walk_nodes(child)
    content_document = node.get("contentDocument")
    if content_document:
        yield from _walk_nodes(content_document)


def _attributes(node):
    values = node.get("attributes") or []
    return dict(zip(values[::2], values[1::2]))


def _valid_quad(quad):
    if not isinstance(quad, list) or len(quad) != 8:
        return False
    try:
        return all(math.isfinite(float(value)) for value in quad)
    except (TypeError, ValueError):
        return False


def _box_center(box_model):
    quad = (box_model or {}).get("model", {}).get("content")
    if not _valid_quad(quad):
        return None
    xs = [float(quad[i]) for i in (0, 2, 4, 6)]
    ys = [float(quad[i]) for i in (1, 3, 5, 7)]
    if max(xs) <= min(xs) or max(ys) <= min(ys):
        return None
    return (sum(xs) / 4, sum(ys) / 4)


def _cdp(ws, command_id, method, params=None):
    ws.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
    while True:
        response = json.loads(ws.recv(timeout=2))
        if response.get("id") == command_id:
            if "error" in response:
                raise RuntimeError(response["error"].get("message", "CDP command failed"))
            return response.get("result", {})


def locate_turnstile(driver):
    """Return None if absent, False if present but not ready, or click coordinates."""
    root = driver.execute_cdp_cmd("DOM.getDocument", {"depth": -1, "pierce": True})
    document = root.get("root") or {}
    nodes = list(_walk_nodes(document))
    response_input = any(
        node.get("nodeName", "").upper() == "INPUT"
        and _attributes(node).get("name") == "cf-turnstile-response"
        for node in nodes
    )

    frames = []
    for node in nodes:
        if node.get("nodeName", "").upper() != "IFRAME":
            continue
        src = _attributes(node).get("src", "")
        parsed = urlparse(src)
        if parsed.hostname != _TURNSTILE_HOST or not parsed.path.startswith(_TURNSTILE_PATH):
            continue
        frames.append((node, node.get("frameId") or (node.get("contentDocument") or {}).get("frameId")))

    if not response_input and not frames:
        return None
    if not frames:
        return False

    frame_node, frame_id = frames[0]
    if not frame_id:
        return False

    parent_node_key = "backendNodeId" if frame_node.get("backendNodeId") else "nodeId"
    try:
        parent_box = driver.execute_cdp_cmd("DOM.getBoxModel", {parent_node_key: frame_node[parent_node_key]})
    except Exception as error:
        logging.debug("Turnstile iframe geometry pending: %s", error)
        return False
    parent_content = (parent_box.get("model") or {}).get("content")
    if not _valid_quad(parent_content):
        return False

    debugger_address = (
        driver.capabilities.get("goog:chromeOptions", {}).get("debuggerAddress")
        or driver.capabilities.get("chrome", {}).get("debuggerAddress")
    )
    if not debugger_address:
        raise RuntimeError("Chrome debugger address unavailable")

    try:
        response = requests.get("http://{}/json/list".format(debugger_address), timeout=1)
        response.raise_for_status()
        target = next((item for item in response.json() if item.get("id") == frame_id), None)
        if not target or not target.get("webSocketDebuggerUrl"):
            return False

        with connect(target["webSocketDebuggerUrl"], open_timeout=1, close_timeout=1) as ws:
            frame_doc = _cdp(ws, 1, "DOM.getDocument", {"depth": -1, "pierce": True}).get("root") or {}
            checkboxes = [
                node for node in _walk_nodes(frame_doc)
                if node.get("nodeName", "").upper() == "INPUT"
                and _attributes(node).get("type", "").lower() == "checkbox"
            ]
            if not checkboxes:
                return False

            checkbox = checkboxes[0]
            checkbox_node_key = "backendNodeId" if checkbox.get("backendNodeId") else "nodeId"
            checkbox_node_id = checkbox[checkbox_node_key]
            box = _cdp(ws, 2, "DOM.getBoxModel", {checkbox_node_key: checkbox_node_id})
            inner_center = _box_center(box)
            if inner_center is None:
                return False
            resolved = _cdp(ws, 3, "DOM.resolveNode", {checkbox_node_key: checkbox_node_id})
            object_id = (resolved.get("object") or {}).get("objectId")
            if not object_id:
                return False
            state = _cdp(ws, 4, "Runtime.callFunctionOn", {
                "objectId": object_id,
                "functionDeclaration": "function(){return {checked:!!this.checked,disabled:!!this.disabled}}",
                "returnByValue": True,
            }).get("result", {}).get("value") or {}
            if state.get("checked") or state.get("disabled"):
                return False
    except Exception as error:
        logging.debug("Turnstile frame lookup pending: %s", error)
        return False

    # Both CDP quads use viewport CSS pixels at the configured scale factor of 1.
    x = float(parent_content[0]) + inner_center[0]
    y = float(parent_content[1]) + inner_center[1]
    if not math.isfinite(x) or not math.isfinite(y):
        return False
    logging.debug("Turnstile checkbox located through its matching CDP frame")
    return x, y
