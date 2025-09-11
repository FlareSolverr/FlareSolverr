#!/usr/bin/env python3
"""
Simple demonstration of the JSON POST functionality.
This shows how the new contentType parameter works.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dtos import V1RequestBase
import json


def demo_json_post_creation():
    """Demonstrate creating JSON POST requests"""
    print("=== FlareSolverr JSON POST Support Demo ===\n")
    
    # Example 1: JSON POST request
    print("1. Creating a JSON POST request:")
    json_data = {
        "username": "test_user",
        "password": "secret123",
        "remember_me": True,
        "metadata": {
            "client": "web",
            "version": "1.0"
        }
    }
    
    req_json = V1RequestBase({
        "cmd": "request.post",
        "url": "https://api.example.com/login",
        "postData": json.dumps(json_data),
        "contentType": "application/json",
        "maxTimeout": 60000
    })
    
    print(f"   Command: {req_json.cmd}")
    print(f"   URL: {req_json.url}")
    print(f"   Content-Type: {req_json.contentType}")
    print(f"   POST Data: {req_json.postData}")
    print(f"   Timeout: {req_json.maxTimeout}ms")
    
    # Example 2: Traditional form-encoded POST (still supported)
    print("\n2. Creating a form-encoded POST request (traditional):")
    req_form = V1RequestBase({
        "cmd": "request.post",
        "url": "https://example.com/submit",
        "postData": "username=test_user&password=secret123&remember_me=true",
        "maxTimeout": 30000
    })
    
    print(f"   Command: {req_form.cmd}")
    print(f"   URL: {req_form.url}")
    print(f"   Content-Type: {req_form.contentType or 'application/x-www-form-urlencoded (default)'}")
    print(f"   POST Data: {req_form.postData}")
    print(f"   Timeout: {req_form.maxTimeout}ms")
    
    # Example 3: Explicitly specifying form content type
    print("\n3. Creating a form-encoded POST with explicit content type:")
    req_form_explicit = V1RequestBase({
        "cmd": "request.post", 
        "url": "https://example.com/contact",
        "postData": "name=John+Doe&email=john%40example.com&message=Hello",
        "contentType": "application/x-www-form-urlencoded",
        "maxTimeout": 45000
    })
    
    print(f"   Command: {req_form_explicit.cmd}")
    print(f"   URL: {req_form_explicit.url}")
    print(f"   Content-Type: {req_form_explicit.contentType}")
    print(f"   POST Data: {req_form_explicit.postData}")
    print(f"   Timeout: {req_form_explicit.maxTimeout}ms")
    
    print("\n=== Demo Complete ===")
    print("\nKey Features Added:")
    print("• Support for 'application/json' content type in POST requests")
    print("• Backward compatibility with existing form-encoded requests")
    print("• JSON data validation to ensure valid JSON format")
    print("• Proper JavaScript escaping for safe JSON handling in the browser")
    print("• Enhanced error handling for invalid JSON data")


if __name__ == "__main__":
    demo_json_post_creation()
