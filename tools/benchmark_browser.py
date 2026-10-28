"""Compare local browser overhead: python tools/benchmark_browser.py --baseline <git-ref>.

Opens Chrome with the existing undetected driver and a temporary profile.
Only navigates to data URLs; driver setup may download ChromeDriver.
This does not measure challenge success or cold browser startup.
"""
import argparse
import importlib.util
import logging
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
os.environ['HEADLESS'] = 'false'
import utils
import flaresolverr_service as current
from dtos import V1RequestBase
from selenium.webdriver.common.by import By

logging.basicConfig(level=logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, help='Git ref containing the original service')
    args = parser.parse_args()
    baseline = importlib.util.module_from_spec(importlib.util.spec_from_loader('baseline_service', loader=None))
    source = subprocess.check_output(['git', 'show', args.baseline + ':src/flaresolverr_service.py'], cwd=root)
    exec(compile(source, 'baseline_service.py', 'exec'), baseline.__dict__)
    driver = utils.get_webdriver()
    try:
        utils.USER_AGENT = driver.execute_script('return navigator.userAgent')
        req = V1RequestBase({'url': 'data:text/html,' + quote('<html><head><title>Example</title></head><body>Example</body></html>'),
                             'maxTimeout': 60000})
        times = {'before': [], 'after': []}
        for iteration in range(16):
            results = []
            pairs = [('before', baseline), ('after', current)]
            if iteration % 2:
                pairs.reverse()
            for label, module in pairs:
                start = time.perf_counter()
                result = utils.object_to_dict(module._evil_logic(req, driver, 'GET'))
                elapsed = time.perf_counter() - start
                if iteration >= 2:
                    times[label].append(elapsed * 1000)
                results.append(result)
            assert results[0] == results[1], results
        fixtures = ['<p>normal</p>', '<div id="cf-challenge-running"></div>',
                    '<div class="ray_id"></div>', '<div id="turnstile-wrapper"></div>',
                    '<table><tr><td class="info"><div id="js_info"></div></td></tr></table>',
                    '<div class="vc"><div class="text-box"><h2>challenge</h2></div></div>',
                    '<div id="cf-error-details"><div class="cf-error-overview"><h1>denied</h1></div></div>']
        fixtures.extend(path.read_text() for path in (root / 'html_samples').glob('*.html'))
        for html in fixtures:
            driver.get('data:text/html,' + quote(html))
            for selectors in [current.ACCESS_DENIED_SELECTORS, current.CHALLENGE_SELECTORS]:
                individual = any(driver.find_elements(By.CSS_SELECTOR, selector) for selector in selectors)
                grouped = bool(driver.find_elements(By.CSS_SELECTOR, ', '.join(selectors)))
                assert individual == grouped
        print('Driver:', type(driver).__module__, 'Chrome:', driver.capabilities.get('browserVersion'))
        print('Identical baseline/updated results: 16 pairs; selector parity fixtures:', len(fixtures))
        for label, values in times.items():
            print(label, 'median_ms=', round(statistics.median(values), 2), 'n=', len(values))
    finally:
        driver.quit()


if __name__ == '__main__':
    main()
