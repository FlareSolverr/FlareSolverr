import log from './services/log'
import {Request, Response} from 'express';
import {getUserAgent} from "./services/sessions";
import {controllerV1} from "./controllers/v1";

const express = require('express');
const app = express();
const bodyParser = require('body-parser');
const version: string = require('../package.json').version

// Convert request objects to JSON
app.use(bodyParser.json({
    limit: '50mb',
    verify(req: Request, res: Response, buf: any) {
        req.body = buf;
    }
}));

// *********************************************************************************************************************
// Routes

// show welcome message
app.get("/", ( req: Request, res: Response ) => {
    log.info(`Incoming request: /`);
    res.send({
        "msg": "FlareSolverr is ready!",
        "version": version,
        "userAgent": getUserAgent()
    });
});

// health endpoint. this endpoint is special because it doesn't print traces
app.get("/health", ( req: Request, res: Response ) => {
    res.send({
        "status": "ok"
    });
});

// controller v1
app.post("/v1", async( req: Request, res: Response ) => {
    // count the request for the log prefix
    log.incRequests()

    const params = req.body;
    log.info(`Incoming request: /v1 Params: ${JSON.stringify(params)}`);
    await controllerV1(req, res);
});

// *********************************************************************************************************************

// Unknown paths or verbs
app.use(function (req : Request, res : Response) {
    res.status(404).send({"error": "Unknown resource or HTTP verb"})
})

module.exports = app;
