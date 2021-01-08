import { v1 as UUIDv1 } from 'uuid'
import { SetCookie, Request, Response, Headers, HttpMethod, Overrides } from 'puppeteer'
import { Page, Browser } from "puppeteer-extra/dist/puppeteer";
const Timeout = require('await-timeout');

import log from './log'
import sessions, { SessionsCacheItem } from './session'
import { RequestContext } from './types'
import cloudflareProvider from './providers/cloudflare';

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

// We always set a Windows User-Agent because ARM builds are detected by Cloudflare
const DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"

async function resolveChallengeWithTimeout(ctx: RequestContext, params: BaseRequestAPICall, page: Page) {
  const maxTimeout = params.maxTimeout || 60000
  const timer = new Timeout();
  try {
    const promise = resolveChallenge(ctx, params, page);
    return await Promise.race([
      promise,
      timer.set(maxTimeout, `Maximum timeout reached. maxTimeout=${maxTimeout} (ms)`)
    ]);
  } finally {
    timer.clear();
  }
}

async function resolveChallenge(ctx: RequestContext, { url, proxy, download, returnOnlyCookies }: BaseRequestAPICall, page: Page): Promise<ChallengeResolutionT | void> {

  let status = 'ok'
  let message = ''

  if (proxy) {
    log.debug("Apply proxy");
    if (proxy.username)
      await page.authenticate({ username: proxy.username, password: proxy.password });
  }

  log.debug(`Navigating to... ${url}`)
  let response: Response = await page.goto(url, { waitUntil: 'domcontentloaded' })
  log.html(await page.content())

  // Detect protection services and solve challenges
  try {
    response = await cloudflareProvider(url, page, response);
  } catch (e) {
    status = "error";
    message = "Cloudflare " + e.toString();
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

  if (returnOnlyCookies) {
    payload.result.headers = null;
    payload.result.userAgent = null;
  } else {
    if (download) {
      // for some reason we get an error unless we reload the page
      // has something to do with a stale buffer and this is the quickest
      // fix since I am short on time
      response = await page.goto(url, { waitUntil: 'domcontentloaded' })
      payload.result.response = (await response.buffer()).toString('base64')
    } else {
      payload.result.response = await page.content()
    }
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

async function setupPage(ctx: RequestContext, params: BaseRequestAPICall, browser: Browser): Promise<Page> {
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
    const data = await resolveChallengeWithTimeout(ctx, params, page)

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
}

export default async function Router(ctx: RequestContext, params: BaseAPICall): Promise<void> {
  const route = routes[params.cmd]
  if (route) { return await route(ctx, params) }
  return ctx.errorResponse(`The command '${params.cmd}' is invalid.`)
}
