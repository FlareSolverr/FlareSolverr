import logging
import platform
import sys
import time
from datetime import timedelta
from html import escape
from urllib.parse import unquote, quote

from func_timeout import FunctionTimedOut, func_timeout
from DrissionPage import ChromiumPage
from DrissionPage._units.listener import DataPacket

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
    '#cf-challenge-running', '.ray_id', '.attack-box', '#cf-please-wait', '#challenge-spinner', '#trk_jschal_js', '#turnstile-wrapper', '.lds-ring',
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
    # do some validations
    if req.cmd is None:
        raise Exception("Request parameter 'cmd' is mandatory.")
    if req.headers is not None:
        logging.warning("Request parameter 'headers' was removed in FlareSolverr v2.")
    if req.userAgent is not None:
        logging.warning("Request parameter 'userAgent' was removed in FlareSolverr v2.")

    # set default values
    if req.maxTimeout is None or int(req.maxTimeout) < 1:
        req.maxTimeout = 60000

    # execute the command
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
    else:
        raise Exception(f"Request parameter 'cmd' = '{req.cmd}' is invalid.")

    return res


def _cmd_request_get(req: V1RequestBase) -> V1ResponseBase:
    # do some validations
    if req.url is None:
        raise Exception("Request parameter 'url' is mandatory in 'request.get' command.")
    if req.postData is not None:
        raise Exception("Cannot use 'postBody' when sending a GET request.")
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
    # do some validations
    if req.postData is None:
        raise Exception("Request parameter 'postData' is mandatory in 'request.post' command.")
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


def _cmd_sessions_create(req: V1RequestBase) -> V1ResponseBase:
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
    session_ids = SESSIONS_STORAGE.session_ids()

    return V1ResponseBase({
        "status": STATUS_OK,
        "message": "",
        "sessions": session_ids
    })


def _cmd_sessions_destroy(req: V1RequestBase) -> V1ResponseBase:
    session_id = req.session
    existed = SESSIONS_STORAGE.destroy(session_id)

    if not existed:
        raise Exception("The session doesn't exist.")

    return V1ResponseBase({
        "status": STATUS_OK,
        "message": "The session has been removed."
    })


def _resolve_challenge(req: V1RequestBase, method: str) -> ChallengeResolutionT:
    timeout = int(req.maxTimeout) / 1000
    driver = None
    try:
        if req.session:
            session_id = req.session
            ttl = timedelta(minutes=req.session_ttl_minutes) if req.session_ttl_minutes else None
            session, fresh = SESSIONS_STORAGE.get(session_id, ttl)

            if fresh:
                logging.debug(f"new session created to perform the request (session_id={session_id})")
            else:
                logging.debug(f"existing session is used to perform the request (session_id={session_id}, "
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

def click_verify(driver: ChromiumPage) -> DataPacket:
    try:
        bde = (
            driver
            .ele("@Style=border: 0px; margin: 0px; padding: 0px;", timeout=10)
            .shadow_root
            .ele("tag:iframe", timeout=10)
            .ele('tag:body', timeout=10)
            .shadow_root
        )
        ve = bde.ele("text:Verify you are human", timeout=10)

        driver.listen.resume()
        ve.click()
        data = driver.listen.wait(count=1,timeout=5)

        if isinstance(data, DataPacket):
            return data

        return None

    except Exception as e:
        logging.debug("Cloudflare verify checkbox not found on the page. %s", repr(e))


def search_challenge(driver: ChromiumPage) -> bool:
    page_title = driver.title.lower()

    # find challenge by title
    for title in CHALLENGE_TITLES:
        if title.lower() == page_title:
            logging.debug("Challenge detected. Title found: %s", page_title)
            return True
    # find challenge by selectors
    if driver.wait.eles_loaded(locators=CHALLENGE_SELECTORS, timeout=SHORT_TIMEOUT, any_one=True):
        logging.debug("Challenge detected. One of selectors found")
        return True
    return False


def _evil_logic(req: V1RequestBase, driver: ChromiumPage, method: str) -> ChallengeResolutionT:
    res = ChallengeResolutionT({})
    res.status = STATUS_OK
    res.message = ""


    # navigate to the page
    logging.debug('Navigating to... %s', req.url)
    driver.listen.start(req.url)
    if method == 'POST':
        _post_request(req, driver)
    else:
        driver.get(req.url)
    data = driver.listen.wait(count=1,timeout=5)
    driver.listen.pause()

    # set cookies if required
    if req.cookies is not None and len(req.cookies) > 0:
        logging.debug('Setting cookies...')
        for cookie in req.cookies:
            driver.set.cookies.remove(cookie['name'])
            driver.set.cookies(cookie)
        # reload the page
        driver.listen.resume()
        if method == 'POST':
            _post_request(req, driver)
        else:
            driver.get(req.url)
        data = driver.listen.wait(count=1, timeout=5)
        driver.listen.pause()

    # wait for the page
    if utils.get_config_log_html():
        logging.debug("Response HTML:\n%s", driver.page_source)

    page_title = driver.title
    # find access denied titles
    for title in ACCESS_DENIED_TITLES:
        if title == page_title:
            raise Exception('Cloudflare has blocked this request. '
                            'Probably your IP is banned for this site, check in your web browser.')
    # find access denied selectors
    if driver.wait.eles_loaded(locators=ACCESS_DENIED_SELECTORS, timeout=SHORT_TIMEOUT, any_one=True):
        raise Exception('Cloudflare has blocked this request. '
                        'Probably your IP is banned for this site, check in your web browser.')

    attempt = 0
    challenge_found = True
    while challenge_found:
        try:
            attempt += 1

            if search_challenge(driver):
                if attempt == 1:
                    logging.info("Challenge detected.")

                data = click_verify(driver)
            else:
                if attempt == 1:
                    logging.info("Challenge not detected!")
                    res.message = "Challenge not detected!"
                else:
                    logging.info("Challenge solved!")
                    res.message = "Challenge solved!"
                break

        except Exception as e:
            logging.debug("Cloudflare check exception")
            raise e


    challenge_res = ChallengeResolutionResultT({})
    challenge_res.url = driver.url
    if data is not None and data.response is not None:
        challenge_res.status = data.response.status
        if not req.returnOnlyCookies:
            challenge_res.response = data.response.body
            challenge_res.headers = data.response.headers.copy()

    challenge_res.cookies = driver.cookies()
    challenge_res.userAgent = utils.get_user_agent(driver)

    res.result = challenge_res
    return res


def _post_request(req: V1RequestBase, driver: ChromiumPage):
    post_form = f'<form id="hackForm" action="{req.url}" method="POST">'
    query_string = req.postData if req.postData[0] != '?' else req.postData[1:]
    pairs = query_string.split('&')
    for pair in pairs:
        parts = pair.split('=')
        # noinspection PyBroadException
        try:
            name = unquote(parts[0])
        except Exception:
            name = parts[0]
        if name == 'submit':
            continue
        # noinspection PyBroadException
        try:
            value = unquote(parts[1])
        except Exception:
            value = parts[1]
        post_form += f'<input type="text" name="{escape(quote(name))}" value="{escape(quote(value))}"><br>'
    post_form += '</form>'
    html_content = f"""
        <!DOCTYPE html>
        <html>
        <body>
            {post_form}
            <script>document.getElementById('hackForm').submit();</script>
        </body>
        </html>"""
    driver.get("data:text/html;charset=utf-8,{html_content}".format(html_content=html_content))
