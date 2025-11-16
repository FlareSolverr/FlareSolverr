"""
Network Interceptor Module
Captures and saves responses from specific API endpoints
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional
from selenium.webdriver import Chrome

log = logging.getLogger('flaresolverr')


class NetworkInterceptor:
    """
    Intercepts network requests and responses using Chrome DevTools Protocol (CDP)
    """

    def __init__(self, driver: Chrome, target_urls: list[str], output_dir: str = "captured_responses"):
        """
        Initialize the network interceptor

        Args:
            driver: Selenium Chrome WebDriver instance
            target_urls: List of URL patterns to intercept (supports partial matching)
            output_dir: Directory to save captured responses
        """
        self.driver = driver
        self.target_urls = target_urls
        self.output_dir = output_dir
        self.captured_responses = []

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Storage for request-response mapping
        self.requests = {}

    def enable(self):
        """
        Enable network interception by registering CDP event listeners
        """
        try:
            # Enable network tracking
            self.driver.execute_cdp_cmd('Network.enable', {})

            # Add CDP event listeners
            self.driver.add_cdp_listener('Network.requestWillBeSent', self._on_request_sent)
            self.driver.add_cdp_listener('Network.responseReceived', self._on_response_received)
            self.driver.add_cdp_listener('Network.loadingFinished', self._on_loading_finished)

            log.info(f"Network interceptor enabled for URLs: {self.target_urls}")
            return True

        except Exception as e:
            log.error(f"Failed to enable network interceptor: {e}")
            return False

    def _matches_target_url(self, url: str) -> bool:
        """
        Check if URL matches any of the target URLs

        Args:
            url: URL to check

        Returns:
            True if URL matches any target pattern
        """
        return any(target in url for target in self.target_urls)

    def _on_request_sent(self, message: dict):
        """
        Handler for Network.requestWillBeSent event

        Args:
            message: CDP event message
        """
        try:
            params = message.get('params', {})
            request_id = params.get('requestId')
            request = params.get('request', {})
            url = request.get('url', '')

            if self._matches_target_url(url):
                log.info(f"Intercepted request: {url}")
                self.requests[request_id] = {
                    'url': url,
                    'method': request.get('method'),
                    'headers': request.get('headers'),
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            log.error(f"Error in _on_request_sent: {e}")

    def _on_response_received(self, message: dict):
        """
        Handler for Network.responseReceived event

        Args:
            message: CDP event message
        """
        try:
            params = message.get('params', {})
            request_id = params.get('requestId')
            response = params.get('response', {})
            url = response.get('url', '')

            if self._matches_target_url(url) and request_id in self.requests:
                log.info(f"Intercepted response: {url}")
                self.requests[request_id]['response'] = {
                    'status': response.get('status'),
                    'statusText': response.get('statusText'),
                    'headers': response.get('headers'),
                    'mimeType': response.get('mimeType')
                }
        except Exception as e:
            log.error(f"Error in _on_response_received: {e}")

    def _on_loading_finished(self, message: dict):
        """
        Handler for Network.loadingFinished event
        Retrieves and saves the response body

        Args:
            message: CDP event message
        """
        try:
            params = message.get('params', {})
            request_id = params.get('requestId')

            if request_id in self.requests:
                request_data = self.requests[request_id]
                url = request_data['url']

                # Get response body using CDP
                try:
                    response = self.driver.execute_cdp_cmd('Network.getResponseBody', {
                        'requestId': request_id
                    })

                    body = response.get('body', '')
                    base64_encoded = response.get('base64Encoded', False)

                    if base64_encoded:
                        import base64
                        body = base64.b64decode(body).decode('utf-8')

                    # Save the response
                    self._save_response(request_data, body)

                    # Clean up
                    del self.requests[request_id]

                except Exception as e:
                    log.warning(f"Could not get response body for {url}: {e}")

        except Exception as e:
            log.error(f"Error in _on_loading_finished: {e}")

    def _save_response(self, request_data: dict, body: str):
        """
        Save captured response to a file

        Args:
            request_data: Request metadata
            body: Response body
        """
        try:
            url = request_data['url']
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')

            # Create filename from URL and timestamp
            url_safe = url.replace('https://', '').replace('http://', '').replace('/', '_').replace('?', '_')[:100]
            filename = f"{timestamp}_{url_safe}.txt"
            filepath = os.path.join(self.output_dir, filename)

            # Prepare metadata
            metadata = {
                'url': url,
                'method': request_data.get('method'),
                'timestamp': request_data.get('timestamp'),
                'response_status': request_data.get('response', {}).get('status'),
                'response_headers': request_data.get('response', {}).get('headers'),
            }

            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("CAPTURED API RESPONSE\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"URL: {metadata['url']}\n")
                f.write(f"Method: {metadata['method']}\n")
                f.write(f"Timestamp: {metadata['timestamp']}\n")
                f.write(f"Status: {metadata['response_status']}\n")
                f.write("\n" + "=" * 80 + "\n")
                f.write("RESPONSE BODY\n")
                f.write("=" * 80 + "\n\n")
                f.write(body)
                f.write("\n\n" + "=" * 80 + "\n")

            log.info(f"Response saved to: {filepath}")
            self.captured_responses.append(filepath)

            # Also save as JSON if the body is JSON
            try:
                json_data = json.loads(body)
                json_filepath = filepath.replace('.txt', '.json')
                with open(json_filepath, 'w', encoding='utf-8') as f:
                    json.dump({
                        'metadata': metadata,
                        'body': json_data
                    }, f, indent=2, ensure_ascii=False)
                log.info(f"JSON response saved to: {json_filepath}")
            except:
                pass  # Not JSON, that's fine

        except Exception as e:
            log.error(f"Error saving response: {e}")

    def get_captured_responses(self) -> list[str]:
        """
        Get list of captured response file paths

        Returns:
            List of file paths
        """
        return self.captured_responses

    def disable(self):
        """
        Disable network interception
        """
        try:
            self.driver.execute_cdp_cmd('Network.disable', {})
            log.info("Network interceptor disabled")
        except Exception as e:
            log.error(f"Error disabling network interceptor: {e}")


def create_ahrefs_interceptor(driver: Chrome, output_dir: str = "captured_responses") -> NetworkInterceptor:
    """
    Create a network interceptor specifically for Ahrefs traffic checker API

    Args:
        driver: Selenium Chrome WebDriver instance
        output_dir: Directory to save captured responses

    Returns:
        Configured NetworkInterceptor instance
    """
    target_urls = [
        'ahrefs.com/v4/stGetFreeTrafficOverview',
        'ahrefs.com/api/',  # Catch other potential API calls
    ]

    interceptor = NetworkInterceptor(driver, target_urls, output_dir)
    return interceptor
