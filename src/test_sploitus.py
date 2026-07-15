#!/usr/bin/env python3
"""Quick proof-of-concept: call sploitus via patched FlareSolverr."""

import json
import sys
import time
import urllib.request

FLARESOLVERR_URL = "http://localhost:8191/v1"
SPLOITUS_SEARCH_URL = "https://sploitus.com/search"
SEARCH_QUERY = {"type": "exploits", "query": "log4j", "sort": "default", "title": False, "offset": 0}
MAX_TIMEOUT = 90000


def post(payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        FLARESOLVERR_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def main():
    print("[1] Creating FlareSolverr session...")
    create_resp = post({"cmd": "sessions.create", "maxTimeout": MAX_TIMEOUT})
    if create_resp.get("status") != "ok":
        print("FAIL: sessions.create =>", create_resp)
        sys.exit(1)
    session_id = create_resp["session"]
    print(f"    session_id = {session_id}")

    try:
        print("[2] Sending request.post_json to sploitus...")
        t0 = time.time()
        search_resp = post({
            "cmd": "request.post_json",
            "url": SPLOITUS_SEARCH_URL,
            "jsonBody": json.dumps(SEARCH_QUERY),
            "session": session_id,
            "maxTimeout": MAX_TIMEOUT,
        })
        elapsed = time.time() - t0
        print(f"    completed in {elapsed:.1f}s")

        if search_resp.get("status") != "ok":
            print("FAIL: request.post_json =>", json.dumps(search_resp, indent=2))
            sys.exit(1)

        raw = search_resp["solution"]["response"]
        print(f"[3] Raw envelope from browser: {raw[:300]}")

        envelope = json.loads(raw)
        http_status = envelope["s"]
        body = envelope["b"]
        print(f"[4] HTTP status from fetch: {http_status}")

        if http_status != 200:
            print(f"FAIL: sploitus returned HTTP {http_status}")
            print("Body:", body[:500])
            sys.exit(1)

        result = json.loads(body)
        exploits = result.get("exploits", [])
        total = result.get("search_total", "?")
        print(f"[5] SUCCESS - total results: {total}, first page count: {len(exploits)}")
        if exploits:
            first = exploits[0]
            print(f"    First exploit: {first.get('title', '?')} | score={first.get('score', '?')}")

    finally:
        print("[6] Destroying session...")
        post({"cmd": "sessions.destroy", "session": session_id})
        print("    done.")


if __name__ == "__main__":
    main()
