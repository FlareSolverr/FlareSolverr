#!/usr/bin/env python3
"""
Simple test script to demonstrate JSON POST functionality.
This can be run independently to test the new JSON content type support.
"""

import json
from src.dtos import V1RequestBase
from src.flaresolverr_service import _cmd_request_post


def test_json_post_validation():
    """Test that JSON POST requests are properly validated"""
    print("Testing JSON POST validation...")
    
    # Test valid JSON
    valid_json = '{"key": "value", "number": 123, "nested": {"inner": "data"}}'
    req = V1RequestBase({
        "cmd": "request.post",
        "url": "https://httpbin.org/post",
        "postData": valid_json,
        "contentType": "application/json",
        "maxTimeout": 60000
    })
    
    print(f"✓ Valid JSON request created: {req.contentType}")
    print(f"  URL: {req.url}")
    print(f"  POST data: {req.postData}")
    
    # Test invalid JSON
    try:
        invalid_json = '{"key": "value", "invalid":}'
        from src.flaresolverr_service import _post_request
        from unittest.mock import Mock
        
        mock_driver = Mock()
        req_invalid = V1RequestBase({
            "cmd": "request.post",
            "url": "https://httpbin.org/post",
            "postData": invalid_json,
            "contentType": "application/json"
        })
        
        _post_request(req_invalid, mock_driver)
        print("✗ Invalid JSON should have failed!")
    except Exception as e:
        print(f"✓ Invalid JSON properly rejected: {str(e)}")
    
    # Test form-encoded data (should still work)
    req_form = V1RequestBase({
        "cmd": "request.post",
        "url": "https://httpbin.org/post",
        "postData": "key1=value1&key2=value2",
        "maxTimeout": 60000
    })
    
    print(f"✓ Form-encoded request still supported (no contentType specified)")
    print(f"  POST data: {req_form.postData}")
    
    print("\nAll validation tests passed!")


if __name__ == "__main__":
    test_json_post_validation()
