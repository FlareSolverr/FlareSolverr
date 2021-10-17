import {v1 as UUIDv1} from 'uuid'
import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'
import {LaunchOptions, Headers, SetCookie, Browser} from 'puppeteer'

import log from './log'
import {deleteFolderRecursive, sleep, removeEmptyFields} from './utils'

const puppeteer = require('puppeteer');

interface SessionPageDefaults {
  headers?: Headers
}

export interface SessionsCacheItem {
  sessionId: string
  browser: Browser
  userDataDir?: string
  defaults: SessionPageDefaults
}

interface SessionsCache {
  [key: string]: SessionsCacheItem
}

export interface SessionCreateOptions {
  oneTimeSession: boolean
  cookies?: SetCookie[],
  headers?: Headers
  maxTimeout?: number
  proxy?: any// TODO: use interface not any
}

const sessionCache: SessionsCache = {}
let webBrowserUserAgent: string;


function userDataDirFromId(id: string): string {
  return path.join(os.tmpdir(), `/puppeteer_profile_${id}`)
}

function prepareBrowserProfile(id: string): string {
  // TODO: maybe pass SessionCreateOptions for loading later?
  const userDataDir = userDataDirFromId(id)

  if (!fs.existsSync(userDataDir)) {
    fs.mkdirSync(userDataDir, { recursive: true })
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

  // todo: these args are only supported in chrome
  let args = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage' // issue #45
  ];
  if (options.proxy && options.proxy.url) {
    args.push(`--proxy-server=${options.proxy.url}`);
  }

  const puppeteerOptions: LaunchOptions = {
    product: 'firefox',
    headless: process.env.HEADLESS !== 'false',
    args
  }

  if (!options.oneTimeSession) {
    log.debug('Creating userDataDir for session.')
    puppeteerOptions.userDataDir = prepareBrowserProfile(sessionId)
  }

  // todo: fix native package with firefox
  // if we are running inside executable binary, change browser path
  if (typeof (process as any).pkg !== 'undefined') {
    const exe = process.platform === "win32" ? 'chrome.exe' : 'chrome';
    puppeteerOptions.executablePath = path.join(path.dirname(process.execPath), 'chrome', exe)
  }

  log.debug('Launching web browser...')

  // TODO: maybe access env variable?
  // TODO: sometimes browser instances are created and not connected to correctly.
  //       how do we handle/quit those instances inside Docker?
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

  if (!browser) { throw Error(`Failed to launch browser 3 times in a row.`) }

  if (options.cookies) {
    const page = await browser.newPage()
    await page.setCookie(...options.cookies)
  }

  sessionCache[sessionId] = {
    sessionId: sessionId,
    browser: browser,
    userDataDir: puppeteerOptions.userDataDir,
    defaults: removeEmptyFields(options) // todo: review
  }

  return sessionCache[sessionId]
}

export function list(): string[] {
  return Object.keys(sessionCache)
}

// todo: create a sessions.close that doesn't rm the userDataDir

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
          await sleep(5000)
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
