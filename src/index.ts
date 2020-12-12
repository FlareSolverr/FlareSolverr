import log from './log'
import { createServer, IncomingMessage, ServerResponse } from 'http';
import { RequestContext } from './types'
import Router, { BaseAPICall } from './routes'

const version: string = require('../package.json').version
const serverPort: number = Number(process.env.PORT) || 8191
const serverHost: string = process.env.HOST || '0.0.0.0'


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
  log.info(`Successful response in ${(endTimestamp - startTimestamp) / 1000} s`)
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

createServer((req: IncomingMessage, res: ServerResponse) => {
  // count the request for the log prefix
  log.incRequests()

  const startTimestamp = Date.now()
  log.info(`Incoming request: ${req.method} ${req.url}`)
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
  log.info(`FlareSolverr v${version} listening on http://${serverHost}:${serverPort}`)
})
