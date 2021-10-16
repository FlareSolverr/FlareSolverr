import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'

import log from './log'
import { deleteFolderRecursive, sleep, removeEmptyFields } from './utils'
import {LaunchOptions, Headers, SetCookie, Browser} from 'puppeteer'
const puppeteer = require('puppeteer');

interface SessionPageDefaults {
  headers?: Headers
  userAgent?: string
}

export interface SessionsCacheItem {
  browser: Browser
  userDataDir?: string
  defaults: SessionPageDefaults
}

interface SessionsCache {
  [key: string]: SessionsCacheItem
}

interface SessionCreateOptions {
  oneTimeSession?: boolean
  userAgent?: string
  cookies?: SetCookie[]
  headers?: Headers,
  maxTimeout?: number
  proxy?: any
}

const sessionCache: SessionsCache = {}

function userDataDirFromId(id: string): string {
  return path.join(os.tmpdir(), `/puppeteer_chrome_profile_${id}`)
}

function prepareBrowserProfile(id: string): string {
  // TODO: maybe pass SessionCreateOptions for loading later?
  const userDataDir = userDataDirFromId(id)

  if (!fs.existsSync(userDataDir)) {
    fs.mkdirSync(userDataDir, { recursive: true })
  }

  return userDataDir
}

export default {
  create: async (id: string, { cookies, oneTimeSession, userAgent, headers, maxTimeout, proxy }: SessionCreateOptions): Promise<SessionsCacheItem> => {
    let args = [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage' // issue #45
    ];
    if (proxy && proxy.url) {
      args.push(`--proxy-server=${proxy.url}`);
    }

    const puppeteerOptions: LaunchOptions = {
      product: 'chrome',
      headless: process.env.HEADLESS !== 'false',
      args
    }

    if (!oneTimeSession) {
      log.debug('Creating userDataDir for session.')
      puppeteerOptions.userDataDir = prepareBrowserProfile(id)
    }

    // if we are running inside executable binary, change chrome path
    if (typeof (process as any).pkg !== 'undefined') {
      const exe = process.platform === "win32" ? 'chrome.exe' : 'chrome';
      puppeteerOptions.executablePath = path.join(path.dirname(process.execPath), 'chrome', exe)
    }

    log.debug('Launching browser...')

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

    if (cookies) {
      const page = await browser.newPage()
      await page.setCookie(...cookies)
    }

    sessionCache[id] = {
      browser: browser,
      userDataDir: puppeteerOptions.userDataDir,
      defaults: removeEmptyFields({
        userAgent,
        headers,
        maxTimeout
      })
    }

    return sessionCache[id]
  },

  list: (): string[] => Object.keys(sessionCache),

  // TODO: create a sessions.close that doesn't rm the userDataDir

  destroy: async (id: string): Promise<boolean> => {
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
    return false
  },

  get: (id: string): SessionsCacheItem | false => sessionCache[id] && sessionCache[id] || false
}
