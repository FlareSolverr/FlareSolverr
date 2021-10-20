import {Response, Headers, Page} from 'puppeteer'
const Timeout = require('await-timeout');

import log from './log'
import {SessionCreateOptions, SessionsCacheItem} from "./sessions";
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

async function resolveChallengeWithTimeout(params: V1Request, session: SessionsCacheItem) {
    const maxTimeout = params.maxTimeout || 60000
    const timer = new Timeout();
    try {
        const promise = resolveChallenge(params, session);
        return await Promise.race([
            promise,
            timer.set(maxTimeout, `Maximum timeout reached. maxTimeout=${maxTimeout} (ms)`)
        ]);
    } finally {
        timer.clear();
    }
}

async function resolveChallenge(params: V1Request, session: SessionsCacheItem): Promise<ChallengeResolutionT | void> {
    try {
        let status = 'ok'
        let message = ''

        const page: Page = await session.browser.newPage()

        // the user-agent is changed just for linux arm build
        await page.setUserAgent(sessions.getUserAgent())

        // set the proxy
        if (params.proxy) {
            log.debug(`Using proxy: ${params.proxy.url}`);
            // todo: credentials are not working
            // if (params.proxy.username) {
            //     await page.authenticate({
            //         username: params.proxy.username,
            //         password: params.proxy.password
            //     });
            // }
        }

        // go to the page
        log.debug(`Navigating to... ${params.url}`)
        let response: Response = await gotoPage(params, page);

        // set cookies
        if (params.cookies) {
            for (const cookie of params.cookies) {
                // the other fields in the cookie can cause issues
                await page.setCookie({
                    "name": cookie.name,
                    "value": cookie.value
                })
            }
            // reload the page
            response = await gotoPage(params, page);
        }

        // log html in debug mode
        log.html(await page.content())

        // detect protection services and solve challenges
        try {
            response = await cloudflareProvider(params.url, page, response);

            // is response is ok
            // reload the page to be sure we get the real page
            log.debug("Reloading the page")
            response = await gotoPage(params, page);

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
                userAgent: sessions.getUserAgent()
            }
        }

        if (params.returnOnlyCookies) {
            payload.result.headers = null;
            payload.result.userAgent = null;
        } else {
            payload.result.response = await page.content()
        }

        // make sure the page is closed because if it isn't and error will be thrown
        // when a user uses a temporary session, the browser make be quit before
        // the page is properly closed.
        await page.close()

        return payload
    } catch (e) {
        log.error("Unexpected error: " + e);
        throw e;
    }
}

async function gotoPage(params: V1Request, page: Page): Promise<Response> {
    let response: Response;
    if (params.method != 'POST') {
        response = await page.goto(params.url, {waitUntil: 'domcontentloaded'});

    } else {
        // post hack
        // first request a page without cloudflare
        response = await page.goto(params.url, {waitUntil: 'domcontentloaded'});
        await page.setContent(
            `
<!DOCTYPE html>
<html>
<body>
<script>

  function parseQuery(queryString) {
    var query = {};
    var pairs = (queryString[0] === '?' ? queryString.substr(1) : queryString).split('&');
    for (var i = 0; i < pairs.length; i++) {
        var pair = pairs[i].split('=');
        query[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1] || '');
    }
    return query;
  }

  const form = document.createElement('form');
  form.method = 'POST';
  form.action = '${params.url}';

  const params = parseQuery('${params.postData}');
  for (const key in params) {
    if (params.hasOwnProperty(key)) {
      const hiddenField = document.createElement('input');
      hiddenField.type = 'hidden';
      hiddenField.name = key;
      hiddenField.value = params[key];
      form.appendChild(hiddenField);
    }
  }

  document.body.appendChild(form);
  form.submit();
    
</script>
</body>
</html> 
            `
        );
        await page.waitFor(2000)
        try {
            await page.waitForNavigation({waitUntil: 'domcontentloaded', timeout: 2000})
        } catch (e) {}

    }
    return response
}

export async function browserRequest(params: V1Request): Promise<ChallengeResolutionT> {
    const oneTimeSession = params.session === undefined;

    const options: SessionCreateOptions = {
        oneTimeSession: oneTimeSession,
        cookies: params.cookies,
        maxTimeout: params.maxTimeout,
        proxy: params.proxy
    }

    const session: SessionsCacheItem = oneTimeSession
        ? await sessions.create(null, options)
        : sessions.get(params.session)

    if (!session) {
        throw Error('This session does not exist. Use \'list_sessions\' to see all the existing sessions.')
    }

    try {
        return  await resolveChallengeWithTimeout(params, session)
    } catch (error) {
        throw Error("Unable to process browser request. " + error)
    } finally {
        if (oneTimeSession) {
            await sessions.destroy(session.sessionId)
        }
    }
}
