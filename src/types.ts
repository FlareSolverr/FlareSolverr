import { IncomingMessage, ServerResponse } from 'http';

export interface RequestContext {
  req: IncomingMessage
  res: ServerResponse
  startTimestamp: number
  errorResponse: (msg: string) => void,
  successResponse: (msg: string, extendedProperties?: object) => void
}