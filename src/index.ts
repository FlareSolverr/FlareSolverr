const fs = require('fs');
const os = require('os');
const path = require('path');
const process = require('process')
import log from './log'
import { createServer, IncomingMessage, ServerResponse } from 'http';
import { RequestContext } from './types'
import Router, { BaseAPICall } from './routes'
import getCaptchaSolver from "./captcha";
import sessions from "./session";
import {v1 as UUIDv1} from "uuid";

const version: string = "v" + require('../package.json').version
const serverPort: number = Number(process.env.PORT) || 8191
const serverHost: string = process.env.HOST || '0.0.0.0'
let webBrowserUserAgent: string = ""

function validateEnvironmentVariables() {
  // ip and port variables are validated by nodejs
  if (process.env.LOG_LEVEL && ['error', 'warn', 'info', 'verbose', 'debug'].indexOf(process.env.LOG_LEVEL) == -1) {
    log.error(`The environment variable 'LOG_LEVEL' is wrong. Check the documentation.`);
    process.exit(1);
  }
  if (process.env.LOG_HTML && ['true', 'false'].indexOf(process.env.LOG_HTML) == -1) {
    log.error(`The environment variable 'LOG_HTML' is wrong. Check the documentation.`);
    process.exit(1);
  }
  if (process.env.HEADLESS && ['true', 'false'].indexOf(process.env.HEADLESS) == -1) {
    log.error(`The environment variable 'HEADLESS' is wrong. Check the documentation.`);
    process.exit(1);
  }
  try {
    getCaptchaSolver();
  } catch (e) {
    log.error(`The environment variable 'CAPTCHA_SOLVER' is wrong. ${e.message}`);
    process.exit(1);
  }
}

async function testWebBrowserInstallation() {
  const sessionId = UUIDv1()
  log.debug("Testing web browser installation...")
  const session = await sessions.create(sessionId, {
    oneTimeSession: true
  })
  const page = await session.browser.newPage()
  await page.goto("https://www.google.com")
  webBrowserUserAgent = await page.evaluate(() => navigator.userAgent)
  log.info("FlareSolverr User-Agent: " + webBrowserUserAgent)
  await page.close()
  await sessions.destroy(sessionId)
  log.debug("Test successful")
}

function errorResponse(errorMsg: string, res: ServerResponse, startTimestamp: number) {
  log.error(errorMsg)
  const response = {
    status: 'error',
    message: errorMsg,
    startTimestamp,
    endTimestamp: Date.now(),
    version
  }
  res.writeHead(500, {
    'Content-Type': 'application/json'
  })
  res.write(JSON.stringify(response))
  res.end()
}

function successResponse(successMsg: string, extendedProperties: object, res: ServerResponse, startTimestamp: number) {
  const endTimestamp = Date.now()
  log.info(`Response in ${(endTimestamp - startTimestamp) / 1000} s`)
  if (successMsg) { log.info(successMsg) }

  const response = Object.assign({
    status: 'ok',
    message: successMsg || '',
    startTimestamp,
    endTimestamp,
    version
  }, extendedProperties || {})
  res.writeHead(200, {
    'Content-Type': 'application/json'
  })
  res.write(JSON.stringify(response))
  res.end()
}

function validateIncomingRequest(ctx: RequestContext, params: BaseAPICall) {
  log.info(`Params: ${JSON.stringify(params)}`)

  if (ctx.req.method !== 'POST') {
    ctx.errorResponse('Only the POST method is allowed')
    return false
  }

  if (ctx.req.url !== '/v1') {
    ctx.errorResponse('Only /v1 endpoint is allowed')
    return false
  }

  if (!params.cmd) {
    ctx.errorResponse("Parameter 'cmd' is mandatory")
    return false
  }

  return true
}

// init
log.info(`FlareSolverr ${version}`);
log.debug('Debug log enabled');

process.on('SIGTERM', () => {
  // Capture signal on Docker Stop #158
  log.info("Process interrupted")
  process.exit(0)
})

validateEnvironmentVariables();

testWebBrowserInstallation()
.catch(e => {
  log.error("Error starting web browser.", e);
  process.exit(1);
})
.then(r =>
  createServer((req: IncomingMessage, res: ServerResponse) => {
    const startTimestamp = Date.now()

    // health endpoint. this endpoint is special because it doesn't print traces
    if (req.url == '/health') {
      res.writeHead(200, {
        'Content-Type': 'application/json'
      })
      res.write(JSON.stringify({"status": "ok"}))
      res.end()
      return;
    }

    // count the request for the log prefix
    log.incRequests()
    log.info(`Incoming request: ${req.method} ${req.url}`)

    // show welcome message
    if (req.url == '/') {
      const extendedProperties = {"userAgent": webBrowserUserAgent};
      successResponse("FlareSolverr is ready!", extendedProperties, res, startTimestamp);
      return;
    }

    // get request body
    const bodyParts: any[] = []
    req.on('data', chunk => {
      bodyParts.push(chunk)
    }).on('end', () => {
      // parse params
      const body = Buffer.concat(bodyParts).toString()
      let params: BaseAPICall = null
      try {
        params = JSON.parse(body)
      } catch (err) {
        errorResponse('Body must be in JSON format', res, startTimestamp)
        return
      }

      const ctx: RequestContext = {
        req,
        res,
        startTimestamp,
        errorResponse: (msg) => errorResponse(msg, res, startTimestamp),
        successResponse: (msg, extendedProperties) => successResponse(msg, extendedProperties, res, startTimestamp)
      }

      // validate params
      if (!validateIncomingRequest(ctx, params)) { return }

      // process request
      Router(ctx, params).catch(e => {
        console.error(e)
        ctx.errorResponse(e.message)
      })
    })
  }).listen(serverPort, serverHost, () => {
    log.info(`Listening on http://${serverHost}:${serverPort}`);
  })
)
