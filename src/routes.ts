import { v1 as UUIDv1 } from 'uuid'
import sessions, { SessionsCacheItem } from './session'
import { RequestContext } from './types'
import log from './log'
import { SetCookie, Request, Headers, HttpMethod, Overrides, Cookie } from 'puppeteer'
import { TimeoutError } from 'puppeteer/Errors'
import getCaptchaSolver, { CaptchaType } from './captcha'
import * as Puppeteer from "puppeteer-extra/dist/puppeteer";

export interface BaseAPICall {
  cmd: string
}

interface BaseSessionsAPICall extends BaseAPICall {
  session?: string
}

interface SessionsCreateAPICall extends BaseSessionsAPICall {
  userAgent?: string,
  cookies?: SetCookie[],
  headers?: Headers
  maxTimeout?: number
  proxy?: any
}

interface BaseRequestAPICall extends BaseAPICall {
  url: string
  method?: HttpMethod
  postData?: string
  session?: string
  userAgent?: string
  maxTimeout?: number
  cookies?: SetCookie[],
  headers?: Headers
  proxy?: any, // TODO: use interface not any
  download?: boolean
  returnOnlyCookies?: boolean
}


interface Routes {
  [key: string]: (ctx: RequestContext, params: BaseAPICall) => void | Promise<void>
}

interface ChallengeResolutionResultT {
  url: string
  status: number,
  headers?: Headers,
  response: string,
  cookies: object[]
  userAgent: string
}

interface ChallengeResolutionT {
  status?: string
  message: string
  result: ChallengeResolutionResultT
}

interface OverrideResolvers {
  method?: (request: Request) => HttpMethod,
  postData?: (request: Request) => string,
  headers?: (request: Request) => Headers
}

type OverridesProps =
  'method' |
  'postData' |
  'headers'

// We always set a Windows User-Agent because ARM builds are detected by CloudFlare
const DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
const CHALLENGE_SELECTORS = ['#trk_jschal_js', '.ray_id', '.attack-box']
const TOKEN_INPUT_NAMES = ['g-recaptcha-response', 'h-captcha-response']

async function interceptResponse(page: Puppeteer.Page, callback: (payload: ChallengeResolutionT) => any) {
  const client = await page.target().createCDPSession();
  await client.send('Fetch.enable', {
    patterns: [
      {
        urlPattern: '*',
        resourceType: 'Document',
        requestStage: 'Response',
      },
    ],
  });

  client.on('Fetch.requestPaused', async (e) => {
    log.debug('Fetch.requestPaused. Checking if the response has valid cookies')
    let headers = e.responseHeaders || []

    let cookies = await page.cookies();
    log.debug(cookies)

    if (cookies.filter((c: Cookie) => c.name === 'cf_clearance').length > 0) {
      log.debug('Aborting request and return cookies. valid cookies found')
      await client.send('Fetch.failRequest', {requestId: e.requestId, errorReason: 'Aborted'})

      let status = 'ok'
      let message = ''
      const payload: ChallengeResolutionT = {
        status,
        message,
        result: {
          url: page.url(),
          status: e.status,
          headers: headers.reduce((a: any, x: { name: any; value: any }) => ({ ...a, [x.name]: x.value }), {}),
          response: null,
          cookies: cookies,
          userAgent: ''
        }
      }

      callback(payload);
    } else {
      log.debug('Continuing request. no valid cookies found')
      await client.send('Fetch.continueRequest', {requestId: e.requestId})
    }
  });
}

async function resolveChallenge(ctx: RequestContext, { url, maxTimeout, proxy, download, returnOnlyCookies }: BaseRequestAPICall, page: Puppeteer.Page): Promise<ChallengeResolutionT | void> {

  maxTimeout = maxTimeout || 60000
  let status = 'ok'
  let message = ''

  if (proxy) {
    log.debug("Apply proxy");
    if (proxy.username)
      await page.authenticate({ username: proxy.username, password: proxy.password });
  }

  log.debug(`Navigating to... ${url}`)
  let response = await page.goto(url, { waitUntil: 'domcontentloaded' })

  // look for challenge
  if (response.headers().server.startsWith('cloudflare')) {
    log.info('Cloudflare detected')

    if (await page.$('.cf-error-code')) {
      await page.close()
      return ctx.errorResponse('Cloudflare has blocked this request (Code 1020 Detected).')
    }

    if (response.status() > 400) {
      // detect cloudflare wait 5s
      for (const selector of CHALLENGE_SELECTORS) {
        const cfChallengeElem = await page.$(selector)
        if (cfChallengeElem) {
          log.html(await page.content())
          log.debug('Waiting for Cloudflare challenge...')

          let interceptingResult: ChallengeResolutionT;
          if (returnOnlyCookies) { //If we just want to get the cookies, intercept the response before we get the content/body (just cookies and headers)
            await interceptResponse(page, async function(payload){
              interceptingResult = payload;
            });
          }

          // TODO: find out why these pages hang sometimes
          while (Date.now() - ctx.startTimestamp < maxTimeout) {
            await page.waitFor(1000)
            try {
              // catch exception timeout in waitForNavigation
              response = await page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 5000 })
            } catch (error) { }

            if (returnOnlyCookies && interceptingResult) {
              await page.close();
              return interceptingResult;
            }

            try {
              // catch Execution context was destroyed
              const cfChallengeElem = await page.$(selector)
              if (!cfChallengeElem) { break }
              log.debug('Found challenge element again...')
            } catch (error)
            { }

            response = await page.reload({ waitUntil: 'domcontentloaded' })
            log.debug('Reloaded page...')
          }

          if (Date.now() - ctx.startTimestamp >= maxTimeout) {
            ctx.errorResponse(`Maximum timeout reached. maxTimeout=${maxTimeout} (ms)`)
            return
          }

          log.debug('Validating HTML code...')
          break
        } else {
          log.debug(`No '${selector}' challenge element detected.`)
        }
      }
    }

    // it seems some captcha pages return 200 sometimes
    if (await page.$('input[name="cf_captcha_kind"]')) {
      const captchaSolver = getCaptchaSolver()
      if (captchaSolver) {
        const captchaStartTimestamp = Date.now()
        const challengeForm = await page.$('#challenge-form')
        if (challengeForm) {
          log.html(await page.content())
          const captchaTypeElm = await page.$('input[name="cf_captcha_kind"]')
          const cfCaptchaType: string = await captchaTypeElm.evaluate((e: any) => e.value)
          const captchaType: CaptchaType = (CaptchaType as any)[cfCaptchaType]
          if (!captchaType) { return ctx.errorResponse('Unknown captcha type!') }

          let sitekey = null
          if (captchaType != 'hCaptcha' && process.env.CAPTCHA_SOLVER != 'hcaptcha-solver') {
            const sitekeyElem = await page.$('*[data-sitekey]')
            if (!sitekeyElem) { return ctx.errorResponse('Could not find sitekey!') }
            sitekey = await sitekeyElem.evaluate((e) => e.getAttribute('data-sitekey'))
          }

          log.info('Waiting to receive captcha token to bypass challenge...')
          const token = await captchaSolver({
            url,
            sitekey,
            type: captchaType
          })

          if (!token) {
            await page.close()
            return ctx.errorResponse('Token solver failed to return a token.')
          }

          for (const name of TOKEN_INPUT_NAMES) {
            const input = await page.$(`textarea[name="${name}"]`)
            if (input) { await input.evaluate((e: HTMLTextAreaElement, token) => { e.value = token }, token) }
          }

          // ignore preset event listeners on the form
          await page.evaluate(() => {
            window.addEventListener('submit', (e) => { event.stopPropagation() }, true)
          })

          // it seems some sites obfuscate their challenge forms
          // TODO: look into how they do it and come up with a more solid solution
          try {
            // this element is added with js and we want to wait for all the js to load before submitting
            await page.waitForSelector('#challenge-form [type=submit]', { timeout: 5000 })
          } catch (err) {
            if (err instanceof TimeoutError) {
              log.debug(`No '#challenge-form [type=submit]' element detected.`)
            }
          }

          // calculates the time it took to solve the captcha
          const captchaSolveTotalTime = Date.now() - captchaStartTimestamp

          // generates a random wait time
          const randomWaitTime = (Math.floor(Math.random() * 20) + 10) * 1000

          // waits, if any, time remaining to appear human but stay as fast as possible
          const timeLeft = randomWaitTime - captchaSolveTotalTime
          if (timeLeft > 0) { await page.waitFor(timeLeft) }

          let interceptingResult: ChallengeResolutionT;
          if (returnOnlyCookies) { //If we just want to get the cookies, intercept the response before we get the content/body (just cookies and headers)
            await interceptResponse(page, async function(payload){
              interceptingResult = payload;
            });
          }

          // submit captcha response
          challengeForm.evaluate((e: HTMLFormElement) => e.submit())
          response = await page.waitForNavigation({ waitUntil: 'domcontentloaded' })

          if (returnOnlyCookies && interceptingResult) {
            await page.close();
            return interceptingResult;
          }
        }
      } else {
        status = 'warning'
        message = 'Captcha detected but no automatic solver is configured.'
      }
    }
  }

  const payload: ChallengeResolutionT = {
    status,
    message,
    result: {
      url: page.url(),
      status: response.status(),
      headers: response.headers(),
      response: null,
      cookies: await page.cookies(),
      userAgent: await page.evaluate(() => navigator.userAgent)
    }
  }

  if (download) {
    // for some reason we get an error unless we reload the page
    // has something to do with a stale buffer and this is the quickest
    // fix since I am short on time
    response = await page.goto(url, { waitUntil: 'domcontentloaded' })
    payload.result.response = (await response.buffer()).toString('base64')
  } else {
    payload.result.response = await page.content()
  }

  // make sure the page is closed because if it isn't and error will be thrown
  // when a user uses a temporary session, the browser make be quit before
  // the page is properly closed.
  await page.close()

  return payload
}

function mergeSessionWithParams({ defaults }: SessionsCacheItem, params: BaseRequestAPICall): BaseRequestAPICall {
  const copy = { ...defaults, ...params }

  // custom merging logic
  copy.headers = { ...defaults.headers || {}, ...params.headers || {} } || null

  return copy
}

async function setupPage(ctx: RequestContext, params: BaseRequestAPICall, browser: Puppeteer.Browser): Promise<Puppeteer.Page> {
  const page = await browser.newPage()

  // merge session defaults with params
  const { method, postData, userAgent, headers, cookies } = params

  let overrideResolvers: OverrideResolvers = {}

  if (method !== 'GET') {
    log.debug(`Setting method to ${method}`)
    overrideResolvers.method = request => method
  }

  if (postData) {
    log.debug(`Setting body data to ${postData}`)
    overrideResolvers.postData = request => postData
  }

  if (userAgent) {
    log.debug(`Using custom UA: ${userAgent}`)
    await page.setUserAgent(userAgent)
  } else {
    await page.setUserAgent(DEFAULT_USER_AGENT)
  }

  if (headers) {
    log.debug(`Adding custom headers: ${JSON.stringify(headers, null, 2)}`,)
    overrideResolvers.headers = request => Object.assign(request.headers(), headers)
  }

  if (cookies) {
    log.debug(`Setting custom cookies: ${JSON.stringify(cookies, null, 2)}`,)
    await page.setCookie(...cookies)
  }

  // if any keys have been set on the object
  if (Object.keys(overrideResolvers).length > 0) {
    log.debug(overrideResolvers)
    let callbackRunOnce = false
    const callback = (request: Request) => {

      if (callbackRunOnce || !request.isNavigationRequest()) {
        request.continue()
        return
      }

      callbackRunOnce = true
      const overrides: Overrides = {}

      Object.keys(overrideResolvers).forEach((key: OverridesProps) => {
        // @ts-ignore
        overrides[key] = overrideResolvers[key](request)
      });

      log.debug(overrides)

      request.continue(overrides)
    }

    await page.setRequestInterception(true)
    page.on('request', callback)
  }

  return page
}

const browserRequest = async (ctx: RequestContext, params: BaseRequestAPICall) => {
  const oneTimeSession = params.session === undefined
  const sessionId = params.session || UUIDv1()
  const session = oneTimeSession
    ? await sessions.create(sessionId, {
      userAgent: params.userAgent,
      oneTimeSession
    })
    : sessions.get(sessionId)

  if (session === false) {
    return ctx.errorResponse('This session does not exist. Use \'list_sessions\' to see all the existing sessions.')
  }

  params = mergeSessionWithParams(session, params)

  try {
    const page = await setupPage(ctx, params, session.browser)
    const data = await resolveChallenge(ctx, params, page)

    if (data) {
      const { status } = data
      delete data.status
      ctx.successResponse(data.message, {
        ...(oneTimeSession ? {} : { session: sessionId }),
        ...(status ? { status } : {}),
        solution: data.result
      })
    }
  } catch (error) {
    log.error(error)
    return ctx.errorResponse("Unable to process browser request. Error: " + error)
  } finally {
    if (oneTimeSession) { sessions.destroy(sessionId) }
  }
}

export const routes: Routes = {
  'sessions.create': async (ctx, { session, ...options }: SessionsCreateAPICall) => {
    session = session || UUIDv1()
    const { browser } = await sessions.create(session, options)
    if (browser) { ctx.successResponse('Session created successfully.', { session }) }
  },
  'sessions.list': (ctx) => {
    ctx.successResponse(null, { sessions: sessions.list() })
  },
  'sessions.destroy': async (ctx, { session }: BaseSessionsAPICall) => {
    if (await sessions.destroy(session)) { return ctx.successResponse('The session has been removed.') }
    ctx.errorResponse('This session does not exist.')
  },
  'request.get': async (ctx, params: BaseRequestAPICall) => {
    params.method = 'GET'
    if (params.postData) {
      return ctx.errorResponse('Cannot use "postBody" when sending a GET request.')
    }
    await browserRequest(ctx, params)
  },
  'request.post': async (ctx, params: BaseRequestAPICall) => {
    params.method = 'POST'

    if (!params.postData) {
      return ctx.errorResponse('Must send param "postBody" when sending a POST request.')
    }

    await browserRequest(ctx, params)
  },
  'request.cookies': async (ctx, params: BaseRequestAPICall) => {
    params.returnOnlyCookies = true
    params.method = 'GET'
    if (params.postData) {
      return ctx.errorResponse('Cannot use "postBody" when sending a GET request.')
    }
    await browserRequest(ctx, params)
  },
}

export default async function Router(ctx: RequestContext, params: BaseAPICall): Promise<void> {
  const route = routes[params.cmd]
  if (route) { return await route(ctx, params) }
  return ctx.errorResponse(`The command '${params.cmd}' is invalid.`)
}
