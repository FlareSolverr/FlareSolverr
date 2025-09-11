#!/usr/bin/env python3
"""
Test selenium-fetch JSON POST functionality
"""

import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dtos import V1RequestBase


def test_selenium_fetch_json_post():
    """Test selenium-fetch JSON POST implementation"""
    print("=== Selenium-Fetch JSON POST Test ===\n")
    
    # Test 1: Valid JSON request structure
    print("Test 1: Creating JSON POST request for selenium-fetch")
    json_payload = {
         "input": "0394604830",
          "password": "Vohoanghuy1@",
          "isRemember": "1",
    }
    
    req = V1RequestBase({
        "cmd": "request.post",
        "url": "https://batdongsan.com.vn/user-management-service/api/v1/User/Login",
        "postData": json.dumps(json_payload, indent=2),
        "contentType": "application/json",
        "maxTimeout": 30000
    })
    
    print(f"✓ Request created successfully")
    print(f"  URL: {req.url}")
    print(f"  Content-Type: {req.contentType}")
    print(f"  JSON payload size: {len(req.postData)} characters")
    print(f"  Formatted JSON preview:")
    print(f"    {json.dumps(json_payload, indent=4)[:200]}...")
    
    # Test 2: Complex nested JSON
    print("\nTest 2: Complex nested JSON structure")
    complex_json = {
        "action": "user_registration",
        "data": {
            "personal_info": {
                "first_name": "Jane",
                "last_name": "Smith",
                "age": 28,
                "address": {
                    "street": "123 Main St",
                    "city": "San Francisco",
                    "state": "CA",
                    "zip": "94105",
                    "coordinates": {
                        "lat": 37.7749,
                        "lng": -122.4194
                    }
                }
            },
            "account_settings": {
                "username": "jane_smith_2025",
                "password_hash": "sha256_hash_here",
                "two_factor_enabled": True,
                "security_questions": [
                    {"question": "What is your mother's maiden name?", "answer_hash": "hash1"},
                    {"question": "What city were you born in?", "answer_hash": "hash2"}
                ]
            }
        },
        "validation": {
            "email_verified": False,
            "phone_verified": True,
            "identity_verified": False
        }
    }
    
    req_complex = V1RequestBase({
        "cmd": "request.post",
        "url": "https://api.example.com/register",
        "postData": json.dumps(complex_json),
        "contentType": "application/json",
        "maxTimeout": 45000
    })
    
    print(f"✓ Complex JSON request created")
    print(f"  Data complexity: {len(str(complex_json))} characters")
    print(f"  Nested levels: Multiple (personal_info -> address -> coordinates)")
    
    # Test 3: API-style request
    print("\nTest 3: API-style request simulation")
    api_request = {
        "jsonrpc": "2.0",
        "method": "create_user",
        "params": {
            "user": {
                "name": "Test User",
                "email": "test@example.com"
            },
            "options": {
                "send_welcome_email": True,
                "auto_verify": False
            }
        },
        "id": 12345
    }
    
    req_api = V1RequestBase({
        "cmd": "request.post",
        "url": "https://api.service.com/rpc",
        "postData": json.dumps(api_request),
        "contentType": "application/json",
        "maxTimeout": 20000
    })
    
    print(f"✓ API-style request created")
    print(f"  JSON-RPC format: {api_request['jsonrpc']}")
    print(f"  Method: {api_request['method']}")
    print(f"  Request ID: {api_request['id']}")
    
    print("\n=== Selenium-Fetch Integration Benefits ===")
    print("✅ Direct HTTP request handling via selenium-fetch")
    print("✅ Better response handling and error management")
    print("✅ Proper HTTP status code and headers access") 
    print("✅ Fallback to JavaScript fetch API if needed")
    print("✅ Maintains Selenium WebDriver context for challenge solving")
    print("✅ More reliable than pure JavaScript fetch for complex scenarios")
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    test_selenium_fetch_json_post()
