import {Response, Headers, Page, Browser} from 'puppeteer'
const Timeout = require('await-timeout');

import log from './log'
import {SessionsCacheItem} from "./sessions";
import {V1Request} from "../controllers/v1";
import cloudflareProvider from '../providers/cloudflare';

const sessions = require('./sessions')

export interface ChallengeResolutionResultT {
    url: string
    status: number,
    headers?: Headers,
    response: string,
    cookies: object[]
    userAgent: string
}

export interface ChallengeResolutionT {
    status?: string
    message: string
    result: ChallengeResolutionResultT
}

// interface OverrideResolvers {
//     method?: (request: Request) => HttpMethod,
//     postData?: (request: Request) => string,
//     headers?: (request: Request) => Headers
// }
//
// type OverridesProps =
//     'method' |
//     'postData' |
//     'headers'

async function resolveChallengeWithTimeout(params: V1Request, page: Page) {
    const maxTimeout = params.maxTimeout || 60000
    const timer = new Timeout();
    try {
        const promise = resolveChallenge(params, page);
        return await Promise.race([
            promise,
            timer.set(maxTimeout, `Maximum timeout reached. maxTimeout=${maxTimeout} (ms)`)
        ]);
    } finally {
        timer.clear();
    }
}

async function resolveChallenge({ url, proxy, download, returnOnlyCookies, returnRawHtml }: V1Request,
                                page: Page): Promise<ChallengeResolutionT | void> {

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

            // todo: review this functionality
            // } else if (returnRawHtml) {
            //   payload.result.response = await response.text()
        } else {
            payload.result.response = await page.content()
        }
    }

    // Add final url in result
    payload.result.url = page.url();

    // make sure the page is closed because if it isn't and error will be thrown
    // when a user uses a temporary session, the browser make be quit before
    // the page is properly closed.
    await page.close()

    return payload
}

function mergeSessionWithParams({ defaults }: SessionsCacheItem, params: V1Request): V1Request {
    const copy = { ...defaults, ...params }

    // custom merging logic
    copy.headers = { ...defaults.headers || {}, ...params.headers || {} } || null

    return copy
}

async function setupPage(params: V1Request, browser: Browser): Promise<Page> {
    const page = await browser.newPage()

    // merge session defaults with params
    const { method, postData, headers, cookies } = params

    // the user-agent is changed just for linux arm build
    await page.setUserAgent(sessions.getUserAgent())

    // todo: redo all functionality

    // let overrideResolvers: OverrideResolvers = {}
    //
    // if (method !== 'GET') {
    //   log.debug(`Setting method to ${method}`)
    //   overrideResolvers.method = request => method
    // }
    //
    // if (postData) {
    //   log.debug(`Setting body data to ${postData}`)
    //   overrideResolvers.postData = request => postData
    // }
    //
    // if (headers) {
    //   log.debug(`Adding custom headers: ${JSON.stringify(headers)}`)
    //   overrideResolvers.headers = request => Object.assign(request.headers(), headers)
    // }
    //
    // if (cookies) {
    //   log.debug(`Setting custom cookies: ${JSON.stringify(cookies)}`)
    //   await page.setCookie(...cookies)
    // }
    //
    // // if any keys have been set on the object
    // if (Object.keys(overrideResolvers).length > 0) {
    //   let callbackRunOnce = false
    //   const callback = (request: Request) => {
    //
    //     // avoid loading resources to speed up page load
    //     if(request.resourceType() == 'stylesheet' || request.resourceType() == 'font' || request.resourceType() == 'image') {
    //       request.abort()
    //       return
    //     }
    //
    //     if (callbackRunOnce || !request.isNavigationRequest()) {
    //       request.continue()
    //       return
    //     }
    //
    //     callbackRunOnce = true
    //     const overrides: Overrides = {}
    //
    //     Object.keys(overrideResolvers).forEach((key: OverridesProps) => {
    //       // @ts-ignore
    //       overrides[key] = overrideResolvers[key](request)
    //     });
    //
    //     log.debug(`Overrides: ${JSON.stringify(overrides)}`)
    //     request.continue(overrides)
    //   }
    //
    //   await page.setRequestInterception(true)
    //   page.on('request', callback)
    // }

    return page
}

export async function browserRequest(params: V1Request): Promise<ChallengeResolutionT> {
    const oneTimeSession = params.session === undefined;
    const session: SessionsCacheItem = oneTimeSession
        ? await sessions.create(null, {
            oneTimeSession: true
        })
        : sessions.get(params.session)

    if (!session) {
        throw Error('This session does not exist. Use \'list_sessions\' to see all the existing sessions.')
    }

    params = mergeSessionWithParams(session, params)

    try {
        const page = await setupPage(params, session.browser)
        return  await resolveChallengeWithTimeout(params, page)
    } catch (error) {
        throw Error("Unable to process browser request. Error: " + error)
    } finally {
        if (oneTimeSession) {
            await sessions.destroy(session.sessionId)
        }
    }
}
