"""Engine registry. Selects the browser backend from the `BROWSER_ENGINE` env var."""

import os
import sys

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
        if sys.version_info < (3, 10):
            raise Exception("BROWSER_ENGINE='scrapling' requires Python 3.10 or newer "
                            f"(running {sys.version.split()[0]}). Use BROWSER_ENGINE=uc instead.")
        try:
            from engines.scrapling_engine import ScraplingEngine
        except ImportError as e:
            raise Exception(
                "BROWSER_ENGINE='scrapling' needs the Scrapling dependencies: "
                "`pip install -r requirements-scrapling.txt`. They are not installed on "
                "32-bit platforms, because playwright/patchright publish no driver for "
                f"them -- use BROWSER_ENGINE=uc there. Original error: {e}") from e
        return ScraplingEngine()

    raise Exception(
        f"Unknown BROWSER_ENGINE '{name}'. Valid values: "
        f"{', '.join(_UC_ALIASES[:1] + _SCRAPLING_ALIASES[:1])}."
    )
