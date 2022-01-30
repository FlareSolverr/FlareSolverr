import {Request, Response} from 'express';
import {Protocol} from "devtools-protocol";

import log from '../services/log'
import {browserRequest, ChallengeResolutionResultT, ChallengeResolutionT} from "../services/solver";
import {SessionCreateOptions} from "../services/sessions";
const sessions = require('../services/sessions')
const version: string = 'v' + require('../../package.json').version

interface V1Routes {
  [key: string]: (params: V1RequestBase, response: V1ResponseBase) => Promise<void>
}

export interface Proxy {
  url?: string
  username?: string
  password?: string
}

export interface V1RequestBase {
  cmd: string
  cookies?: Protocol.Network.CookieParam[],
  maxTimeout?: number
  proxy?: Proxy
  session: string
  headers?: Record<string, string> // deprecated v2, not used
  userAgent?: string // deprecated v2, not used
}

interface V1RequestSession extends V1RequestBase {
}

export interface V1Request extends V1RequestBase {
  url: string
  method?: string
  postData?: string
  returnOnlyCookies?: boolean
  download?: boolean // deprecated v2, not used
  returnRawHtml?: boolean // deprecated v2, not used
}

export interface V1ResponseBase {
  status: string
  message: string
  startTimestamp: number
  endTimestamp: number
  version: string
}

export interface V1ResponseSolution extends V1ResponseBase {
  solution: ChallengeResolutionResultT
}

export interface V1ResponseSession extends V1ResponseBase {
  session: string
}

export interface V1ResponseSessions extends V1ResponseBase {
  sessions: string[]
}

export const routes: V1Routes = {
  'sessions.create': async (params: V1RequestSession, response: V1ResponseSession): Promise<void> => {
    const options: SessionCreateOptions = {
      oneTimeSession: false,
      cookies: params.cookies,
      maxTimeout: params.maxTimeout,
      proxy: params.proxy
    }
    const { sessionId, browser } = await sessions.create(params.session, options)
    if (browser) {
      response.status = "ok";
      response.message = "Session created successfully.";
      response.session = sessionId
    } else {
      throw Error('Error creating session.')
    }
  },
  'sessions.list': async (params: V1RequestSession, response: V1ResponseSessions): Promise<void> => {
    response.status = "ok";
    response.message = "";
    response.sessions = sessions.list();
  },
  'sessions.destroy': async (params: V1RequestSession, response: V1ResponseBase): Promise<void> => {
    if (await sessions.destroy(params.session)) {
      response.status = "ok";
      response.message = "The session has been removed.";
    } else {
      throw Error('This session does not exist.')
    }
  },
  'request.get': async (params: V1Request, response: V1ResponseSolution): Promise<void> => {
    params.method = 'GET'
    if (params.postData) {
      throw Error('Cannot use "postBody" when sending a GET request.')
    }
    if (params.returnRawHtml) {
      log.warn("Request parameter 'returnRawHtml' was removed in FlareSolverr v2.")
    }
    if (params.download) {
      log.warn("Request parameter 'download' was removed in FlareSolverr v2.")
    }
    const result: ChallengeResolutionT = await browserRequest(params)

    response.status = result.status;
    response.message = result.message;
    response.solution = result.result;
    if (response.message) {
      log.info(response.message)
    }
  },
  'request.post': async (params: V1Request, response: V1ResponseSolution): Promise<void> => {
    params.method = 'POST'
    if (!params.postData) {
      throw Error('Must send param "postBody" when sending a POST request.')
    }
    if (params.returnRawHtml) {
      log.warn("Request parameter 'returnRawHtml' was removed in FlareSolverr v2.")
    }
    if (params.download) {
      log.warn("Request parameter 'download' was removed in FlareSolverr v2.")
    }
    const result: ChallengeResolutionT = await browserRequest(params)

    response.status = result.status;
    response.message = result.message;
    response.solution = result.result;
    if (response.message) {
      log.info(response.message)
    }
  },
}

export async function controllerV1(req: Request, res: Response): Promise<void> {
  const response: V1ResponseBase = {
    status: null,
    message: null,
    startTimestamp: Date.now(),
    endTimestamp: 0,
    version: version
  }

  try {
    const params: V1RequestBase = req.body
    // do some validations
    if (!params.cmd) {
      throw Error("Request parameter 'cmd' is mandatory.")
    }
    if (params.headers) {
      log.warn("Request parameter 'headers' was removed in FlareSolverr v2.")
    }
    if (params.userAgent) {
      log.warn("Request parameter 'userAgent' was removed in FlareSolverr v2.")
    }

    // set default values
    if (!params.maxTimeout || params.maxTimeout < 1) {
      params.maxTimeout = 60000;
    }

    // execute the command
    const route = routes[params.cmd]
    if (route) {
      await route(params, response)
    } else {
      throw Error(`The command '${params.cmd}' is invalid.`)
    }
  } catch (e) {
    res.status(500)
    response.status = "error";
    response.message = e.toString();
    log.error(response.message)
  }

  response.endTimestamp = Date.now()
  log.info(`Response in ${(response.endTimestamp - response.startTimestamp) / 1000} s`)
  res.send(response)
}
