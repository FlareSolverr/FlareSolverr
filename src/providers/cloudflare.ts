import {Page, HTTPResponse} from 'puppeteer'

import log from "../services/log";

/**
 *  This class contains the logic to solve protections provided by CloudFlare
 **/

const BAN_SELECTORS: string[] = [];
const CHALLENGE_SELECTORS: string[] = [
    // todo: deprecate  '#trk_jschal_js', '#cf-please-wait'
    '#cf-challenge-running', '#trk_jschal_js', '#cf-please-wait', // CloudFlare
    '#link-ddg', // DDoS-GUARD
    'td.info #js_info' // Custom CloudFlare for EbookParadijs, Film-Paleis, MuziekFabriek and Puur-Hollands
];
const CAPTCHA_SELECTORS: string[] = [
    // todo: deprecate 'input[name="cf_captcha_kind"]'
    '#cf-challenge-hcaptcha-wrapper', '#cf-norobot-container', 'input[name="cf_captcha_kind"]'
];

export default async function resolveChallenge(url: string, page: Page, response: HTTPResponse): Promise<HTTPResponse> {

  // look for challenge and return fast if not detected
  let cfDetected = response.headers().server &&
      (response.headers().server.startsWith('cloudflare') || response.headers().server.startsWith('ddos-guard'));
  if (cfDetected) {
    if (response.status() == 403 || response.status() == 503) {
      cfDetected = true; // Defected CloudFlare and DDoS-GUARD
    } else if (response.headers().vary && response.headers().vary.trim() == 'Accept-Encoding,User-Agent' &&
        response.headers()['content-encoding'] && response.headers()['content-encoding'].trim() == 'br') {
      cfDetected = true; // Detected Custom CloudFlare for EbookParadijs, Film-Paleis, MuziekFabriek and Puur-Hollands
    } else {
      cfDetected = false;
    }
  }

  if (cfDetected) {
    log.info('Cloudflare detected');
  } else {
    log.info('Cloudflare not detected');
    return response;
  }

  if (await findAnySelector(page, BAN_SELECTORS)) {
    throw new Error('Cloudflare has blocked this request. Probably your IP is banned for this site, check in your web browser.');
  }

  // find Cloudflare selectors
  let selectorFound = false;
  let selector: string = await findAnySelector(page, CHALLENGE_SELECTORS)
  if (selector) {
    selectorFound = true;
    log.debug(`Javascript challenge element '${selector}' detected.`)
    log.debug('Waiting for Cloudflare challenge...')

    while (true) {
      try {

        selector = await findAnySelector(page, CHALLENGE_SELECTORS)
        if (!selector) {
          // solved!
          log.debug('Challenge element not found')
          break

        } else {
          log.debug(`Javascript challenge element '${selector}' detected.`)

          // check for CAPTCHA challenge
          if (await findAnySelector(page, CAPTCHA_SELECTORS)) {
            // captcha detected
            break
          }

          // new Cloudflare Challenge #cf-please-wait
          const displayStyle = await page.evaluate((selector) => {
            return getComputedStyle(document.querySelector(selector)).getPropertyValue("display");
          }, selector);
          if (displayStyle == "none") {
            // spinner is hidden, could be a captcha or not
            log.debug('Challenge element is hidden')
            // wait until redirecting disappears
            while (true) {
              try {
                await page.waitForTimeout(1000)
                const displayStyle2 = await page.evaluate(() => {
                  return getComputedStyle(document.querySelector('#cf-spinner-redirecting')).getPropertyValue("display");
                });
                if (displayStyle2 == "none") {
                  break // hCaptcha detected
                }
              } catch (error) {
                break // redirection completed
              }
            }
            break
          } else {
            log.debug('Challenge element is visible')
          }
        }
        log.debug('Found challenge element again')

      } catch (error)
      {
        log.debug("Unexpected error: " + error);
        if (!error.toString().includes("Execution context was destroyed")) {
          break
        }
      }

      log.debug('Waiting for Cloudflare challenge...')
      await page.waitForTimeout(1000)
    }

    log.debug('Validating HTML code...')
  } else {
    log.debug(`No challenge element detected.`)
  }

  // check for CAPTCHA challenge
  if (await findAnySelector(page, CAPTCHA_SELECTORS)) {
    log.info('CAPTCHA challenge detected');
    throw new Error('FlareSolverr can not resolve CAPTCHA challenges. Since the captcha doesn\'t always appear, you may have better luck with the next request.');

    // const captchaSolver = getCaptchaSolver()
    // if (captchaSolver) {
    //     // to-do: get the params
    //     log.info('Waiting to receive captcha token to bypass challenge...')
    //     const token = await captchaSolver({
    //       url,
    //       sitekey,
    //       type: captchaType
    //     })
    //     log.debug(`Token received: ${token}`);
    //     // to-do: send the token
    //   }
    // } else {
    //   throw new Error('Captcha detected but no automatic solver is configured.');
    // }
  } else {
    if (!selectorFound)
    {
      throw new Error('No challenge selectors found, unable to proceed.')
    } else {
      log.info('Challenge solved');
    }
  }

  return response;
}

async function findAnySelector(page: Page, selectors: string[]) {
  for (const selector of selectors) {
    const cfChallengeElem = await page.$(selector)
    if (cfChallengeElem) {
      return selector;
    }
  }
  return null;
}
