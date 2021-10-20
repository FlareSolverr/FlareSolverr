import log from './services/log'
import {NextFunction, Request, Response} from 'express';
import {getUserAgent} from "./services/sessions";
import {controllerV1} from "./controllers/v1";

const express = require('express');
const app = express();
const bodyParser = require('body-parser');
const version: string = 'v' + require('../package.json').version

// Convert request objects to JSON
app.use(bodyParser.json({
    limit: '50mb',
    verify(req: Request, res: Response, buf: any) {
        req.body = buf;
    }
}));

// Access log
app.use(function(req: Request, res: Response, next: NextFunction) {
    if (req.url != '/health') {
        // count the request for the log prefix
        log.incRequests()
        // build access message
        let body = "";
        if (req.method == 'POST' && req.body) {
            body += " body: "
            try {
                body += JSON.stringify(req.body)
            } catch(e) {
                body += req.body
            }
        }
        log.info(`Incoming request => ${req.method} ${req.url}${body}`);
    }
    next();
});

// *********************************************************************************************************************
// Routes

// Show welcome message
app.get("/", ( req: Request, res: Response ) => {
    res.send({
        "msg": "FlareSolverr is ready!",
        "version": version,
        "userAgent": getUserAgent()
    });
});

// Health endpoint. this endpoint is special because it doesn't print traces
app.get("/health", ( req: Request, res: Response ) => {
    res.send({
        "status": "ok"
    });
});

// Controller v1
app.post("/v1", async( req: Request, res: Response ) => {
    await controllerV1(req, res);
});

// *********************************************************************************************************************

// Unknown paths or verbs
app.use(function (req : Request, res : Response) {
    res.status(404)
        .send({"error": "Unknown resource or HTTP verb"})
})

// Errors
app.use(function (err: any, req: Request, res: Response, next: NextFunction) {
    if (err) {
        let msg = 'Invalid request: ' + err;
        msg = msg.replace("\n", "").replace("\r", "")
        log.error(msg)
        res.send({"error": msg})
    } else {
        next()
    }
})

module.exports = app;
