import requests
import json

# Test the JSON POST implementation with a simple endpoint
url = "http://localhost:8191/v1"

payload = {
    "cmd": "request.post",
    "url": "https://jsonplaceholder.typicode.com/posts",
    "postData": json.dumps({
        "title": "Test Post",
        "body": "This is a test post",
        "userId": 1
    }),
    "contentType": "application/json",
    "maxTimeout": 30000
}

response = requests.post(url, json=payload)
print("Status Code:", response.status_code)
print("Response:", json.dumps(response.json(), indent=2))
