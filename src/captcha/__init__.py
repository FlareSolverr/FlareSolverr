"""Pluggable captcha-solver support for FlareSolverr.

A *captcha solver* is an adapter module placed inside this package (for
example :mod:`captcha.2captcha`). The active adapter is selected with the
``CAPTCHA_SOLVER`` environment variable, whose value is the adapter file name
without the ``.py`` extension. When the variable is unset or set to ``none``
no captcha solving is attempted and FlareSolverr keeps its previous behaviour.

Each adapter module must expose a ``get_solver()`` function returning an object
that implements the :class:`CaptchaSolver` protocol.

This module also contains the browser-agnostic *detection* logic
(:func:`detect_captcha`) and the JavaScript snippets used to read the captcha
parameters from the page and to inject the solved token back into it. Keeping
the detection logic pure (it operates on a plain ``dict`` of DOM facts) makes it
straightforward to unit-test without a real browser.
"""
import importlib.util
import logging
import os
import re
from typing import Optional

# Captcha types understood by the solvers / detection logic.
TURNSTILE = "turnstile"
HCAPTCHA = "hcaptcha"
RECAPTCHA = "recaptcha"

# Cloudflare Turnstile site keys look like ``0x4AAAAAAA...``.
_TURNSTILE_SITEKEY_RE = re.compile(r"0x[0-9A-Za-z_-]{20,}")

_SOLVER_CACHE: dict = {}


class CaptchaSolver:
    """Interface every captcha-solver adapter must implement.

    Adapters may subclass this or simply provide an object with the same
    methods (duck typing). Every ``solve_*`` method must return the solution
    token as a string, or raise an exception when the captcha cannot be solved.
    """

    def solve_turnstile(self, *, url: str, sitekey: str, action: Optional[str] = None,
                        data: Optional[str] = None, pagedata: Optional[str] = None,
                        useragent: Optional[str] = None) -> str:
        raise NotImplementedError

    def solve_hcaptcha(self, *, url: str, sitekey: str) -> str:
        raise NotImplementedError

    def solve_recaptcha(self, *, url: str, sitekey: str, version: str = "v2",
                        action: Optional[str] = None) -> str:
        raise NotImplementedError


def get_config_captcha_solver() -> Optional[str]:
    """Return the configured captcha solver adapter name, or ``None``."""
    name = os.environ.get("CAPTCHA_SOLVER", "none")
    if not name or name.strip().lower() == "none":
        return None
    return name.strip()


def get_solver() -> Optional[CaptchaSolver]:
    """Load (and cache) the captcha solver selected by ``CAPTCHA_SOLVER``.

    Returns ``None`` when no solver is configured. Raises an exception when a
    solver is configured but cannot be loaded, so the misconfiguration is
    surfaced to the user instead of being silently ignored.
    """
    name = get_config_captcha_solver()
    if name is None:
        return None

    # only allow a plain file name, never a path (avoid loading arbitrary files)
    safe_name = os.path.basename(name)
    if safe_name in _SOLVER_CACHE:
        return _SOLVER_CACHE[safe_name]

    adapter_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{safe_name}.py")
    if not os.path.isfile(adapter_path):
        raise Exception(f"Captcha solver '{name}' not found. "
                        f"Expected an adapter file at '{adapter_path}'.")

    # load by file location so adapter names that are not valid Python
    # identifiers (e.g. '2captcha') can still be used.
    spec = importlib.util.spec_from_file_location(f"captcha._adapter_{safe_name}", adapter_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "get_solver"):
        raise Exception(f"Captcha solver '{name}' must expose a 'get_solver()' function.")

    solver = module.get_solver()
    _SOLVER_CACHE[safe_name] = solver
    logging.info(f"Captcha solver '{name}' loaded.")
    return solver


# JavaScript executed in the page to collect everything needed to identify a
# captcha and extract its site key. It returns a plain JSON-serialisable object
# consumed by :func:`detect_captcha`.
CAPTCHA_DETECT_JS = r"""
const attr = (el, name) => (el && el.getAttribute(name)) || null;
const collect = (selector, extra) => Array.from(document.querySelectorAll(selector)).map(el => {
    const out = { sitekey: attr(el, 'data-sitekey') };
    (extra || []).forEach(a => { out[a.replace('data-', '')] = attr(el, a); });
    return out;
});
const iframeSrcs = Array.from(document.querySelectorAll('iframe')).map(f => f.src).filter(Boolean);
return {
    turnstileWidgets: collect('.cf-turnstile', ['data-action', 'data-cdata']),
    hasTurnstileResponse: !!document.querySelector('[name="cf-turnstile-response"]'),
    hcaptchaWidgets: collect('.h-captcha'),
    hasHcaptchaResponse: !!document.querySelector('[name="h-captcha-response"]'),
    recaptchaWidgets: collect('.g-recaptcha', ['data-action', 'data-size']),
    hasRecaptchaResponse: !!document.querySelector('#g-recaptcha-response, [name="g-recaptcha-response"]'),
    iframeSrcs: iframeSrcs
};
"""

# JavaScript that injects a solved token back into the page and triggers the
# widget callback (if any). Executed with the token as the single argument.
CAPTCHA_INJECT_JS = {
    TURNSTILE: r"""
const token = arguments[0];
document.querySelectorAll('[name="cf-turnstile-response"], #cf-turnstile-response, #cf-chl-widget-response')
    .forEach(el => { el.value = token; });
try {
    const w = document.querySelector('.cf-turnstile');
    const cb = w && w.getAttribute('data-callback');
    if (cb && typeof window[cb] === 'function') window[cb](token);
} catch (e) {}
""",
    HCAPTCHA: r"""
const token = arguments[0];
document.querySelectorAll('[name="h-captcha-response"], [name="g-recaptcha-response"], textarea#h-captcha-response, textarea#g-recaptcha-response')
    .forEach(el => { el.value = token; el.innerHTML = token; });
try {
    const w = document.querySelector('.h-captcha');
    const cb = w && w.getAttribute('data-callback');
    if (cb && typeof window[cb] === 'function') window[cb](token);
} catch (e) {}
""",
    RECAPTCHA: r"""
const token = arguments[0];
document.querySelectorAll('#g-recaptcha-response, [name="g-recaptcha-response"]')
    .forEach(el => { el.style.display = 'block'; el.value = token; el.innerHTML = token; });
try {
    const w = document.querySelector('.g-recaptcha');
    const cb = w && w.getAttribute('data-callback');
    if (cb && typeof window[cb] === 'function') { window[cb](token); }
    else if (window.___grecaptcha_cfg && window.___grecaptcha_cfg.clients) {
        const clients = window.___grecaptcha_cfg.clients;
        Object.values(clients).forEach(client => {
            Object.values(client).forEach(obj => {
                if (obj && typeof obj === 'object') {
                    Object.values(obj).forEach(inner => {
                        if (inner && typeof inner === 'object' && typeof inner.callback === 'function') {
                            try { inner.callback(token); } catch (e) {}
                        }
                    });
                }
            });
        });
    }
} catch (e) {}
""",
}


def _sitekey_from_iframes(iframe_srcs: list, needles: list, param: Optional[str] = None,
                          regex: Optional[re.Pattern] = None) -> Optional[str]:
    """Best-effort extraction of a site key from captcha iframe URLs."""
    for src in iframe_srcs or []:
        if not any(needle in src for needle in needles):
            continue
        if param:
            match = re.search(rf"[?&]{param}=([^&]+)", src)
            if match:
                return match.group(1)
        if regex:
            match = regex.search(src)
            if match:
                return match.group(0)
    return None


def detect_captcha(facts: dict, page_url: Optional[str] = None) -> Optional[dict]:
    """Decide which captcha (if any) is present from a dict of DOM facts.

    ``facts`` is the object returned by :data:`CAPTCHA_DETECT_JS`. Returns a
    dict ``{type, sitekey, action, data, version}`` describing the captcha to
    solve, or ``None`` when no supported captcha with a usable site key is
    found. Turnstile is preferred over hCaptcha over reCAPTCHA when several are
    present, matching the Cloudflare-centric use case of FlareSolverr.
    """
    if not facts:
        return None
    iframe_srcs = facts.get("iframeSrcs") or []

    # -- Cloudflare Turnstile ------------------------------------------------
    for widget in facts.get("turnstileWidgets") or []:
        if widget.get("sitekey"):
            return {"type": TURNSTILE, "sitekey": widget["sitekey"],
                    "action": widget.get("action"), "data": widget.get("cdata")}
    if facts.get("hasTurnstileResponse"):
        sitekey = _sitekey_from_iframes(
            iframe_srcs, ["challenges.cloudflare.com"], regex=_TURNSTILE_SITEKEY_RE)
        if sitekey:
            return {"type": TURNSTILE, "sitekey": sitekey, "action": None, "data": None}

    # -- hCaptcha ------------------------------------------------------------
    for widget in facts.get("hcaptchaWidgets") or []:
        if widget.get("sitekey"):
            return {"type": HCAPTCHA, "sitekey": widget["sitekey"]}
    if facts.get("hasHcaptchaResponse") or any("hcaptcha.com" in s for s in iframe_srcs):
        sitekey = _sitekey_from_iframes(iframe_srcs, ["hcaptcha.com"], param="sitekey")
        if sitekey:
            return {"type": HCAPTCHA, "sitekey": sitekey}

    # -- Google reCAPTCHA ----------------------------------------------------
    for widget in facts.get("recaptchaWidgets") or []:
        if widget.get("sitekey"):
            version = "v3" if widget.get("action") else "v2"
            return {"type": RECAPTCHA, "sitekey": widget["sitekey"],
                    "action": widget.get("action"), "version": version}
    if facts.get("hasRecaptchaResponse") or any("recaptcha" in s for s in iframe_srcs):
        sitekey = _sitekey_from_iframes(
            iframe_srcs, ["google.com/recaptcha", "recaptcha.net"], param="k")
        if sitekey:
            return {"type": RECAPTCHA, "sitekey": sitekey, "action": None, "version": "v2"}

    return None
