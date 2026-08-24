"""
Browser engine abstraction.

FlareSolverr's `/v1` contract is engine-agnostic: give it a URL and it hands back the
final URL, the HTTP status, the headers, the cookies and the rendered HTML. Everything
that actually drives a browser lives behind the `Engine` protocol below, so a backend
can be swapped with the `BROWSER_ENGINE` environment variable without the bottle
routes, the DTOs or the Prometheus plugin knowing about it.

Implementations live next to this file:
  - `undetected.py`  Selenium + undetected-chromedriver (the historical engine)
  - `scrapling.py`   Scrapling's `AsyncStealthySession` (patchright + Chromium)
"""

from typing import List, Optional, Protocol, Tuple

from dtos import ChallengeResolutionT, V1RequestBase


class Engine(Protocol):
    """A browser backend capable of resolving challenges and holding sessions."""

    name: str

    def startup(self) -> None:
        """Verify the browser is usable and warm up anything expensive.

        Called once from `flaresolverr.py` before the web server starts listening.
        Must raise (or `sys.exit`) if the browser is unusable, so the container
        fails fast instead of answering requests it cannot serve.
        """
        ...

    def shutdown(self) -> None:
        """Release every browser resource held by this engine.

        Must be idempotent: it is called on interpreter exit and may also be
        called explicitly.
        """
        ...

    def user_agent(self) -> str:
        """The User-Agent that this engine's browser sends.

        Clients must send the same User-Agent as the one that earned a
        `cf_clearance` cookie, otherwise Cloudflare re-challenges them, so this
        value is part of the public contract (`GET /` and `solution.userAgent`).
        """
        ...

    def create_session(self, session_id: Optional[str], proxy: Optional[dict]) -> Tuple[str, bool]:
        """Create a session, returning its id and whether it was freshly created.

        Idempotent: asking for an existing id returns `(session_id, False)`
        instead of replacing the session.
        """
        ...

    def list_sessions(self) -> List[str]:
        """The ids of every live session."""
        ...

    def destroy_session(self, session_id: str) -> bool:
        """Close a session's browser. Returns False if the id was not found."""
        ...

    def solve(self, req: V1RequestBase, method: str) -> ChallengeResolutionT:
        """Navigate to `req.url`, clear any challenge, and build the solution.

        `method` is 'GET' or 'POST'. Enforcing `req.maxTimeout` is the engine's
        responsibility, because how a timeout is applied (and how the browser is
        cleaned up afterwards) is engine-specific.
        """
        ...
