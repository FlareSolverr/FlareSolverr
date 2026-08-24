"""
Scrapling engine: patchright + Chromium, with Scrapling's Turnstile/interstitial solver.

Three things differ structurally from the Selenium engine, and they are the reason this
file looks the way it does.

1. Threading. Playwright's *sync* API binds its objects to the greenlet dispatcher of
   the thread that created them, so a session created on one waitress worker thread
   cannot be driven from another -- it raises
   `greenlet.error: cannot switch to a different thread`. FlareSolverr hands pooled
   sessions to whichever worker arrives next, and `func_timeout` runs the solve in a
   *third* thread, so the sync API is unusable here. We therefore run Scrapling's
   *async* session on one dedicated event-loop thread and submit work to it with
   `run_coroutine_threadsafe`. This also replaces `func_timeout`: `asyncio.wait_for`
   cancels cooperatively, so the browser actually gets closed on timeout instead of
   being orphaned when the thread is killed.

2. Response provenance. Scrapling's `ResponseFactory` takes `status` from the *final*
   navigation response but `headers` from the *first* one. On a challenged page the
   first response is the 403 interstitial and the final is the solved 200, so those two
   fields would describe different HTTP responses -- and the `set-cookie` handed to
   Prowlarr would come from the challenge page. We therefore capture the final document
   response ourselves through `page_setup` and read status/headers from that.

3. Ordering. Scrapling runs `page_action` *before* its own `wait`, but FlareSolverr's
   contract is `waitInSeconds` first and then the screenshot of the settled page. So we
   leave Scrapling's `wait` at 0 and do the wait, the POST, the screenshot and the
   turnstile-token read inside `page_action`, in FlareSolverr's order.
"""

import asyncio
import base64
import logging
import os
import platform
import re
import sys
import threading
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from html import escape
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote
from uuid import uuid1
from weakref import WeakKeyDictionary, WeakSet

import utils
from dtos import (STATUS_OK, ChallengeResolutionResultT, ChallengeResolutionT,
                  V1RequestBase)
from engines.challenges import (ACCESS_DENIED_MESSAGE,
                                ACCESS_DENIED_SELECTOR_CSS,
                                CHALLENGE_SELECTOR_CSS, TURNSTILE_SELECTORS,
                                title_is_access_denied, title_is_challenge)

# Grace added to the outer future's timeout so the inner asyncio.wait_for wins the race
# and we report FlareSolverr's timeout message rather than a bare future timeout.
_TIMEOUT_GRACE = 5.0

# Sessions that serve requests without an explicit `session` id, keyed by proxy.
_ANON_PREFIX = '__anon__:'

# Chromium flags FlareSolverr needs and Scrapling does not add. Taken from the
# Selenium engine's option list so container behaviour matches.
_CONTAINER_FLAGS = (
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--no-zygote',
    '--disable-gpu-sandbox',
    '--disable-software-rasterizer',
    '--ignore-certificate-errors',
    '--ignore-ssl-errors',
    # fix GL errors in ASUSTOR NAS -- https://github.com/FlareSolverr/FlareSolverr/issues/782
    '--use-gl=swiftshader',
    # disable breaking popup
    '--disable-features=LocalNetworkAccessChecks',
)

# Resource types blocked for `disableMedia`. Deliberately excludes `stylesheet`:
# Scrapling's Turnstile solver clicks the widget's `bounding_box()`, so it needs layout.
# Blocking CSS makes the box wrong or absent and the solve fails.
_MEDIA_RESOURCE_TYPES = frozenset({'image', 'media', 'font', 'imageset'})

# Playwright's accepted cookie keys. Anything else raises on `add_cookies`.
_COOKIE_KEYS = frozenset({'name', 'value', 'url', 'domain', 'path', 'expires', 'httpOnly',
                          'secure', 'sameSite'})

_POST_FORM_ID = 'flaresolverrPostForm'

# Insert the form, then submit on the next tick so `page.evaluate` can return before the
# navigation tears down its execution context.
_POST_INJECT_JS = """
(html) => {
    const holder = document.createElement('div');
    holder.style.display = 'none';
    holder.innerHTML = html;
    document.body.appendChild(holder);
    const form = document.getElementById('%s');
    setTimeout(() => form.submit(), 0);
}
""" % _POST_FORM_ID

# Cloudflare marks a challenge response with this header, which is the cheapest
# reliable signal that an interstitial was served.
_CF_MITIGATED_HEADER = 'cf-mitigated'
_CHALLENGE_STATUSES = frozenset({403, 429, 503})

# Per-page state. Keyed weakly because Scrapling pools and recycles pages: the response
# listener is attached once per page and finds the in-flight request through this map.
_STATE_BY_PAGE: 'WeakKeyDictionary[Any, Any]' = WeakKeyDictionary()
_INSTRUMENTED: 'WeakSet[Any]' = WeakSet()


def get_config_max_pages() -> int:
    try:
        return max(1, min(50, int(os.environ.get('SCRAPLING_MAX_PAGES', '4'))))
    except ValueError:
        return 4


def get_config_ephemeral_sessions() -> bool:
    """Close the browser after every session-less request, like the Selenium engine does.

    Off by default: reusing a persistent context keeps `cf_clearance` warm, which is the
    single biggest latency win available here. Cookies stay domain-scoped by the browser,
    so reuse does not leak them between sites.
    """
    return os.environ.get('SCRAPLING_EPHEMERAL_SESSIONS', 'false').lower() == 'true'


def get_config_google_referer() -> bool:
    """Scrapling sets a Google referer by default, which helps against Cloudflare.
    Upstream FlareSolverr sends none, so this is switchable."""
    return os.environ.get('SCRAPLING_GOOGLE_REFERER', 'true').lower() == 'true'


def get_config_solve_cloudflare() -> bool:
    return os.environ.get('SCRAPLING_SOLVE_CLOUDFLARE', 'true').lower() == 'true'


def get_config_eager_cf_solve() -> bool:
    """Let Scrapling run its solver on every navigation instead of only when needed.

    Scrapling's `solve_cloudflare=True` enters the solver unconditionally, and the
    solver's first act is to wait up to 5s for network idle -- so every clean page pays
    for a challenge that is not there. By default we pass `solve_cloudflare=False` and
    invoke the very same solver ourselves from `page_action`, but only once Scrapling's
    own detector confirms a challenge is on the page. Set this to `true` to go back to
    Scrapling's built-in behaviour (also the automatic fallback if a Scrapling upgrade
    moves the internals we call).
    """
    return os.environ.get('SCRAPLING_EAGER_CF_SOLVE', 'false').lower() == 'true'


def resolve_display_mode() -> Tuple[bool, bool]:
    """Decide `(headless, use_xvfb)`.

    Patchright is least detectable head-full, so on Linux `HEADLESS=true` means
    "run visible inside a virtual display" -- the same trick the Selenium engine
    uses. Windows and macOS have no Xvfb, so there `HEADLESS=true` means real
    headless rather than a crash on a missing binary.
    """
    if not utils.get_config_headless():
        return False, False
    if sys.platform.startswith('linux'):
        return False, True
    return True, False


def _proxy_to_scrapling(proxy: Optional[dict]) -> Optional[Any]:
    """FlareSolverr's `{url, username, password}` -> Playwright's `{server, username, password}`.

    Playwright authenticates proxies natively, so the Selenium engine's generated MV2
    extension is not needed here.
    """
    if not proxy or not proxy.get('url'):
        return None
    converted: Dict[str, str] = {'server': proxy['url']}
    if proxy.get('username'):
        converted['username'] = proxy['username']
    if proxy.get('password'):
        converted['password'] = proxy['password']
    return converted


def _proxy_key(proxy: Optional[dict]) -> str:
    if not proxy or not proxy.get('url'):
        return 'direct'
    return f"{proxy.get('url')}|{proxy.get('username') or ''}"


def _normalize_out_cookies(cookies) -> List[dict]:
    """Playwright cookies -> the shape FlareSolverr clients expect.

    Playwright reports `expires` as a float (-1 for a session cookie); Selenium reported
    `expiry` as an int and omitted it for session cookies; the README documents `expires`
    plus `size` and `session`. We emit all of them so no client regresses.
    """
    normalized: List[dict] = []
    for raw in cookies or ():
        cookie = dict(raw)
        try:
            expires = float(cookie.get('expires', -1))
        except (TypeError, ValueError):
            expires = -1.0
        cookie['expires'] = expires
        cookie['session'] = expires <= 0
        if expires > 0:
            cookie['expiry'] = int(expires)
        cookie.setdefault('size', len(str(cookie.get('name', ''))) + len(str(cookie.get('value', ''))))
        normalized.append(cookie)
    return normalized


def _sanitize_in_cookie(raw: dict, default_url: str) -> Optional[dict]:
    """A request cookie -> something `context.add_cookies` will accept."""
    cookie = {k: v for k, v in (raw or {}).items() if k in _COOKIE_KEYS and v is not None}
    if not cookie.get('name'):
        return None
    if 'expires' not in cookie and raw.get('expiry') is not None:
        try:
            cookie['expires'] = float(raw['expiry'])
        except (TypeError, ValueError):
            pass
    cookie.setdefault('value', '')
    # Playwright requires either a url or a domain+path pair; Selenium inferred it.
    if 'domain' not in cookie and 'url' not in cookie:
        cookie['url'] = default_url
    return cookie


def _build_post_form(req: V1RequestBase) -> str:
    """Byte-for-byte the same form the Selenium engine builds, so POST behaviour matches."""
    post_form = f'<form id="{_POST_FORM_ID}" action="{req.url}" method="POST">'
    query_string = req.postData if req.postData and req.postData[0] != '?' else req.postData[1:] if req.postData else ''
    pairs = query_string.split('&')
    for pair in pairs:
        parts = pair.split('=', 1)
        # noinspection PyBroadException
        try:
            name = unquote(parts[0])
        except Exception:
            name = parts[0]
        if name == 'submit':
            continue
        # noinspection PyBroadException
        try:
            value = unquote(parts[1]) if len(parts) > 1 else ''
        except Exception:
            value = parts[1] if len(parts) > 1 else ''
        # Protection of " character, for syntax
        value = value.replace('"', '&quot;')
        post_form += f'<input type="text" name="{escape(quote(name))}" value="{escape(quote(value))}"><br>'
    post_form += '</form>'
    return post_form


def _instrument_page(page) -> None:
    """Record every main-frame document response for this page.

    Registered once per page rather than once per request: Scrapling recycles pages
    between requests, so re-registering would pile up listeners.
    """
    if page in _INSTRUMENTED:
        return

    def on_response(response) -> None:
        # noinspection PyBroadException
        try:
            request = response.request
            if not (request.resource_type == 'document'
                    and request.is_navigation_request()
                    and request.frame == page.main_frame):
                return
            state = _STATE_BY_PAGE.get(page)
            if state is None:
                return
            state.documents.append(response)
            headers = response.headers or {}
            if headers.get(_CF_MITIGATED_HEADER, '').lower() == 'challenge':
                state.challenge_seen = True
            elif response.status in _CHALLENGE_STATUSES and 'cloudflare' in headers.get('server', '').lower():
                state.challenge_seen = True
        except Exception:
            pass

    page.on('response', on_response)
    _INSTRUMENTED.add(page)


async def _challenge_present(page) -> bool:
    """FlareSolverr's title/selector challenge test, run against the live page."""
    # noinspection PyBroadException
    try:
        if title_is_challenge(await page.title()):
            return True
        return await page.locator(CHALLENGE_SELECTOR_CSS).count() > 0
    except Exception:
        return False


@dataclass
class _SessionEntry:
    session_id: str
    session: Any
    created_at: datetime
    proxy_key: str

    def lifetime(self) -> timedelta:
        return datetime.now() - self.created_at


@dataclass
class _RequestState:
    """Per-request scratch space shared between `page_setup` and `page_action`."""

    req: V1RequestBase
    method: str
    deadline: float
    session: Any = None
    # True when this engine drives the Cloudflare solve itself; see get_config_eager_cf_solve
    conditional_cf: bool = False
    page: Any = None
    screenshot: Optional[bytes] = None
    turnstile_token: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    documents: List[Any] = field(default_factory=list)
    cookies: List[dict] = field(default_factory=list)
    challenge_seen: bool = False

    def remaining_ms(self) -> int:
        return max(0, int((self.deadline - time.monotonic()) * 1000))

    # -- Scrapling hooks ---------------------------------------------------

    async def page_setup(self, page) -> None:
        """Runs before navigation."""
        self.page = page
        self.documents = []
        _STATE_BY_PAGE[page] = self
        _instrument_page(page)

        if self.req.disableMedia if self.req.disableMedia is not None else utils.get_config_disable_media():
            await page.route('**/*', _media_route_handler)

        if self.req.cookies:
            await self._apply_cookies(page)

    async def page_action(self, page) -> None:
        """Runs after navigation and after Scrapling's Cloudflare solve."""
        await self._solve_cloudflare_if_present(page)

        if self.method == 'POST':
            await self._submit_post_form(page)

        # Non-Cloudflare interstitials (DDoS-Guard, Fairlane) that Scrapling's solver
        # does not know about: wait for them to clear on their own.
        await self._wait_for_challenge_to_clear(page)

        if self.req.waitInSeconds and self.req.waitInSeconds > 0:
            logging.info('Waiting ' + str(self.req.waitInSeconds) + ' seconds before returning the response...')
            await page.wait_for_timeout(self.req.waitInSeconds * 1000)

        if self.req.tabs_till_verify is not None:
            await self._keyboard_verify(page)

        self.turnstile_token = await self._read_turnstile_token(page)

        # Scope the cookies to the resolved URL. `context.cookies()` with no argument
        # returns every cookie the context holds, and the context is reused across
        # requests, so an unfiltered read would hand callers other sites' cookies.
        # noinspection PyBroadException
        try:
            self.cookies = list(await page.context.cookies(page.url))
        except Exception as e:
            logging.warning(f'Could not read the cookies: {e}')
            self.cookies = []

        if self.req.returnScreenshot:
            # noinspection PyBroadException
            try:
                self.screenshot = await page.screenshot()
            except Exception as e:
                logging.warning(f'Could not capture the screenshot: {e}')

    # -- helpers -----------------------------------------------------------

    async def _solve_cloudflare_if_present(self, page) -> None:
        """Detect a Cloudflare challenge and, only then, run Scrapling's solver.

        Reuses Scrapling's own detector and solver so the bypass logic stays in one
        place; all we change is *when* it runs.
        """
        if not self.conditional_cf or self.session is None:
            return
        detect = getattr(self.session, '_detect_cloudflare', None)
        solve = getattr(self.session, '_cloudflare_solver', None)
        if detect is None or solve is None:  # pragma: no cover - checked at startup
            return

        # noinspection PyBroadException
        try:
            content = await page.content()
        except Exception:
            return

        challenge_type = detect(content)
        if not challenge_type:
            return

        logging.info(f'Cloudflare challenge detected ({challenge_type}); solving...')
        self.challenge_seen = True
        await solve(page)
        stability = getattr(self.session, '_wait_for_page_stability', None)
        if stability is not None:
            await stability(page, True, False)

    async def _apply_cookies(self, page) -> None:
        logging.debug('Setting cookies...')
        context = page.context
        to_add = []
        for raw in self.req.cookies:
            cookie = _sanitize_in_cookie(raw, self.req.url)
            if cookie is None:
                continue
            # The context outlives the request, so drop any previous value first.
            # noinspection PyBroadException
            try:
                await context.clear_cookies(name=cookie['name'])
            except Exception:
                pass
            to_add.append(cookie)
        if to_add:
            await context.add_cookies(to_add)

    async def _submit_post_form(self, page) -> None:
        """POST by submitting a generated form from the already-loaded target page.

        Upstream navigates to a `data:` URL holding the form. That cannot be used here:
        `page.goto('data:...')` returns no response and Scrapling raises. Submitting from
        the target page is also strictly better -- the challenge is already cleared and
        the cookies are already set when the POST goes out.
        """
        form_html = _build_post_form(self.req)
        timeout = max(1000, self.remaining_ms())
        async with page.expect_navigation(wait_until='load', timeout=timeout):
            await page.evaluate(_POST_INJECT_JS, form_html)

    async def _wait_for_challenge_to_clear(self, page) -> None:
        deadline = min(self.deadline, time.monotonic() + 60)
        announced = False
        while time.monotonic() < deadline:
            if not await _challenge_present(page):
                if announced:
                    self.notes.append('solved')
                return
            if not announced:
                logging.info('Challenge detected. Waiting for it to clear...')
                announced = True
            await page.wait_for_timeout(1000)
        if announced:
            logging.warning('Challenge still present when the wait budget ran out.')
            self.notes.append('unsolved')

    async def _keyboard_verify(self, page) -> None:
        """Legacy `tabs_till_verify` support.

        Scrapling's solver already handles embedded Turnstile widgets by clicking them,
        so this is a compatibility shim for clients that still send the parameter.
        """
        # noinspection PyBroadException
        try:
            if await page.locator(TURNSTILE_SELECTORS[0]).count() == 0:
                logging.debug('Turnstile challenge not found; ignoring tabs_till_verify.')
                return
            if await self._read_turnstile_token(page):
                logging.debug('Turnstile token already present; ignoring tabs_till_verify.')
                return
            for _ in range(int(self.req.tabs_till_verify)):
                await page.keyboard.press('Tab')
                await page.wait_for_timeout(100)
            await page.keyboard.press('Space')
            await page.wait_for_timeout(2000)
        except Exception as e:
            logging.debug(f'tabs_till_verify walk failed: {e}')

    @staticmethod
    async def _read_turnstile_token(page) -> Optional[str]:
        # noinspection PyBroadException
        try:
            locator = page.locator(TURNSTILE_SELECTORS[0])
            if await locator.count() == 0:
                return None
            token = await locator.first.get_attribute('value')
            if token:
                logging.info(f'Turnstile token: {token}')
            return token or None
        except Exception:
            return None


async def _media_route_handler(route) -> None:
    # noinspection PyBroadException
    try:
        if route.request.resource_type in _MEDIA_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()
    except Exception:
        pass


class ScraplingEngine:
    """Drives Chromium through Scrapling's `AsyncStealthySession`."""

    name = 'scrapling'

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._sessions: Dict[str, _SessionEntry] = {}
        self._lock = threading.RLock()
        self._user_agent: Optional[str] = None
        self._headless, self._use_xvfb = resolve_display_mode()
        self._conditional_cf = self._can_solve_conditionally()

    @staticmethod
    def _can_solve_conditionally() -> bool:
        """Prefer solving on demand, but only while Scrapling still exposes the pieces."""
        if get_config_eager_cf_solve():
            return False
        from scrapling.engines._browsers._stealth import AsyncStealthySession
        required = ('_detect_cloudflare', '_cloudflare_solver', '_wait_for_page_stability')
        missing = [n for n in required if not hasattr(AsyncStealthySession, n)]
        if missing:
            logging.warning('Scrapling no longer exposes %s; falling back to its '
                            'built-in solve_cloudflare path.', ', '.join(missing))
            return False
        return True

    # -- event loop --------------------------------------------------------

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                self._loop_thread = threading.Thread(
                    target=self._loop.run_forever, daemon=True, name='scrapling-loop')
                self._loop_thread.start()
                logging.debug('Scrapling event loop thread started')
            return self._loop

    def _submit(self, coro, timeout: float):
        """Run a coroutine on the engine's loop from any thread, bounded by `timeout`.

        This is what replaces `func_timeout`.
        """
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(asyncio.wait_for(coro, timeout), loop)
        try:
            return future.result(timeout + _TIMEOUT_GRACE)
        except (asyncio.TimeoutError, FutureTimeoutError):
            future.cancel()
            raise Exception(f'Error solving the challenge. Timeout after {timeout} seconds.')

    # -- lifecycle ---------------------------------------------------------

    def startup(self) -> None:
        logging.info('Testing web browser installation...')
        logging.info('Platform: ' + platform.platform())
        self._ensure_loop()

        chrome_exe_path = utils.get_chrome_exe_path()
        if chrome_exe_path:
            logging.info('Chrome / Chromium path: ' + chrome_exe_path)
        else:
            logging.info("Chrome / Chromium not found on the system; using Scrapling's bundled Chromium")

        if self._use_xvfb:
            # Scrapling has no virtual-display handling of its own, so this stays the
            # engine's job.
            utils.start_xvfb_display()
        logging.info(f'Display mode: {"headless" if self._headless else "head-full"}'
                     f'{" (Xvfb)" if self._use_xvfb else ""}')

        logging.info('Launching web browser...')
        self._user_agent = self._submit(self._probe_user_agent(), 180)
        logging.info('FlareSolverr User-Agent: ' + self._user_agent)
        logging.info('Test successful!')

    def shutdown(self) -> None:
        with self._lock:
            session_ids = list(self._sessions)
        for session_id in session_ids:
            # noinspection PyBroadException
            try:
                self.destroy_session(session_id)
            except Exception:
                logging.debug('Error destroying session %s on shutdown', session_id)
        with self._lock:
            loop = self._loop
            self._loop = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)

    def user_agent(self) -> str:
        if self._user_agent is None:
            self._user_agent = self._submit(self._probe_user_agent(), 180)
        return self._user_agent

    async def _probe_user_agent(self) -> str:
        if utils.USER_AGENT:
            return utils.USER_AGENT
        session = self._new_session(proxy=None, max_pages=1)
        try:
            await session.start()
            page = await session.context.new_page()
            try:
                user_agent = await page.evaluate('() => navigator.userAgent')
            finally:
                await page.close()
        finally:
            # noinspection PyBroadException
            try:
                await session.close()
            except Exception:
                pass
        # Fix for Chrome 117 | https://github.com/FlareSolverr/FlareSolverr/issues/910
        return re.sub('HEADLESS', '', user_agent, flags=re.IGNORECASE)

    # -- sessions ----------------------------------------------------------

    def _new_session(self, proxy: Optional[dict], max_pages: int):
        from scrapling.engines._browsers._stealth import AsyncStealthySession

        options: Dict[str, Any] = {
            'headless': self._headless,
            'max_pages': max_pages,
            'extra_flags': list(_CONTAINER_FLAGS),
            'solve_cloudflare': get_config_solve_cloudflare() and not self._conditional_cf,
            'google_search': get_config_google_referer(),
            'disable_resources': False,  # handled per-request, see _media_route_handler
            'retries': 1,                # FlareSolverr's maxTimeout is the retry budget
        }

        language = os.environ.get('LANG', None)
        if language:
            # Scrapling sets --lang/--accept-lang browser-wide, which also covers Web
            # Workers; the context-level locale alone leaks the real language.
            options['locale'] = language.replace('_', '-').split('.')[0]

        if utils.USER_AGENT:
            options['useragent'] = utils.USER_AGENT

        chrome_exe_path = utils.get_chrome_exe_path()
        if chrome_exe_path:
            options['executable_path'] = chrome_exe_path

        converted_proxy = _proxy_to_scrapling(proxy)
        if converted_proxy:
            logging.debug('Using webdriver proxy: %s', converted_proxy['server'])
            options['proxy'] = converted_proxy

        return AsyncStealthySession(**options)

    def _acquire(self, session_id: str, proxy: Optional[dict], force_new: bool = False) -> Tuple[_SessionEntry, bool]:
        """Get or create a session. Returns the entry and whether it was created now."""
        with self._lock:
            if force_new and session_id in self._sessions:
                self._destroy_locked(session_id)
            entry = self._sessions.get(session_id)
            if entry is not None:
                return entry, False

        session = self._new_session(proxy, get_config_max_pages())
        self._submit(session.start(), 180)
        entry = _SessionEntry(session_id, session, datetime.now(), _proxy_key(proxy))

        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                # Lost a race; keep the winner and discard ours.
                loser = session
                self._submit_quiet(loser.close())
                return existing, False
            self._sessions[session_id] = entry
            return entry, True

    def _submit_quiet(self, coro) -> None:
        # noinspection PyBroadException
        try:
            self._submit(coro, 60)
        except Exception:
            pass

    def _destroy_locked(self, session_id: str) -> bool:
        entry = self._sessions.pop(session_id, None)
        if entry is None:
            return False
        self._submit_quiet(entry.session.close())
        return True

    def create_session(self, session_id: Optional[str], proxy: Optional[dict]) -> Tuple[str, bool]:
        session_id = session_id or str(uuid1())
        _, fresh = self._acquire(session_id, proxy)
        return session_id, fresh

    def list_sessions(self) -> List[str]:
        with self._lock:
            return [sid for sid in self._sessions if not sid.startswith(_ANON_PREFIX)]

    def destroy_session(self, session_id: str) -> bool:
        with self._lock:
            return self._destroy_locked(session_id)

    def _session_for_request(self, req: V1RequestBase) -> Tuple[_SessionEntry, bool]:
        """Resolve the session a request should run on.

        A per-request proxy cannot be layered onto an existing persistent context --
        Scrapling's per-fetch `proxy=` needs a session launched in proxy-rotation mode.
        So session-less requests get a session keyed by their proxy instead.
        """
        if req.session:
            ttl = timedelta(minutes=req.session_ttl_minutes) if req.session_ttl_minutes else None
            entry, fresh = self._acquire(req.session, req.proxy)
            if not fresh and ttl is not None and entry.lifetime() > ttl:
                logging.debug(f"session's lifetime has expired, so the session is recreated "
                              f"(session_id={req.session})")
                entry, fresh = self._acquire(req.session, req.proxy, force_new=True)
            if fresh:
                logging.debug(f'new session created to perform the request (session_id={req.session})')
            else:
                logging.debug(f'existing session is used to perform the request (session_id={req.session}, '
                              f'lifetime={str(entry.lifetime())}, ttl={str(ttl)})')
            return entry, False

        key = _ANON_PREFIX + _proxy_key(req.proxy)
        ephemeral = get_config_ephemeral_sessions()
        if ephemeral:
            key = f'{key}:{uuid1()}'
        entry, fresh = self._acquire(key, req.proxy)
        if fresh:
            logging.debug('New instance of the browser has been created to perform the request')
        return entry, ephemeral

    # -- solving -----------------------------------------------------------

    def solve(self, req: V1RequestBase, method: str) -> ChallengeResolutionT:
        timeout = int(req.maxTimeout) / 1000
        entry, ephemeral = self._session_for_request(req)
        try:
            return self._submit(self._solve(entry, req, method, timeout), timeout)
        except Exception as e:
            message = str(e)
            if message.startswith('Error solving the challenge.'):
                raise
            raise Exception('Error solving the challenge. ' + message.replace('\n', '\\n'))
        finally:
            if ephemeral:
                self.destroy_session(entry.session_id)
                logging.debug('A used instance of the browser has been destroyed')

    async def _solve(self, entry: _SessionEntry, req: V1RequestBase, method: str,
                     timeout: float) -> ChallengeResolutionT:
        state = _RequestState(req=req, method=method, deadline=time.monotonic() + timeout,
                              session=entry.session, conditional_cf=self._conditional_cf)

        # Scrapling raises `timeout` to 60s whenever solve_cloudflare is on, so the
        # authoritative bound is the outer asyncio.wait_for in `_submit`.
        try:
            response = await entry.session.fetch(
                req.url,
                timeout=timeout * 1000,
                wait=0,
                page_setup=state.page_setup,
                page_action=state.page_action,
            )
        except Exception as e:
            # Chromium refuses to render some error responses (a 4xx/5xx with an empty
            # body raises ERR_HTTP_RESPONSE_CODE_FAILURE), and Playwright surfaces that
            # as a failed navigation. The Selenium engine returned the response anyway,
            # and callers rely on reading error pages, so rebuild from what the response
            # listener captured instead of failing the request.
            salvaged = await self._salvage(state, req, e)
            if salvaged is None:
                raise
            return salvaged

        return await self._build_result(state, req, response)

    async def _salvage(self, state: '_RequestState', req: V1RequestBase,
                       error: Exception) -> Optional[ChallengeResolutionT]:
        final = state.documents[-1] if state.documents else None
        if final is None:
            return None

        # noinspection PyBroadException
        try:
            body = await final.text()
        except Exception:
            body = ''

        logging.warning(f'Navigation reported an error ({str(error).splitlines()[0]}); '
                        f'returning the captured {final.status} response instead.')

        res = ChallengeResolutionT({})
        res.status = STATUS_OK
        res.message = 'Challenge not detected!'

        challenge_res = ChallengeResolutionResultT({})
        challenge_res.url = final.url
        challenge_res.status = final.status
        challenge_res.cookies = _normalize_out_cookies(state.cookies)
        challenge_res.userAgent = self.user_agent()
        challenge_res.turnstile_token = None
        if not req.returnOnlyCookies:
            # noinspection PyBroadException
            try:
                challenge_res.headers = dict(await final.all_headers())
            except Exception:
                challenge_res.headers = {}
            challenge_res.response = body
        res.result = challenge_res
        return res

    async def _build_result(self, state: _RequestState, req: V1RequestBase,
                            response) -> ChallengeResolutionT:
        res = ChallengeResolutionT({})
        res.status = STATUS_OK

        html = response.body.decode(response.encoding or 'utf-8', errors='replace')
        if utils.get_config_log_html():
            logging.debug(f'Response HTML:\n{html}')

        page_title = response.css('title::text').get() or ''
        if title_is_access_denied(page_title) or response.css(ACCESS_DENIED_SELECTOR_CSS):
            raise Exception(ACCESS_DENIED_MESSAGE)

        documents = state.documents
        final = documents[-1] if documents else None

        if 'unsolved' in state.notes:
            raise Exception('Challenge not solved! Maybe try again later.')

        # A challenge counts as seen when Scrapling's detector found one on the page,
        # when Cloudflare marked the response (`cf-mitigated: challenge`, or a Cloudflare
        # 403/429/503), or when our own wait loop watched a non-Cloudflare interstitial
        # clear. No inference from navigation counts: redirect chains are not challenges.
        challenged = state.challenge_seen or 'solved' in state.notes
        if challenged:
            logging.info('Challenge solved!')
            res.message = 'Challenge solved!'
        else:
            logging.info('Challenge not detected!')
            res.message = 'Challenge not detected!'

        challenge_res = ChallengeResolutionResultT({})
        challenge_res.url = response.url
        challenge_res.status = final.status if final is not None else response.status
        challenge_res.cookies = _normalize_out_cookies(state.cookies)
        challenge_res.userAgent = (response.request_headers or {}).get('user-agent') or self.user_agent()
        challenge_res.turnstile_token = state.turnstile_token

        if not req.returnOnlyCookies:
            if final is not None:
                # noinspection PyBroadException
                try:
                    challenge_res.headers = dict(await final.all_headers())
                except Exception:
                    challenge_res.headers = dict(response.headers or {})
            else:
                challenge_res.headers = dict(response.headers or {})
            challenge_res.response = html

        if req.returnScreenshot and state.screenshot is not None:
            challenge_res.screenshot = base64.b64encode(state.screenshot).decode('ascii')

        res.result = challenge_res
        return res
