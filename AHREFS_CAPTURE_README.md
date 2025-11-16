# Ahrefs API Response Capture Feature

This feature automatically captures and saves API responses when using FlareSolverr to access Ahrefs traffic checker.

## How It Works

1. **Automatic Detection**: When FlareSolverr detects an Ahrefs URL, it automatically enables network interception
2. **Captcha Solving**: FlareSolverr solves any Cloudflare captchas as usual
3. **API Interception**: The page automatically calls `https://ahrefs.com/v4/stGetFreeTrafficOverview` after captcha is solved
4. **Response Capture**: The network interceptor captures this API response
5. **File Saving**: Responses are saved to `captured_responses/` directory in both `.txt` and `.json` formats

## Usage

### Method 1: Using the Example Script

```bash
# Make sure FlareSolverr is running
python example_ahrefs_capture.py
```

### Method 2: Using curl

```bash
curl -X POST http://localhost:8191/v1 \
  -H "Content-Type: application/json" \
  -d '{
    "cmd": "request.get",
    "url": "https://ahrefs.com/traffic-checker/?input=yep.com&mode=subdomains",
    "maxTimeout": 60000
  }'
```

### Method 3: Using Python requests

```python
import requests

response = requests.post('http://localhost:8191/v1', json={
    "cmd": "request.get",
    "url": "https://ahrefs.com/traffic-checker/?input=example.com&mode=subdomains",
    "maxTimeout": 60000
})

print(response.json())
```

## Output Files

The captured responses are saved in the `captured_responses/` directory with the following naming pattern:

```
captured_responses/
├── 20250116_143052_123456_ahrefs.com_v4_stGetFreeTrafficOverview.txt
└── 20250116_143052_123456_ahrefs.com_v4_stGetFreeTrafficOverview.json
```

### Text File Format (.txt)

The `.txt` file contains:
- Request metadata (URL, method, timestamp, status)
- Full response body in plain text

Example:
```
================================================================================
CAPTURED API RESPONSE
================================================================================

URL: https://ahrefs.com/v4/stGetFreeTrafficOverview
Method: GET
Timestamp: 2025-01-16T14:30:52.123456
Status: 200

================================================================================
RESPONSE BODY
================================================================================

{"domain": "yep.com", "traffic": {...}, ...}

================================================================================
```

### JSON File Format (.json)

The `.json` file contains:
- `metadata`: Request information
- `body`: Parsed JSON response

Example:
```json
{
  "metadata": {
    "url": "https://ahrefs.com/v4/stGetFreeTrafficOverview",
    "method": "GET",
    "timestamp": "2025-01-16T14:30:52.123456",
    "response_status": 200
  },
  "body": {
    "domain": "yep.com",
    "traffic": {...}
  }
}
```

## Configuration

The interceptor is configured in `src/network_interceptor.py` and monitors these URLs by default:

- `ahrefs.com/v4/stGetFreeTrafficOverview`
- `ahrefs.com/api/*` (any other API calls)

### Customizing Target URLs

To capture different API endpoints, edit `create_ahrefs_interceptor()` in `src/network_interceptor.py`:

```python
def create_ahrefs_interceptor(driver: Chrome, output_dir: str = "captured_responses") -> NetworkInterceptor:
    target_urls = [
        'ahrefs.com/v4/stGetFreeTrafficOverview',
        'ahrefs.com/v4/yourNewEndpoint',  # Add your endpoints here
    ]

    interceptor = NetworkInterceptor(driver, target_urls, output_dir)
    return interceptor
```

### Changing Output Directory

By default, responses are saved to `captured_responses/`. To change this, modify the `output_dir` parameter when creating the interceptor in `src/flaresolverr_service.py`:

```python
interceptor = create_ahrefs_interceptor(driver, output_dir="your_custom_directory")
```

## Logging

The interceptor provides detailed logging:

```
[INFO] Ahrefs URL detected - enabling network interceptor
[INFO] Network interceptor enabled for URLs: ['ahrefs.com/v4/stGetFreeTrafficOverview', ...]
[INFO] Intercepted request: https://ahrefs.com/v4/stGetFreeTrafficOverview
[INFO] Intercepted response: https://ahrefs.com/v4/stGetFreeTrafficOverview
[INFO] Response saved to: captured_responses/20250116_143052_123456_ahrefs.com_v4_stGetFreeTrafficOverview.txt
[INFO] JSON response saved to: captured_responses/20250116_143052_123456_ahrefs.com_v4_stGetFreeTrafficOverview.json
[INFO] Successfully captured 1 API response(s):
[INFO]   - captured_responses/20250116_143052_123456_ahrefs.com_v4_stGetFreeTrafficOverview.txt
```

## How to Run FlareSolverr

### Using Docker (Recommended)

```bash
docker run -d \
  --name flaresolverr \
  -p 8191:8191 \
  -v $(pwd)/captured_responses:/app/captured_responses \
  ghcr.io/flaresolverr/flaresolverr:latest
```

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run FlareSolverr
python src/flaresolverr.py
```

## Troubleshooting

### No responses captured

If you see "No API responses were captured", try:

1. **Increase wait time**: The default wait is 5 seconds. You can increase this in `src/flaresolverr_service.py`:
   ```python
   time.sleep(10)  # Wait 10 seconds instead of 5
   ```

2. **Check if API is called**: Manually visit the Ahrefs URL in your browser and check the Network tab to verify the API is called after captcha

3. **Enable debug logging**: Check FlareSolverr logs for any errors during interception

### Permission errors

If you get permission errors when saving files:

```bash
# Make sure the output directory is writable
mkdir -p captured_responses
chmod 777 captured_responses
```

## Technical Details

### Architecture

The interceptor uses Chrome DevTools Protocol (CDP) to monitor network traffic:

1. `Network.enable` - Enables network tracking
2. `Network.requestWillBeSent` - Captures outgoing requests
3. `Network.responseReceived` - Captures response headers
4. `Network.loadingFinished` - Retrieves response body via `Network.getResponseBody`

### File Structure

```
src/
├── network_interceptor.py      # Network interception module
├── flaresolverr_service.py     # Integration point
└── ...

captured_responses/             # Output directory (created automatically)
├── *.txt                       # Text format responses
└── *.json                      # JSON format responses

example_ahrefs_capture.py       # Example usage script
```

## Educational Purpose & Authorization

This feature is designed for:
- Educational purposes
- Authorized testing of your own Ahrefs traffic
- Debugging and development
- Research with proper authorization

**Important**: Only use this feature with your own authorized Ahrefs account and traffic. Do not use it to scrape or abuse Ahrefs services.

## License

Same license as FlareSolverr (MIT).
