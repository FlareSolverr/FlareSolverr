import {v1 as UUIDv1} from 'uuid'
import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'
import {LaunchOptions, SetCookie, Browser} from 'puppeteer'

import log from './log'
import {deleteFolderRecursive, sleep} from './utils'
import {Proxy} from "../controllers/v1";

const puppeteer = require('puppeteer');

export interface SessionsCacheItem {
  sessionId: string
  browser: Browser
  userDataDir?: string
}

interface SessionsCache {
  [key: string]: SessionsCacheItem
}

export interface SessionCreateOptions {
  oneTimeSession: boolean
  cookies?: SetCookie[],
  maxTimeout?: number
  proxy?: Proxy
}

const sessionCache: SessionsCache = {}
let webBrowserUserAgent: string;


function userDataDirFromId(id: string): string {
  return path.join(os.tmpdir(), `/puppeteer_profile_${id}`)
}

function prepareBrowserProfile(id: string, proxy: Proxy): string {
  const userDataDir = userDataDirFromId(id)

  if (!fs.existsSync(userDataDir)) {
    fs.mkdirSync(userDataDir, { recursive: true })
  }

  // proxy.url format => http://<host>:<port>
  if (proxy && proxy.url) {
    let [host, port] = proxy.url.replace(/https?:\/\//g, '').split(':');

    let prefs = `
    user_pref("browser.newtabpage.enabled", false);
    user_pref("browser.startup.homepage", "about:blank");
    user_pref("browser.tabs.warnOnClose", false);
    user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
    user_pref("trailhead.firstrun.branches", "nofirstrun-empty");
    user_pref("browser.aboutwelcome.enabled", false);
    user_pref("network.proxy.ftp", "${host}");
    user_pref("network.proxy.ftp_port", ${port});
    user_pref("network.proxy.http", "${host}");
    user_pref("network.proxy.http_port", ${port});
    user_pref("network.proxy.share_proxy_settings", true);
    user_pref("network.proxy.socks", "${host}");
    user_pref("network.proxy.socks_port", ${port});
    user_pref("network.proxy.ssl", "${host}");
    user_pref("network.proxy.ssl_port", ${port});
    user_pref("network.proxy.type", 1);
    `

    fs.writeFileSync(path.join(userDataDir, './prefs.js'), prefs);
  }

  return userDataDir
}

export function getUserAgent() {
  return webBrowserUserAgent
}

export async function testWebBrowserInstallation(): Promise<void> {
  log.info("Testing web browser installation...")
  const session = await create(null, {
    oneTimeSession: true
  })
  const page = await session.browser.newPage()
  await page.goto("https://www.google.com")
  webBrowserUserAgent = await page.evaluate(() => navigator.userAgent)

  // replace Linux ARM user-agent because it's detected
  if (webBrowserUserAgent.toLocaleLowerCase().includes('linux arm')) {
    webBrowserUserAgent = webBrowserUserAgent.replace(/linux arm[^;]+;/i, 'Linux x86_64;')
  }

  log.info("FlareSolverr User-Agent: " + webBrowserUserAgent)
  await page.close()
  await destroy(session.sessionId)

  log.info("Test successful")
}

export async function create(session: string, options: SessionCreateOptions): Promise<SessionsCacheItem> {
  const sessionId = session || UUIDv1()

  // todo: cookies can't be set in the session, you need to open the page first

  const args: string[] = [];
  const puppeteerOptions: LaunchOptions = {
    product: 'firefox',
    headless: process.env.HEADLESS !== 'false',
    args
  }

  log.debug('Creating userDataDir for session.')
  puppeteerOptions.userDataDir = prepareBrowserProfile(sessionId, options.proxy)

  // todo: fix native package with firefox
  // if we are running inside executable binary, change browser path
  if (typeof (process as any).pkg !== 'undefined') {
    const exe = process.platform === "win32" ? 'chrome.exe' : 'chrome';
    puppeteerOptions.executablePath = path.join(path.dirname(process.execPath), 'chrome', exe)
  }

  log.debug('Launching web browser...')

  // todo: the retries are required?
  let launchTries = 3
  let browser: Browser;
  while (0 <= launchTries--) {
    try {
      browser = await puppeteer.launch(puppeteerOptions)
      break
    } catch (e) {
      if (e.message !== 'Failed to launch the browser process!')
        throw e
      log.warn('Failed to open browser, trying again...')
    }
  }

  if (!browser) {
    throw Error(`Failed to launch browser 3 times in a row.`)
  }

  sessionCache[sessionId] = {
    sessionId: sessionId,
    browser: browser,
    userDataDir: puppeteerOptions.userDataDir
  }

  return sessionCache[sessionId]
}

export function list(): string[] {
  return Object.keys(sessionCache)
}

export async function destroy(id: string): Promise<boolean>{
  if (id && sessionCache.hasOwnProperty(id)) {
    const { browser, userDataDir } = sessionCache[id]
    if (browser) {
      await browser.close()
      delete sessionCache[id]
      if (userDataDir) {
        const userDataDirPath = userDataDirFromId(id)
        try {
          // for some reason this keeps an error from being thrown in Windows, figures
          await sleep(100)
          deleteFolderRecursive(userDataDirPath)
        } catch (e) {
          console.error(e)
          throw Error(`Error deleting browser session folder. ${e.message}`)
        }
      }
      return true
    }
  }
  return false
}

export function get(id: string): SessionsCacheItem {
  return sessionCache[id]
}
