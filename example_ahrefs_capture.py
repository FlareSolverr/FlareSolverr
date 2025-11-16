#!/usr/bin/env python3
"""
Example script to use FlareSolverr with Ahrefs traffic checker
and capture API responses automatically.

This demonstrates how to:
1. Send a request to FlareSolverr
2. Let it solve the captcha on Ahrefs
3. Automatically capture the API response that the page makes
4. Save it to a text file
"""

import requests
import json
import time

# FlareSolverr endpoint (default: http://localhost:8191)
FLARESOLVERR_URL = "http://localhost:8191/v1"

# Target Ahrefs URL
AHREFS_URL = "https://ahrefs.com/traffic-checker/?input=yep.com&mode=subdomains"


def capture_ahrefs_traffic(domain: str = "yep.com", mode: str = "subdomains"):
    """
    Capture Ahrefs traffic data by solving captcha and intercepting API calls

    Args:
        domain: Domain to check traffic for
        mode: Mode (subdomains, prefix, exact)

    Returns:
        Response from FlareSolverr
    """
    url = f"https://ahrefs.com/traffic-checker/?input={domain}&mode={mode}"

    # Prepare the request to FlareSolverr
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000,  # 60 seconds timeout
        "returnOnlyCookies": False
    }

    print(f"[*] Sending request to FlareSolverr...")
    print(f"[*] Target URL: {url}")
    print(f"[*] FlareSolverr will solve any captchas and capture API responses...")

    try:
        response = requests.post(FLARESOLVERR_URL, json=payload)
        response.raise_for_status()

        result = response.json()

        if result.get("status") == "ok":
            print(f"\n[✓] Success!")
            print(f"[✓] Challenge status: {result.get('message')}")
            print(f"\n[*] API responses have been saved to 'captured_responses/' directory")
            print(f"[*] Check the logs above for the exact file paths")

            return result
        else:
            print(f"\n[✗] Error: {result.get('message')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"\n[✗] Request failed: {e}")
        return None


def main():
    print("=" * 80)
    print("Ahrefs Traffic Capture Example")
    print("=" * 80)
    print()

    # Example 1: Check traffic for yep.com with subdomains
    print("Example 1: Checking traffic for yep.com (subdomains mode)")
    print("-" * 80)
    capture_ahrefs_traffic("yep.com", "subdomains")

    print("\n" + "=" * 80)
    print("Done! Check the 'captured_responses/' directory for saved API responses.")
    print("=" * 80)


if __name__ == "__main__":
    main()
