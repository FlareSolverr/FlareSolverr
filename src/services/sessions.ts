import {v1 as UUIDv1} from 'uuid'
import * as path from 'path'
import {Browser} from 'puppeteer'
import {Protocol} from "devtools-protocol";

import log from './log'
import {Proxy} from "../controllers/v1";

const os = require('os');
const fs = require('fs');
const puppeteer = require('puppeteer');

export interface SessionsCacheItem {
  sessionId: string
  browser: Browser
}

interface SessionsCache {
  [key: string]: SessionsCacheItem
}

export interface SessionCreateOptions {
  oneTimeSession: boolean
  cookies?: Protocol.Network.CookieParam[],
  maxTimeout?: number
  proxy?: Proxy
}

const sessionCache: SessionsCache = {}
let webBrowserUserAgent: string;

function buildExtraPrefsFirefox(proxy: Proxy): object {
  // Default configurations are defined here
  // https://github.com/puppeteer/puppeteer/blob/v3.3.0/src/Launcher.ts#L481
  const extraPrefsFirefox = {
    // Disable newtabpage
    "browser.newtabpage.enabled": false,
    "browser.startup.homepage": "about:blank",

    // Do not warn when closing all open tabs
    "browser.tabs.warnOnClose": false,

    // Disable telemetry
    "toolkit.telemetry.reportingpolicy.firstRun": false,

    // Disable first-run welcome page
    "startup.homepage_welcome_url": "about:blank",
    "startup.homepage_welcome_url.additional": "",

    // Detected !
    // // Disable images to speed up load
    // "permissions.default.image": 2,

    // Limit content processes to 1
    "dom.ipc.processCount": 1
  }

  // proxy.url format => http://<host>:<port>
  if (proxy && proxy.url) {
    log.debug(`Using proxy: ${proxy.url}`)
    const [host, portStr] = proxy.url.replace(/.+:\/\//g, '').split(':');
    const port = parseInt(portStr);
    if (!host || !portStr || !port) {
      throw new Error("Proxy configuration is invalid! Use the format: protocol://ip:port")
    }

    const proxyPrefs = {
      "network.proxy.type": 1,
      "network.proxy.share_proxy_settings": true
    }
    if (proxy.url.indexOf("socks") != -1) {
      // SOCKSv4 & SOCKSv5
      Object.assign(proxyPrefs, {
        "network.proxy.socks": host,
        "network.proxy.socks_port": port,
        "network.proxy.socks_remote_dns": true
      });
      if (proxy.url.indexOf("socks4") != -1) {
        Object.assign(proxyPrefs, {
          "network.proxy.socks_version": 4
        });
      } else {
        Object.assign(proxyPrefs, {
          "network.proxy.socks_version": 5
        });
      }
    } else {
      // HTTP
      Object.assign(proxyPrefs, {
        "network.proxy.ftp": host,
        "network.proxy.ftp_port": port,
        "network.proxy.http": host,
        "network.proxy.http_port": port,
        "network.proxy.ssl": host,
        "network.proxy.ssl_port": port
      });
    }

    // merge objects
    Object.assign(extraPrefsFirefox, proxyPrefs);
  }

  return extraPrefsFirefox;
}

export function getUserAgent() {
  return webBrowserUserAgent
}

export async function testWebBrowserInstallation(): Promise<void> {
  log.info("Testing web browser installation...")

  // check user home dir. this dir will be used by Firefox
  const homeDir = os.homedir();
  fs.accessSync(homeDir, fs.constants.F_OK | fs.constants.R_OK | fs.constants.W_OK | fs.constants.X_OK);
  log.debug("FlareSolverr user home directory is OK: " + homeDir)

  // test web browser
  const testUrl = process.env.TEST_URL || "https://www.google.com";
  log.debug("Test URL: " + testUrl)
  const session = await create(null, {
    oneTimeSession: true
  })
  const page = await session.browser.newPage()
  const pageTimeout = Number(process.env.BROWSER_TIMEOUT) || 40000
  await page.goto(testUrl, {waitUntil: 'domcontentloaded', timeout: pageTimeout})
  webBrowserUserAgent = await page.evaluate(() => navigator.userAgent)

  // replace Linux ARM user-agent because it's detected
  if (["arm", "aarch64"].some(arch => webBrowserUserAgent.toLocaleLowerCase().includes('linux ' + arch))) {
    webBrowserUserAgent = webBrowserUserAgent.replace(/linux \w+;/i, 'Linux x86_64;')
  }

  log.info("FlareSolverr User-Agent: " + webBrowserUserAgent)
  await page.close()
  await destroy(session.sessionId)

  log.info("Test successful")
}

export async function create(session: string, options: SessionCreateOptions): Promise<SessionsCacheItem> {
  log.debug('Creating new session...')

  const sessionId = session || UUIDv1()

  // NOTE: cookies can't be set in the session, you need to open the page first

  const puppeteerOptions: any = {
    product: 'firefox',
    headless: process.env.HEADLESS !== 'false',
    timeout: Number(process.env.BROWSER_TIMEOUT) || 40000
  }

  puppeteerOptions.extraPrefsFirefox = buildExtraPrefsFirefox(options.proxy)

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
    browser: browser
  }

  return sessionCache[sessionId]
}

export function list(): string[] {
  return Object.keys(sessionCache)
}

export async function destroy(id: string): Promise<boolean>{
  if (id && sessionCache.hasOwnProperty(id)) {
    const { browser } = sessionCache[id]
    if (browser) {
      await browser.close()
      delete sessionCache[id]
      return true
    }
  }
  return false
}

export function get(id: string): SessionsCacheItem {
  return sessionCache[id]
}
