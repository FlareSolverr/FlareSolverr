#!/usr/bin/env python3
"""
Test JSON validation functionality
"""

import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dtos import V1RequestBase


def test_json_validation():
    """Test JSON validation scenarios"""
    print("=== JSON Validation Tests ===\n")
    
    # Test 1: Valid JSON
    print("Test 1: Valid JSON data")
    try:
        valid_json = '{"name": "John", "age": 30, "active": true}'
        json.loads(valid_json)  # This is what our code does for validation
        print(f"✓ Valid JSON accepted: {valid_json}")
    except json.JSONDecodeError as e:
        print(f"✗ Unexpected error: {e}")
    
    # Test 2: Invalid JSON - missing value
    print("\nTest 2: Invalid JSON - missing value")
    try:
        invalid_json = '{"name": "John", "age":}'
        json.loads(invalid_json)
        print(f"✗ Should have failed: {invalid_json}")
    except json.JSONDecodeError as e:
        print(f"✓ Invalid JSON properly rejected: {e}")
    
    # Test 3: Invalid JSON - trailing comma
    print("\nTest 3: Invalid JSON - trailing comma")
    try:
        invalid_json = '{"name": "John", "age": 30,}'
        json.loads(invalid_json)
        print(f"✗ Should have failed: {invalid_json}")
    except json.JSONDecodeError as e:
        print(f"✓ Invalid JSON properly rejected: {e}")
    
    # Test 4: Complex nested JSON
    print("\nTest 4: Complex nested JSON")
    try:
        complex_json = '''
        {
            "user": {
                "profile": {
                    "name": "Jane Doe",
                    "preferences": {
                        "theme": "dark",
                        "notifications": true,
                        "features": ["feature1", "feature2"]
                    }
                },
                "sessions": [
                    {"id": 1, "active": true},
                    {"id": 2, "active": false}
                ]
            },
            "metadata": {
                "version": "2.0",
                "timestamp": "2025-09-11T10:00:00Z"
            }
        }
        '''
        json.loads(complex_json)
        print("✓ Complex nested JSON accepted")
    except json.JSONDecodeError as e:
        print(f"✗ Unexpected error: {e}")
    
    # Test 5: Creating V1RequestBase with JSON
    print("\nTest 5: Creating request objects")
    try:
        json_request = V1RequestBase({
            "cmd": "request.post",
            "url": "https://api.example.com/data",
            "postData": '{"action": "create", "data": {"name": "test"}}',
            "contentType": "application/json",
            "maxTimeout": 30000
        })
        print("✓ JSON V1RequestBase created successfully")
        print(f"  - Content-Type: {json_request.contentType}")
        print(f"  - Data length: {len(json_request.postData)} characters")
        
        form_request = V1RequestBase({
            "cmd": "request.post", 
            "url": "https://example.com/form",
            "postData": "field1=value1&field2=value2",
            "maxTimeout": 30000
        })
        print("✓ Form V1RequestBase created successfully") 
        print(f"  - Content-Type: {form_request.contentType or 'None (defaults to form-encoded)'}")
        print(f"  - Data: {form_request.postData}")
        
    except Exception as e:
        print(f"✗ Error creating request: {e}")
    
    print("\n=== All Tests Complete ===")


if __name__ == "__main__":
    test_json_validation()
