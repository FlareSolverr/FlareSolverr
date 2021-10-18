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
  return path.join(os.tmpdir(), `/puppeteer_cprofile_${id}`)
}

function prepareBrowserProfile(id: string, proxy: Proxy): string {
  const userDataDir = userDataDirFromId(id)

  if (!fs.existsSync(userDataDir)) {
    fs.mkdirSync(userDataDir, { recursive: true })
  }

  // Some parameters to configure Firefox
  // https://github.com/puppeteer/puppeteer/blob/943477cc1eb4b129870142873b3554737d5ef252/experimental/puppeteer-firefox/misc/puppeteer.cfg
  let prefs = `// Any comment. You must start the file with a comment!

// Disable newtabpage
user_pref("browser.newtabpage.enabled", false);
user_pref("browser.startup.homepage", "about:blank");

// Do not warn when closing all open tabs
user_pref("browser.tabs.warnOnClose", false);

// Disable telemetry
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);

// Disable first-run welcome page
user_pref("startup.homepage_welcome_url", "about:blank");
user_pref("startup.homepage_welcome_url.additional", "");

// Disable images to speed up load
user_pref("permissions.default.image", 2);

`

  // proxy.url format => http://<host>:<port>
  if (proxy && proxy.url) {
    let [host, port] = proxy.url.replace(/https?:\/\//g, '').split(':');
    prefs += `

// Proxy configuration
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
  }
  fs.writeFileSync(path.join(userDataDir, './prefs.js'), prefs);

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

  // if we are running inside executable binary, change browser path
  if (typeof (process as any).pkg !== 'undefined') {
    const exe = process.platform === "win32" ? 'firefox.exe' : 'firefox';
    puppeteerOptions.executablePath = path.join(path.dirname(process.execPath), 'firefox', exe)
  }

  log.debug('Launching web browser...')
  let browser: Browser = await puppeteer.launch(puppeteerOptions)
  if (!browser) {
    throw Error(`Failed to launch web browser.`)
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
