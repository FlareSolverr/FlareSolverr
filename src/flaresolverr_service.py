import json
import logging
import traceback
import platform
import sys
import time
from datetime import timedelta
from html import escape
from urllib.parse import unquote, quote

from func_timeout import FunctionTimedOut, func_timeout
from selenium.common import TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.expected_conditions import (
    presence_of_element_located, staleness_of, title_is)
from selenium.webdriver.support.wait import WebDriverWait
from selenium_fetch import fetch, Options

import utils
from dtos import (STATUS_ERROR, STATUS_OK, ChallengeResolutionResultT,
                  ChallengeResolutionT, HealthResponse, IndexResponse,
                  V1RequestBase, V1ResponseBase)
from sessions import SessionsStorage

ACCESS_DENIED_TITLES = [
    # Cloudflare
    'Access denied',
    # Cloudflare http://bitturk.net/ Firefox
    'Attention Required! | Cloudflare'
]
ACCESS_DENIED_SELECTORS = [
    # Cloudflare
    'div.cf-error-title span.cf-code-label span',
    # Cloudflare http://bitturk.net/ Firefox
    '#cf-error-details div.cf-error-overview h1'
]
CHALLENGE_TITLES = [
    # Cloudflare
    'Just a moment...',
    # DDoS-GUARD
    'DDoS-Guard'
]
CHALLENGE_SELECTORS = [
    # Cloudflare
    '#cf-challenge-running', '.ray_id', '.attack-box', '#cf-please-wait', '#challenge-spinner', '#trk_jschal_js',
    '#turnstile-wrapper', '.lds-ring',
    # Custom CloudFlare for EbookParadijs, Film-Paleis, MuziekFabriek and Puur-Hollands
    'td.info #js_info',
    # Fairlane / pararius.com
    'div.vc div.text-box h2'
]
SHORT_TIMEOUT = 1
SESSIONS_STORAGE = SessionsStorage()


def test_browser_installation():
    logging.info("Testing web browser installation...")
    logging.info("Platform: " + platform.platform())

    chrome_exe_path = utils.get_chrome_exe_path()
    if chrome_exe_path is None:
        logging.error("Chrome / Chromium web browser not installed!")
        sys.exit(1)
    else:
        logging.info("Chrome / Chromium path: " + chrome_exe_path)

    chrome_major_version = utils.get_chrome_major_version()
    if chrome_major_version == '':
        logging.error("Chrome / Chromium version not detected!")
        sys.exit(1)
    else:
        logging.info("Chrome / Chromium major version: " + chrome_major_version)

    logging.info("Launching web browser...")
    user_agent = utils.get_user_agent()
    logging.info("FlareSolverr User-Agent: " + user_agent)
    logging.info("Test successful!")


def index_endpoint() -> IndexResponse:
    res = IndexResponse({})
    res.msg = "FlareSolverr is ready!"
    res.version = utils.get_flaresolverr_version()
    res.userAgent = utils.get_user_agent()
    return res


def health_endpoint() -> HealthResponse:
    res = HealthResponse({})
    res.status = STATUS_OK
    return res


def controller_v1_endpoint(req: V1RequestBase) -> V1ResponseBase:
    start_ts = int(time.time() * 1000)
    logging.info(f"Incoming request => POST /v1 body: {utils.object_to_dict(req)}")
    res: V1ResponseBase
    try:
        res = _controller_v1_handler(req)
    except Exception as e:
        res = V1ResponseBase({})
        res.__error_500__ = True
        res.status = STATUS_ERROR
        res.message = "Error: " + str(e)
        logging.error(res.message)

    res.startTimestamp = start_ts
    res.endTimestamp = int(time.time() * 1000)
    res.version = utils.get_flaresolverr_version()
    logging.debug(f"Response => POST /v1 body: {utils.object_to_dict(res)}")
    logging.info(f"Response in {(res.endTimestamp - res.startTimestamp) / 1000} s")
    return res


def _controller_v1_handler(req: V1RequestBase) -> V1ResponseBase:
    """Main request handler that routes commands to appropriate handlers."""
    # Validate required parameters
    if req.cmd is None:
        raise Exception("Request parameter 'cmd' is mandatory.")
    if req.userAgent is not None:
        logging.warning("Request parameter 'userAgent' was removed in FlareSolverr v2.")

    # Set default values
    if req.maxTimeout is None or int(req.maxTimeout) < 1:
        req.maxTimeout = 60000

    # Route command to appropriate handler
    res: V1ResponseBase
    if req.cmd == 'sessions.create':
        res = _cmd_sessions_create(req)
    elif req.cmd == 'sessions.list':
        res = _cmd_sessions_list(req)
    elif req.cmd == 'sessions.destroy':
        res = _cmd_sessions_destroy(req)
    elif req.cmd == 'request.get':
        res = _cmd_request_get(req)
    elif req.cmd == 'request.post':
        res = _cmd_request_post(req)
    elif req.cmd == 'request.delete':
        res = _cmd_request_delete(req)
    else:
        raise Exception(f"Request parameter 'cmd' = '{req.cmd}' is invalid.")

    return res


def _execute_xhr_request(driver: WebDriver, method: str, url: str, headers: dict = None, body: str = None) -> dict:
    """
    Execute an XHR request with custom headers and body using JavaScript.

    Args:
        driver: Selenium WebDriver instance
        method: HTTP method (GET, POST, DELETE, etc.)
        url: Target URL
        headers: Optional dictionary of HTTP headers
        body: Optional request body (for POST/DELETE)

    Returns:
        dict: Response data with status, responseText, and success flag
    """
    # Build headers JavaScript code
    headers_js_lines = []
    if headers:
        for header_name, header_value in headers.items():
            escaped_value = str(header_value).replace("'", "\\'")
            headers_js_lines.append(f"xhr.setRequestHeader('{header_name}', '{escaped_value}');")

    headers_js = '\n            '.join(headers_js_lines)

    # Prepare body
    body_js = "null"
    if body:
        escaped_body = body.replace("'", "\\'")
        body_js = f"'{escaped_body}'"

    # Execute XHR request
    script = f"""
    var xhr = new XMLHttpRequest();
    xhr.open('{method}', '{url}', false);
    {headers_js}

    try {{
        xhr.send({body_js});
        return {{
            status: xhr.status,
            statusText: xhr.statusText,
            responseText: xhr.responseText,
            success: true
        }};
    }} catch (error) {{
        return {{
            status: 0,
            statusText: error.message,
            responseText: '',
            success: false,
            error: error.message
        }};
    }}
    """

    result = driver.execute_script(script)

    if result and result.get('success'):
        logging.info(f"{method} request completed with status: {result.get('status', 0)}")
        logging.debug(f"{method} response: {result.get('responseText', '')[:500]}")
    else:
        error_msg = result.get('statusText', 'Unknown error') if result else 'Script execution failed'
        error_detail = result.get('error', '') if result else ''
        logging.error(f"XHR request failed: {error_msg} - {error_detail}")
        raise Exception(f"{method} request failed: {error_msg}")

    return result


def get_with_params(req: V1RequestBase, driver: WebDriver) -> str:
    """
    Execute GET request with custom headers using XHR.
    Used when custom headers are provided.

    Args:
        req: Request object containing URL and headers
        driver: Selenium WebDriver instance

    Returns:
        str: Response text
    """
    headers = getattr(req, 'headers', {})

    try:
        # Load blank page to have a context for XHR
        driver.get("about:blank")
        time.sleep(1)
    except Exception as e:
        logging.warning(f"Could not load blank page: {e}")

    result = _execute_xhr_request(driver, 'GET', req.url, headers)

    # Write response to document
    try:
        driver.execute_script(f"""
            document.open();
            document.write(arguments[0]);
            document.close();
        """, result.get('responseText', ''))
        time.sleep(1)
    except Exception as e:
        logging.warning(f"Could not write response to document: {e}")

    return result.get('responseText', '')


def delete_with_params(req: V1RequestBase, driver: WebDriver) -> str:
    """
    Execute DELETE request with custom headers and optional body using XHR.
    Loads the target page first to bypass protection mechanisms.

    Args:
        req: Request object containing URL, headers, and optional postData
        driver: Selenium WebDriver instance

    Returns:
        str: Response text
    """
    headers = getattr(req, 'headers', {})
    post_data = getattr(req, 'postData', None)

    # Load target page first to bypass protection
    try:
        driver.get(req.url)
        time.sleep(2)

        page_source = driver.page_source.lower()
        if any(term in page_source for term in
               ['cloudflare', 'checking your browser', 'ddos protection', 'please wait']):
            logging.info("Protection detected, waiting for bypass...")
            time.sleep(5)
    except Exception as e:
        logging.warning(f"Could not load target page directly: {e}")

    # Prepare body if provided
    body = None
    if post_data:
        if isinstance(post_data, str):
            body = post_data
        else:
            body = json.dumps(post_data)

    result = _execute_xhr_request(driver, 'DELETE', req.url, headers, body)
    return result.get('responseText', '')


def post_with_params(req: V1RequestBase, driver: WebDriver) -> str:
    """
    Execute POST request with custom headers and body using XHR.
    Supports both JSON and form-encoded data based on Content-Type header.

    Args:
        req: Request object containing URL, headers, and postData
        driver: Selenium WebDriver instance

    Returns:
        str: Response text
    """
    headers = getattr(req, 'headers', {})

    # Determine content type from headers
    content_type = None
    if headers:
        for header_name, header_value in headers.items():
            if header_name.lower() == 'content-type':
                content_type = header_value.lower()
                break

    # Fallback to deprecated contentType parameter if no Content-Type header
    if not content_type:
        content_type = getattr(req, 'contentType', 'application/x-www-form-urlencoded')
        # Add Content-Type to headers if not present
        if not headers:
            headers = {}
        headers['Content-Type'] = content_type

    if not req.postData:
        raise Exception("postData is empty for POST request")

    if 'application/json' in content_type:
        # Handle JSON POST request
        try:
            # Load target page first to bypass protection
            driver.get(req.url)
            time.sleep(2)

            page_source = driver.page_source.lower()
            if any(term in page_source for term in
                   ['cloudflare', 'checking your browser', 'ddos protection', 'please wait']):
                logging.info("Protection detected, waiting for bypass...")
                time.sleep(5)
        except Exception as e:
            logging.warning(f"Could not load target page directly: {e}")

        # Parse and prepare JSON data
        try:
            if isinstance(req.postData, str):
                post_data = json.loads(req.postData)
            else:
                post_data = req.postData
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing failed: {e}")
            raise Exception(f"Invalid JSON in postData: {e}")

        json_body = json.dumps(post_data)
        result = _execute_xhr_request(driver, 'POST', req.url, headers, json_body)
        return result.get('responseText', '')

    elif 'application/x-www-form-urlencoded' in content_type:
        # Handle form-encoded POST request using HTML form submission
        headers_meta = ""
        if headers:
            for header_name, header_value in headers.items():
                if header_name.lower() != 'content-type':
                    headers_meta += f'<meta http-equiv="{header_name}" content="{header_value}">'

        post_form = f'<form id="hackForm" action="{req.url}" method="POST">'
        query_string = req.postData if req.postData[0] != '?' else req.postData[1:]
        pairs = query_string.split('&')

        for pair in pairs:
            if '=' not in pair:
                continue
            parts = pair.split('=', 1)
            try:
                name = unquote(parts[0])
            except:
                name = parts[0]
            if name == 'submit':
                continue
            try:
                value = unquote(parts[1]) if len(parts) > 1 else ''
            except:
                value = parts[1] if len(parts) > 1 else ''
            post_form += f'<input type="text" name="{escape(quote(name))}" value="{escape(quote(value))}"><br>'

        post_form += '</form>'
        html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    {headers_meta}
                </head>
                <body>
                    {post_form}
                    <script>document.getElementById('hackForm').submit();</script>
                </body>
                </html>"""
        driver.get(f"data:text/html;charset=utf-8,{html_content}")
        return "Success"
    else:
        raise Exception(
            f"Unsupported Content-Type: '{content_type}'. Supported: 'application/json', 'application/x-www-form-urlencoded'")


def _cmd_request_get(req: V1RequestBase) -> V1ResponseBase:
    """
    Handle GET request command.
    Uses standard driver.get() for simple requests.
    Uses XHR when custom headers are provided.
    """
    # Validate parameters
    if req.url is None:
        raise Exception("Request parameter 'url' is mandatory in 'request.get' command.")
    if req.postData is not None:
        raise Exception("Cannot use 'postData' when sending a GET request.")
    if req.contentType is not None:
        raise Exception("Cannot use 'contentType' when sending a GET request.")
    if req.returnRawHtml is not None:
        logging.warning("Request parameter 'returnRawHtml' was removed in FlareSolverr v2.")
    if req.download is not None:
        logging.warning("Request parameter 'download' was removed in FlareSolverr v2.")

    challenge_res = _resolve_challenge(req, 'GET')
    res = V1ResponseBase({})
    res.status = challenge_res.status
    res.message = challenge_res.message
    res.solution = challenge_res.result
    return res


def _cmd_request_post(req: V1RequestBase) -> V1ResponseBase:
    """
    Handle POST request command.
    Supports both JSON and form-encoded data.
    Content-Type can be specified via 'headers' parameter or deprecated 'contentType' parameter.
    """
    # Validate parameters
    if req.postData is None:
        raise Exception("Request parameter 'postData' is mandatory in 'request.post' command.")

    # Check for Content-Type in headers
    headers = getattr(req, 'headers', {})
    has_content_type = False
    if headers:
        for header_name in headers.keys():
            if header_name.lower() == 'content-type':
                has_content_type = True
                break

    # If no Content-Type in headers and no contentType parameter, use default
    if not has_content_type and not hasattr(req, 'contentType'):
        # Add default contentType
        req.contentType = 'application/json'

    if req.returnRawHtml is not None:
        logging.warning("Request parameter 'returnRawHtml' was removed in FlareSolverr v2.")
    if req.download is not None:
        logging.warning("Request parameter 'download' was removed in FlareSolverr v2.")

    challenge_res = _resolve_challenge(req, 'POST')
    res = V1ResponseBase({})
    res.status = challenge_res.status
    res.message = challenge_res.message
    res.solution = challenge_res.result
    return res


def _cmd_request_delete(req: V1RequestBase) -> V1ResponseBase:
    """
    Handle DELETE request command.
    Supports optional body and custom headers via XHR.
    """
    # Validate parameters
    if req.url is None:
        raise Exception("Request parameter 'url' is mandatory in 'request.delete' command.")
    if req.returnRawHtml is not None:
        logging.warning("Request parameter 'returnRawHtml' was removed in FlareSolverr v2.")
    if req.download is not None:
        logging.warning("Request parameter 'download' was removed in FlareSolverr v2.")

    challenge_res = _resolve_challenge(req, 'DELETE')
    res = V1ResponseBase({})
    res.status = challenge_res.status
    res.message = challenge_res.message
    res.solution = challenge_res.result
    return res


def _cmd_sessions_create(req: V1RequestBase) -> V1ResponseBase:
    """Create a new session or return existing one."""
    logging.debug("Creating new session...")

    session, fresh = SESSIONS_STORAGE.create(session_id=req.session, proxy=req.proxy)
    session_id = session.session_id

    if not fresh:
        return V1ResponseBase({
            "status": STATUS_OK,
            "message": "Session already exists.",
            "session": session_id
        })

    return V1ResponseBase({
        "status": STATUS_OK,
        "message": "Session created successfully.",
        "session": session_id
    })


def _cmd_sessions_list(req: V1RequestBase) -> V1ResponseBase:
    """List all active session IDs."""
    session_ids = SESSIONS_STORAGE.session_ids()

    return V1ResponseBase({
        "status": STATUS_OK,
        "message": "",
        "sessions": session_ids
    })


def _cmd_sessions_destroy(req: V1RequestBase) -> V1ResponseBase:
    """Destroy an existing session."""
    session_id = req.session
    existed = SESSIONS_STORAGE.destroy(session_id)

    if not existed:
        raise Exception("The session doesn't exist.")

    return V1ResponseBase({
        "status": STATUS_OK,
        "message": "The session has been removed."
    })


def _resolve_challenge(req: V1RequestBase, method: str) -> ChallengeResolutionT:
    """
    Main challenge resolution handler.
    Manages WebDriver lifecycle and executes request with timeout.
    """
    timeout = int(req.maxTimeout) / 1000
    driver = None
    try:
        if req.session:
            session_id = req.session
            ttl = timedelta(minutes=req.session_ttl_minutes) if req.session_ttl_minutes else None
            session, fresh = SESSIONS_STORAGE.get(session_id, ttl)

            if fresh:
                logging.debug(f"New session created to perform the request (session_id={session_id})")
            else:
                logging.debug(f"Existing session is used to perform the request (session_id={session_id}, "
                              f"lifetime={str(session.lifetime())}, ttl={str(ttl)})")

            driver = session.driver
        else:
            driver = utils.get_webdriver(req.proxy)
            logging.debug('New instance of webdriver has been created to perform the request')
        return func_timeout(timeout, _evil_logic, (req, driver, method))
    except FunctionTimedOut:
        raise Exception(f'Error solving the challenge. Timeout after {timeout} seconds.')
    except Exception as e:
        raise Exception('Error solving the challenge. ' + str(e).replace('\n', '\\n'))
    finally:
        if not req.session and driver is not None:
            if utils.PLATFORM_VERSION == "nt":
                driver.close()
            driver.quit()
            logging.debug('A used instance of webdriver has been destroyed')


def click_verify(driver: WebDriver):
    """Attempt to click Cloudflare verification elements."""
    try:
        logging.debug("Try to find the Cloudflare verify checkbox...")
        actions = ActionChains(driver)
        actions.pause(5).send_keys(Keys.TAB).pause(1).send_keys(Keys.SPACE).perform()
        logging.debug("Cloudflare verify checkbox found and clicked!")
    except Exception:
        logging.debug("Cloudflare verify checkbox not found on the page.")
    finally:
        driver.switch_to.default_content()

    try:
        logging.debug("Try to find the Cloudflare 'Verify you are human' button...")
        button = driver.find_element(
            by=By.XPATH,
            value="//input[@type='button' and @value='Verify you are human']",
        )
        if button:
            actions = ActionChains(driver)
            actions.move_to_element_with_offset(button, 5, 7)
            actions.click(button)
            actions.perform()
            logging.debug("The Cloudflare 'Verify you are human' button found and clicked!")
    except Exception:
        logging.debug("The Cloudflare 'Verify you are human' button not found on the page.")

    time.sleep(2)


def _evil_logic(req: V1RequestBase, driver: WebDriver, method: str) -> ChallengeResolutionT:
    """
    Core logic for request execution and challenge detection/solving.
    Handles navigation, cookie management, and Cloudflare challenge detection.
    """
    res = ChallengeResolutionT({})
    res.status = STATUS_OK
    res.message = ""

    # Navigate to the page based on method and headers
    logging.debug(f'Navigating to... {req.url}')
    if method == 'POST':
        res.response = post_with_params(req, driver)
    elif method == 'DELETE':
        res.response = delete_with_params(req, driver)
    elif method == 'GET' and getattr(req, 'headers', None):
        res.response = get_with_params(req, driver)
    else:
        try:
            driver.set_page_load_timeout(90)
            driver.get(req.url)
        except TimeoutException:
            logging.warning(f"Page load timeout for {req.url}, but continuing...")

    logging.info(f'Current URL after navigation: {driver.current_url}')
    logging.info(f'Page title: {driver.title}')

    # Set cookies if required
    if req.cookies is not None and len(req.cookies) > 0:
        logging.debug(f'Setting cookies...')
        for cookie in req.cookies:
            driver.delete_cookie(cookie['name'])
            driver.add_cookie(cookie)
        # Reload the page
        if method == 'POST':
            res.response = post_with_params(req, driver)
        elif method == 'DELETE':
            res.response = delete_with_params(req, driver)
        else:
            driver.get(req.url)

    # Wait for the page
    if utils.get_config_log_html():
        logging.debug(f"Response HTML:\n{driver.page_source}")
    html_element = driver.find_element(By.TAG_NAME, "html")
    page_title = driver.title

    # Check for access denied
    for title in ACCESS_DENIED_TITLES:
        if page_title.startswith(title):
            raise Exception('Cloudflare has blocked this request. '
                            'Probably your IP is banned for this site, check in your web browser.')

    for selector in ACCESS_DENIED_SELECTORS:
        found_elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if len(found_elements) > 0:
            raise Exception('Cloudflare has blocked this request. '
                            'Probably your IP is banned for this site, check in your web browser.')

    # Detect challenge
    challenge_found = False
    for title in CHALLENGE_TITLES:
        if title.lower() == page_title.lower():
            challenge_found = True
            logging.info("Challenge detected. Title found: " + page_title)
            break

    if not challenge_found:
        for selector in CHALLENGE_SELECTORS:
            found_elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if len(found_elements) > 0:
                challenge_found = True
                logging.info("Challenge detected. Selector found: " + selector)
                break

    # Solve challenge if found
    attempt = 0
    if challenge_found:
        while True:
            try:
                attempt = attempt + 1
                # Wait until the title changes
                for title in CHALLENGE_TITLES:
                    logging.debug("Waiting for title (attempt " + str(attempt) + "): " + title)
                    WebDriverWait(driver, SHORT_TIMEOUT).until_not(title_is(title))

                # Wait until all the selectors disappear
                for selector in CHALLENGE_SELECTORS:
                    logging.debug("Waiting for selector (attempt " + str(attempt) + "): " + selector)
                    WebDriverWait(driver, SHORT_TIMEOUT).until_not(
                        presence_of_element_located((By.CSS_SELECTOR, selector)))

                # All elements not found - challenge solved
                break

            except TimeoutException:
                logging.debug("Timeout waiting for selector")
                click_verify(driver)
                # Update the html (cloudflare reloads the page every 5 s)
                html_element = driver.find_element(By.TAG_NAME, "html")

        # Wait until cloudflare redirection ends
        logging.debug("Waiting for redirect")
        try:
            WebDriverWait(driver, SHORT_TIMEOUT).until(staleness_of(html_element))
        except Exception:
            logging.debug("Timeout waiting for redirect")

        logging.info("Challenge solved!")
        res.message = "Challenge solved!"
    else:
        logging.info("Challenge not detected!")
        res.message = "Challenge not detected!"

    # Prepare response
    challenge_res = ChallengeResolutionResultT({})
    challenge_res.url = driver.current_url
    challenge_res.status = 200  # TODO: Extract actual status from XHR response
    challenge_res.cookies = driver.get_cookies()
    challenge_res.userAgent = utils.get_user_agent(driver)

    if not req.returnOnlyCookies:
        challenge_res.headers = {}  # TODO: Extract headers from XHR response
        if req.waitInSeconds and req.waitInSeconds > 0:
            logging.info("Waiting " + str(req.waitInSeconds) + " seconds before returning the response...")
            time.sleep(req.waitInSeconds)
        challenge_res.response = driver.page_source

    if req.returnScreenshot:
        challenge_res.screenshot = driver.get_screenshot_as_base64()

    res.result = challenge_res
    return res
