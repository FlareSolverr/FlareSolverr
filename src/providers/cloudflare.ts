import {Response} from 'puppeteer'
import {Page} from "puppeteer-extra/dist/puppeteer";

import log from "../log";
import getCaptchaSolver, {CaptchaType} from "../captcha";

/**
 *  This class contains the logic to solve protections provided by CloudFlare
**/

const CHALLENGE_SELECTORS = ['#trk_jschal_js', '.ray_id', '.attack-box', '#cf-please-wait'];
const TOKEN_INPUT_NAMES = ['g-recaptcha-response', 'h-captcha-response'];

export default async function resolveChallenge(url: string, page: Page, response: Response): Promise<Response> {

  // look for challenge and return fast if not detected
  if (!response.headers().server.startsWith('cloudflare')) {
    log.info('Cloudflare not detected');
    return response;
  }
  log.info('Cloudflare detected');

  if (await page.$('span[data-translate="error"]') || (await page.content()).includes('error code: 1020')) {
    throw new Error('Cloudflare has blocked this request. Probably your IP is banned for this site, check in your web browser.')
  }

  let selectorFoundCount = 0;
  if (response.status() > 400) {
    // detect cloudflare wait 5s
    for (const selector of CHALLENGE_SELECTORS) {
      const cfChallengeElem = await page.$(selector)
      if (cfChallengeElem) {
        selectorFoundCount++
        log.debug(`Javascript challenge element '${selector}' detected.`)
        log.debug('Waiting for Cloudflare challenge...')

        while (true) {
          try {
            // catch Execution context was destroyed
            const cfChallengeElem = await page.$(selector)
            if (!cfChallengeElem) {
              // solved!
              log.debug('Challenge element not found.')
              break
            } else {
              // new Cloudflare Challenge #cf-please-wait
              const displayStyle = await page.evaluate((selector) => {
                return getComputedStyle(document.querySelector(selector)).getPropertyValue("display");
              }, selector);
              if (displayStyle == "none") {
                // spinner is hidden, could be a captcha or not
                log.debug('Challenge element is hidden.')
                // wait until redirecting disappears
                while (true) {
                  try {
                    await page.waitFor(1000)
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
                log.debug('Challenge element is visible.')
              }
            }
            log.debug('Found challenge element again.')
          } catch (error)
          {
            log.debug("Unexpected error: " + error);
            if (!error.toString().includes("Execution context was destroyed")) {
              break
            }
          }

          log.debug('Waiting for Cloudflare challenge...')
          await page.waitFor(1000)
        }

        log.debug('Validating HTML code...')
        break
      } else {
        log.debug(`No '${selector}' challenge element detected.`)
      }
    }
    log.debug("Javascript challenge selectors found: " + selectorFoundCount + ", total selectors: " + CHALLENGE_SELECTORS.length)
  } else {
    // some sites use cloudflare but there is no challenge
    log.debug(`Javascript challenge not detected. Status code: ${response.status()}`);
    selectorFoundCount = 1;
  }

  // it seems some captcha pages return 200 sometimes
  if (await page.$('input[name="cf_captcha_kind"]')) {
    log.info('Captcha challenge detected.');
    const captchaSolver = getCaptchaSolver()
    if (captchaSolver) {
      const captchaStartTimestamp = Date.now()
      const challengeForm = await page.$('#challenge-form')
      if (challengeForm) {
        const captchaTypeElm = await page.$('input[name="cf_captcha_kind"]')
        const cfCaptchaType: string = await captchaTypeElm.evaluate((e: any) => e.value)
        const captchaType: CaptchaType = (CaptchaType as any)[cfCaptchaType]
        if (!captchaType) {
          throw new Error('Unknown captcha type!');
        }

        let sitekey = null
        if (captchaType != 'hCaptcha' && process.env.CAPTCHA_SOLVER != 'hcaptcha-solver') {
          const sitekeyElem = await page.$('*[data-sitekey]')
          if (!sitekeyElem) {
            throw new Error('Could not find sitekey!');
          }
          sitekey = await sitekeyElem.evaluate((e) => e.getAttribute('data-sitekey'))
        }

        log.info('Waiting to receive captcha token to bypass challenge...')
        const token = await captchaSolver({
          url,
          sitekey,
          type: captchaType
        })
        log.debug(`Token received: ${token}`);
        if (!token) {
          throw new Error('Token solver failed to return a token.')
        }

        let responseFieldsFoundCount = 0;
        for (const name of TOKEN_INPUT_NAMES) {
          const input = await page.$(`textarea[name="${name}"]`)
          if (input) {
            responseFieldsFoundCount ++;
            log.debug(`Challenge response field '${name}' found in challenge form.`);
            await input.evaluate((e: HTMLTextAreaElement, token) => { e.value = token }, token);
          }
        }
        if (responseFieldsFoundCount == 0) {
          throw new Error('Challenge response field not found in challenge form.');
        }

        // ignore preset event listeners on the form
        await page.evaluate(() => {
          window.addEventListener('submit', (e) => { e.stopPropagation() }, true)
        })

        // it seems some sites obfuscate their challenge forms
        // TODO: look into how they do it and come up with a more solid solution
        try {
          // this element is added with js and we want to wait for all the js to load before submitting
          await page.waitForSelector('#challenge-form', { timeout: 10000 })
        } catch (err) {
          throw new Error("No '#challenge-form' element detected.");
        }

        // calculates the time it took to solve the captcha
        const captchaSolveTotalTime = Date.now() - captchaStartTimestamp

        // generates a random wait time
        const randomWaitTime = (Math.floor(Math.random() * 10) + 10) * 1000

        // waits, if any, time remaining to appear human but stay as fast as possible
        const timeLeft = randomWaitTime - captchaSolveTotalTime
        if (timeLeft > 0) {
          log.debug(`Waiting for '${timeLeft}' milliseconds.`);
          await page.waitFor(timeLeft);
        }

        // submit captcha response
        await challengeForm.evaluate((e: HTMLFormElement) => e.submit())
        response = await page.waitForNavigation({ waitUntil: 'domcontentloaded' })

        if (await page.$('input[name="cf_captcha_kind"]')) {
          throw new Error('Captcha service failed to solve the challenge.');
        }
      }
    } else {
      throw new Error('Captcha detected but no automatic solver is configured.');
    }
  } else {
    if (selectorFoundCount == 0)
    {
      throw new Error('No challenge selectors found, unable to proceed')
    } else {
      // reload the page to make sure we get the real response
      // do not use page.reload() to avoid #162 #143
      response = await page.goto(url, { waitUntil: 'domcontentloaded' })
      await page.content()
      log.info('Challenge solved.');
    }
  }

  return response;
}
