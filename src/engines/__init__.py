"""Engine registry. Selects the browser backend from the `BROWSER_ENGINE` env var."""

import logging
import os

from engines.base import Engine

_UC_ALIASES = ('uc', 'undetected', 'undetected-chromedriver', 'selenium')
_SCRAPLING_ALIASES = ('scrapling', 'patchright')

DEFAULT_ENGINE = 'uc'


def get_config_engine_name() -> str:
    return os.environ.get('BROWSER_ENGINE', DEFAULT_ENGINE).strip().lower()


def create_engine(name: str = None) -> Engine:
    """Instantiate the configured engine.

    Constructors must stay cheap: this runs at import time, before logging is
    configured and before the web server starts. Anything expensive belongs in
    `Engine.startup()`.
    """
    name = (name or get_config_engine_name()) or DEFAULT_ENGINE

    if name in _UC_ALIASES:
        from engines.undetected import UndetectedChromeEngine
        return UndetectedChromeEngine()

    if name in _SCRAPLING_ALIASES:
        from engines.scrapling import ScraplingEngine
        return ScraplingEngine()

    raise Exception(
        f"Unknown BROWSER_ENGINE '{name}'. Valid values: "
        f"{', '.join(_UC_ALIASES[:1] + _SCRAPLING_ALIASES[:1])}."
    )
