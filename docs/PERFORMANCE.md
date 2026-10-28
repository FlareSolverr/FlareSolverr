# Browser overhead optimization

The existing vendored undetected_chromedriver, browser options, request/session
lifecycle, challenge waits and verification actions are retained. No browser
pooling or profile sharing is introduced. HTTP response serialization is unchanged.

Initial access-denied and challenge detection now use two CSS selector-list
queries instead of twelve separate WebDriver commands on a normal page. A selector
list matches any of its members. Challenge disappearance waits still check each
original selector. The challenge detection log now reports the matching selector
list rather than an individual selector.

Request/response logging only serializes objects when its log level is enabled.
At INFO, this avoids an extra JSON round trip and string formatting of response
HTML and screenshots. LOG_HTML only fetches HTML for logging when DEBUG is enabled;
response HTML is still fetched as before when requested by the API.

## Validation

Install requirements.txt and test-requirements.txt in a virtual environment, then:

```sh
python -m unittest discover -s src -p test_performance.py -v
python tools/benchmark_browser.py --baseline cc2224b
```

The benchmark opens a separate Chrome window with a temporary profile using the
project's get_webdriver(). It may download ChromeDriver. It compares the original
and updated service against local data URLs, alternates execution order, excludes
two warmup pairs and checks exact result equality. It also compares individual
and grouped selector detection on synthetic HTML and repository HTML samples.

Measured locally on macOS with Chrome 156.0.8078.48:

| Measurement | Original | Updated |
| --- | ---: | ---: |
| Median local page handling, 14 measured runs each | 50.04 ms | 29.74 ms |
| Initial CSS queries on a page without a challenge | 12 | 2 |

All 16 before/after result pairs matched. Selector detection matched on 11 HTML
fixtures. Ten new offline regression tests passed. Eleven existing API tests
(index, health, routing, validation and session commands) also passed with browser
creation mocked.

The approximately 41% reduction applies only to this local, already-running-browser
measurement. Browser startup, external network requests, live challenge handling,
concurrent load and successful challenge rates were not measured. The full existing
site suite requires live sites and proxy services and was not run.
