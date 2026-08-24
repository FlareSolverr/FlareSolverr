"""
Challenge fingerprints shared by every engine.

These lists are the accumulated field knowledge of the project and cover more than
Cloudflare: DDoS-Guard, Fairlane, and several bespoke interstitials. Scrapling's own
detector only knows Cloudflare Turnstile/interstitial, so these stay in use no matter
which engine is active.
"""

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

TURNSTILE_SELECTORS = [
    "input[name='cf-turnstile-response']"
]

ACCESS_DENIED_MESSAGE = ('Cloudflare has blocked this request. '
                         'Probably your IP is banned for this site, check in your web browser.')

# Comma-joined forms, so a Playwright locator can test every selector in one round trip
CHALLENGE_SELECTOR_CSS = ', '.join(CHALLENGE_SELECTORS)
ACCESS_DENIED_SELECTOR_CSS = ', '.join(ACCESS_DENIED_SELECTORS)


def title_is_access_denied(page_title: str) -> bool:
    """Upstream matches access-denied titles by prefix."""
    return any(page_title.startswith(title) for title in ACCESS_DENIED_TITLES)


def title_is_challenge(page_title: str) -> bool:
    """Upstream matches challenge titles case-insensitively and exactly."""
    lowered = (page_title or '').lower()
    return any(title.lower() == lowered for title in CHALLENGE_TITLES)
