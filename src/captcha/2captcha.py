"""2captcha (https://2captcha.com) adapter for FlareSolverr.

Enable it with::

    CAPTCHA_SOLVER=2captcha
    TWOCAPTCHA_API_KEY=<your api key>

Optional environment variables:

    TWOCAPTCHA_SERVER            API host, defaults to ``2captcha.com``
                                 (use ``rucaptcha.com`` for RuCaptcha).
    TWOCAPTCHA_SOFT_ID           Software id sent to the API.
    TWOCAPTCHA_DEFAULT_TIMEOUT   Seconds to wait for a solution (default 120).
    TWOCAPTCHA_POLLING_INTERVAL  Seconds between result polls (default 10).

This adapter is a thin wrapper around the official ``2captcha-python``
library, mapping FlareSolverr's captcha types to the corresponding 2captcha
methods and returning the solution token.
"""
import logging
import os

from twocaptcha import TwoCaptcha

from captcha import CaptchaSolver


class TwoCaptchaSolver(CaptchaSolver):
    def __init__(self, api_key: str, **client_opts):
        self._client = TwoCaptcha(api_key, **client_opts)

    def solve_turnstile(self, *, url, sitekey, action=None, data=None,
                        pagedata=None, useragent=None):
        kwargs = {}
        if action:
            kwargs["action"] = action
        if data:
            kwargs["data"] = data
        if pagedata:
            kwargs["pagedata"] = pagedata
        if useragent:
            kwargs["useragent"] = useragent
        logging.debug("Submitting Turnstile captcha to 2captcha (sitekey=%s)", sitekey)
        result = self._client.turnstile(sitekey=sitekey, url=url, **kwargs)
        return result["code"]

    def solve_hcaptcha(self, *, url, sitekey):
        logging.debug("Submitting hCaptcha to 2captcha (sitekey=%s)", sitekey)
        result = self._client.hcaptcha(sitekey=sitekey, url=url)
        return result["code"]

    def solve_recaptcha(self, *, url, sitekey, version="v2", action=None):
        kwargs = {"version": version}
        if action:
            kwargs["action"] = action
        logging.debug("Submitting reCAPTCHA %s to 2captcha (sitekey=%s)", version, sitekey)
        result = self._client.recaptcha(sitekey=sitekey, url=url, **kwargs)
        return result["code"]


def _int_env(name):
    value = os.environ.get(name)
    return int(value) if value else None


def get_solver() -> TwoCaptchaSolver:
    api_key = os.environ.get("TWOCAPTCHA_API_KEY") or os.environ.get("CAPTCHA_SOLVER_API_KEY")
    if not api_key:
        raise Exception("The 2captcha solver requires the 'TWOCAPTCHA_API_KEY' "
                        "environment variable to be set.")

    client_opts = {}
    server = os.environ.get("TWOCAPTCHA_SERVER")
    if server:
        client_opts["server"] = server
    for env_name, opt_name in (("TWOCAPTCHA_SOFT_ID", "softId"),
                               ("TWOCAPTCHA_DEFAULT_TIMEOUT", "defaultTimeout"),
                               ("TWOCAPTCHA_POLLING_INTERVAL", "pollingInterval")):
        value = _int_env(env_name)
        if value is not None:
            client_opts[opt_name] = value

    return TwoCaptchaSolver(api_key, **client_opts)
