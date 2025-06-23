import json
from urllib.parse import quote, unquote # unquote is not used in the final solution but often useful
from html import escape # escape is not used in the final solution but often useful

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

# Step 1: Define V1RequestBase class
class V1RequestBase:
    """
    A simple class to mimic the structure of a request object,
    holding the target URL and JSON data for the POST request.
    """
    def __init__(self, url: str, json_data: dict):
        """
        Initializes the V1RequestBase object.

        Args:
            url: The target URL for the POST request.
            json_data: A Python dictionary containing the data to be sent as JSON.
        """
        self.url = url
        self.json_data = json_data

def solve_post_json(driver: webdriver.Chrome, req: V1RequestBase) -> str:
    """
    Simulates an HTTP POST request with Content-Type: application/json
    by generating an HTML page with JavaScript, loading it into the WebDriver,
    and using the browser's fetch API.

    Args:
        driver: An instance of Selenium WebDriver (e.g., Chrome).
        req: An object with 'url' and 'json_data' attributes.
             req.url: The target URL for the POST request.
             req.json_data: A Python dictionary for the JSON payload.

    Returns:
        A string indicating the outcome of the request, usually the content
        of the 'status-message' div from the generated HTML page.
    """
    try:
        # Step 2a: JSON Payload Preparation
        # Convert Python dictionary to JSON string.
        json_payload_str_raw = json.dumps(req.json_data)

        # Escape single quotes in the JSON string to safely embed it in JavaScript.
        # JSON strings use double quotes, so we only need to worry about single quotes
        # if they appear *within* string values in the JSON.
        # The critical part is escaping for JavaScript single-quoted string literals.
        json_payload_str_escaped = json_payload_str_raw.replace("'", "\\'")

        # Step 2b: HTML Document Generation
        # Construct a minimal HTML5 document with embedded JavaScript.
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>POST Request Executor</title>
</head>
<body>
    <h1>Executing POST Request...</h1>
    <div id="status-message">Request initiated...</div>

    <script>
        // JavaScript implementation
        (async function() {{
            const url = '{req.url}';
            // The JSON payload string is directly embedded here.
            // Note: It's wrapped in single quotes in the JS.
            const jsonPayloadStr = '{json_payload_str_escaped}';
            const statusDiv = document.getElementById('status-message');

            console.log('Request URL:', url);
            console.log('JSON Payload (raw string for JS):', jsonPayloadStr);

            try {{
                // Parse the JSON string to ensure it's valid before sending
                // This also correctly unescapes characters for the actual HTTP body
                const jsonData = JSON.parse(jsonPayloadStr);
                console.log('JSON Payload (parsed JS object):', jsonData);

                statusDiv.textContent = 'Sending request to ' + url + '...';

                // fetch API Call
                const response = await fetch(url, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        // Add any other headers if necessary, e.g., 'Accept': 'application/json'
                    }},
                    body: JSON.stringify(jsonData) // Send the parsed and re-stringified JSON object
                }});

                statusDiv.textContent = 'Waiting for response... Status: ' + response.status;
                const responseText = await response.text(); // Get response as text

                if (!response.ok) {{
                    // If response is not ok, throw an error to be caught by the catch block
                    throw new Error(`HTTP error! Status: ${{response.status}} - ${{response.statusText}}. Response: ${{responseText.substring(0, 500)}}`);
                }}

                // Success Display
                // Displaying a snippet of the response.
                const responseSnippet = responseText.substring(0, 200);
                statusDiv.textContent = `Success! Status: ${{response.status}}. Response Snippet: ${{responseSnippet}}`;
                console.log('Full Response:', responseText);

            }} catch (error) {{
                // Error Handling
                console.error('Fetch Error:', error);
                statusDiv.textContent = 'Error: ' + error.message;
            }}
        }})();
    </script>
</body>
</html>
"""
        # Step 2c: WebDriver Execution
        # URL-encode the HTML content for the data URI.
        # `safe=''` ensures that characters like '/', '?', '&', '=', ':' are also encoded.
        # However, for data URIs, common characters in HTML are generally fine.
        # The primary concern is characters that would break the URI structure itself.
        # Using `quote` without `safe=''` is usually sufficient for `data:text/html`.
        # Let's be more specific with `safe` if issues arise, but default should be fine.
        encoded_html_content = quote(html_content)
        data_uri = f"data:text/html,{encoded_html_content}"

        # Load the data URI into the WebDriver.
        driver.get(data_uri)

        # Wait for the JavaScript to update the status message.
        # This indicates that the fetch operation has likely completed (or failed).
        # We wait for "Success!", "Error:", or "HTTP error!" to appear in the div.
        # Increased timeout for potentially slow network requests.
        wait = WebDriverWait(driver, 30) # 30 seconds timeout
        try:
            status_element = wait.until(
                EC.presence_of_element_located((By.ID, "status-message"))
            )

            # Wait until text contains one of the terminal keywords
            wait.until(
                lambda d: "Success!" in status_element.text or \
                          "Error:" in status_element.text or \
                          "HTTP error!" in status_element.text or \
                          "Request initiated..." not in status_element.text # fallback if it never changes from initial
            )

            # A small explicit sleep to allow final JS updates to the DOM if any race condition.
            time.sleep(1)

            final_status_text = status_element.text
        except Exception as e:
            print(f"Timeout or error waiting for status message: {e}")
            # Try to get current status message anyway or logs
            try:
                final_status_text = driver.find_element(By.ID, "status-message").text
            except:
                final_status_text = "Error: Could not retrieve final status message."

        # Retrieve browser console logs for debugging (optional but good for complex cases)
        try:
            browser_logs = driver.get_log('browser')
            if browser_logs:
                print("Browser Console Logs:")
                for entry in browser_logs:
                    print(f"  [{entry['level']}] {entry['message']}")
        except Exception as e:
            print(f"Could not retrieve browser logs: {e} (This might be normal if not supported by driver/config)")

        return final_status_text

    except json.JSONDecodeError as e:
        error_msg = f"JSON Encoding Error: {e}"
        print(error_msg)
        return error_msg
    except Exception as e:
        # Catch any other exceptions during the process.
        error_msg = f"An unexpected error occurred in solve_post_json: {e}"
        print(error_msg)
        # It might be useful to also get the current page source for debugging
        # print("Current Page Source on Error:\n", driver.page_source)
        return error_msg

if __name__ == '__main__':
    # Placeholder for example usage, will be filled in later
    print("V1RequestBase class defined.")
    # Basic test of V1RequestBase
    # req_obj = V1RequestBase("http://example.com", {"key": "value"}) # Keep for basic class test if needed
    # print(f"Request URL: {req_obj.url}, Data: {req_obj.json_data}")

    print("\nsolve_post_json function defined. Running demonstration example...")

    # Step 3: Create Demonstration Example
    # Setup headless Chrome WebDriver
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox") # Necessary for running in some environments (e.g. Docker)
    chrome_options.add_argument("--disable-dev-shm-usage") # Overcome limited resource problems
    # Enable browser logging
    chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})


    driver = None  # Initialize driver to None for finally block
    try:
        driver = webdriver.Chrome(options=chrome_options)

        # Create a dummy V1RequestBase instance
        # Using httpbin.org/post which echoes back the POST request data.
        # This is a great service for testing HTTP requests.
        request_data = {
            "name": "FlareSolverr Test",
            "type": "JSON_POST",
            "message": "Hello from Selenium!",
            "details": {
                "version": 1.0,
                "nested_key": "value with 'single quote' and \"double quote\""
            },
            "items": [1, "two", {"three": 3.0}]
        }
        # Test with a URL that might fail to see error handling
        # req_instance = V1RequestBase(url="https://nonexistent-domain-for-testing123.com/post", json_data=request_data)

        req_instance = V1RequestBase(url="https://httpbin.org/post", json_data=request_data)

        # Call the function
        print(f"\nSending POST request to: {req_instance.url}")
        print(f"With JSON data: {req_instance.json_data}")

        result_message = solve_post_json(driver, req_instance)

        # Print the result
        print("\n--- Result from solve_post_json ---")
        print(result_message)
        print("--- End of Result ---")

        # Example of a failing request (e.g. network error)
        print("\n--- Testing a failing request (network error) ---")
        failing_req_instance = V1RequestBase(url="https://domain.invalid/post", json_data={"error_test": True})
        failing_result_message = solve_post_json(driver, failing_req_instance)
        print("\n--- Result from failing solve_post_json ---")
        print(failing_result_message)
        print("--- End of Failing Result ---")

        # Example of a request to a URL that returns a 404
        print("\n--- Testing a request that results in HTTP 404 ---")
        notfound_req_instance = V1RequestBase(url="https://httpbin.org/status/404", json_data={"status_test": 404})
        notfound_result_message = solve_post_json(driver, notfound_req_instance)
        print("\n--- Result from 404 solve_post_json ---")
        print(notfound_result_message)
        print("--- End of 404 Result ---")


    except Exception as e:
        print(f"An error occurred during the demonstration: {e}")
    finally:
        if driver:
            # Quit the WebDriver session.
            driver.quit()
        print("\nDemonstration finished and WebDriver closed.")
