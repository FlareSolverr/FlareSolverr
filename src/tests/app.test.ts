// noinspection DuplicatedCode

import {Response} from "superagent";
import {V1ResponseBase, V1ResponseSession, V1ResponseSessions, V1ResponseSolution} from "../controllers/v1"
import {testWebBrowserInstallation} from "../services/sessions";

const request = require("supertest");
const app = require("../app");
const version: string = require('../../package.json').version

const googleUrl = "https://www.google.com";
const postUrl = "https://ptsv2.com/t/qv4j3-1634496523";
const cfUrl = "https://pirateiro.com/torrents/?search=harry";
const cfCaptchaUrl = "https://idope.se"

beforeAll(async () => {
    // Init session
    await testWebBrowserInstallation();
});

describe("Test '/' path", () => {
    test("GET method should return OK ", async () => {
        const response: Response = await request(app).get("/");
        expect(response.statusCode).toBe(200);
        expect(response.body.msg).toBe("FlareSolverr is ready!");
        expect(response.body.version).toBe(version);
        expect(response.body.userAgent).toContain("Firefox/")
    });

    test("POST method should fail", async () => {
        const response: Response = await request(app).post("/");
        expect(response.statusCode).toBe(404);
        expect(response.body.error).toBe("Unknown resource or HTTP verb");
    });
});

describe("Test '/health' path", () => {
    test("GET method should return OK", async () => {
        const response: Response = await request(app).get("/health");
        expect(response.statusCode).toBe(200);
        expect(response.body.status).toBe("ok");
    });
});

describe("Test '/wrong' path", () => {
    test("GET method should fail", async () => {
        const response: Response = await request(app).get("/wrong");
        expect(response.statusCode).toBe(404);
        expect(response.body.error).toBe("Unknown resource or HTTP verb");
    });
});

describe("Test '/v1' path", () => {
    jest.setTimeout(70000);

    test("Cmd 'request.bad' should fail", async () => {
        const payload = {
            "cmd": "request.bad",
            "url": googleUrl
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(500);

        const apiResponse: V1ResponseBase = response.body;
        expect(apiResponse.status).toBe("error");
        expect(apiResponse.message).toBe("Error: The command 'request.bad' is invalid.");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThanOrEqual(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);
    });

    test("Cmd 'request.get' should return OK with no Cloudflare", async () => {
        const payload = {
            "cmd": "request.get",
            "url": googleUrl
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSolution = response.body;
        expect(apiResponse.status).toBe("ok");
        expect(apiResponse.message).toBe("");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThan(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);

        const solution = apiResponse.solution;
        expect(solution.url).toContain(googleUrl)
        expect(solution.status).toBe(200);
        expect(Object.keys(solution.headers).length).toBeGreaterThan(0)
        expect(solution.response).toContain("<!DOCTYPE html>")
        expect(Object.keys(solution.cookies).length).toBeGreaterThan(0)
        expect(solution.userAgent).toContain("Firefox/")
    });

    test("Cmd 'request.get' should return OK with Cloudflare JS", async () => {
        const payload = {
            "cmd": "request.get",
            "url": cfUrl
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSolution = response.body;
        expect(apiResponse.status).toBe("ok");
        expect(apiResponse.message).toBe("");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThan(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);

        const solution = apiResponse.solution;
        expect(solution.url).toContain(cfUrl)
        expect(solution.status).toBe(200);
        expect(Object.keys(solution.headers).length).toBeGreaterThan(0)
        expect(solution.response).toContain("<!DOCTYPE html>")
        expect(Object.keys(solution.cookies).length).toBeGreaterThan(0)
        expect(solution.userAgent).toContain("Firefox/")

        const cfCookie: string = (solution.cookies as any[]).filter(function(cookie) {
            return cookie.name == "cf_clearance";
        })[0].value
        expect(cfCookie.length).toBeGreaterThan(30)
    });

    test("Cmd 'request.get' should return fail with Cloudflare CAPTCHA", async () => {
        const payload = {
            "cmd": "request.get",
            "url": cfCaptchaUrl
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSolution = response.body;
        expect(apiResponse.status).toBe("error");
        expect(apiResponse.message).toBe("Cloudflare Error: FlareSolverr can not resolve CAPTCHA challenges. Since the captcha doesn't always appear, you may have better luck with the next request.");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThan(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);
        // solution is filled but not useful
        expect(apiResponse.solution.url).toContain(cfCaptchaUrl)
    });

    test("Cmd 'request.get' should return OK with 'cookies' param", async () => {
        const payload = {
            "cmd": "request.get",
            "url": googleUrl,
            "cookies": [
                {
                    "name": "testcookie1",
                    "value": "testvalue1"
                },
                {
                    "name": "testcookie2",
                    "value": "testvalue2"
                }
            ]
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSolution = response.body;
        expect(apiResponse.status).toBe("ok");

        const solution = apiResponse.solution;
        expect(solution.url).toContain(googleUrl)
        expect(Object.keys(solution.cookies).length).toBeGreaterThan(1)
        const cookie1: string = (solution.cookies as any[]).filter(function(cookie) {
            return cookie.name == "testcookie1";
        })[0].value
        expect(cookie1).toBe("testvalue1")
        const cookie2: string = (solution.cookies as any[]).filter(function(cookie) {
            return cookie.name == "testcookie2";
        })[0].value
        expect(cookie2).toBe("testvalue2")
    });

    test("Cmd 'request.get' should return OK with 'returnOnlyCookies' param", async () => {
        const payload = {
            "cmd": "request.get",
            "url": googleUrl,
            "returnOnlyCookies": true
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSolution = response.body;

        const solution = apiResponse.solution;
        expect(solution.url).toContain(googleUrl)
        expect(solution.status).toBe(200);
        expect(solution.headers).toBe(null)
        expect(solution.response).toBe(null)
        expect(Object.keys(solution.cookies).length).toBeGreaterThan(0)
        expect(solution.userAgent).toBe(null)
    });

    test("Cmd 'request.get' should return timeout", async () => {
        const payload = {
            "cmd": "request.get",
            "url": googleUrl,
            "maxTimeout": 10
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(500);

        const apiResponse: V1ResponseBase = response.body;
        expect(apiResponse.status).toBe("error");
        expect(apiResponse.message).toBe("Error: Unable to process browser request. Error: Error: Maximum timeout reached. maxTimeout=10 (ms)");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThan(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);
    });

    test("Cmd 'request.get' should accept deprecated params", async () => {
        const payload = {
            "cmd": "request.get",
            "url": googleUrl,
            "userAgent": "Test User-Agent" // was removed in v2, not used
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSolution = response.body;
        expect(apiResponse.status).toBe("ok");

        const solution = apiResponse.solution;
        expect(solution.url).toContain(googleUrl)
        expect(solution.status).toBe(200);
        expect(solution.userAgent).toContain("Firefox/")
    });

    test("Cmd 'request.post' should return OK with no Cloudflare", async () => {
        const payload = {
            "cmd": "request.post",
            "url": postUrl + '/post',
            "postData": "param1=value1&param2=value2"
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSolution = response.body;
        expect(apiResponse.status).toBe("ok");
        expect(apiResponse.message).toBe("");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThan(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);

        const solution = apiResponse.solution;
        expect(solution.url).toContain(postUrl)
        expect(solution.status).toBe(200);
        expect(Object.keys(solution.headers).length).toBeGreaterThan(0)
        expect(solution.response).toContain(" I hope you have a lovely day!")
        expect(Object.keys(solution.cookies).length).toBe(0)
        expect(solution.userAgent).toContain("Firefox/")

        // check that we sent the date
        const payload2 = {
            "cmd": "request.get",
            "url": postUrl
        }
        const response2: Response = await request(app).post("/v1").send(payload2);
        expect(response2.statusCode).toBe(200);

        const apiResponse2: V1ResponseSolution = response2.body;
        expect(apiResponse2.status).toBe("ok");

        const solution2 = apiResponse2.solution;
        expect(solution2.status).toBe(200);
        expect(solution2.response).toContain(new Date().toISOString().split(':')[0].replace('T', ' '))
    });

    test("Cmd 'request.post' should fail without 'postData' param", async () => {
        const payload = {
            "cmd": "request.post",
            "url": googleUrl
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(500);

        const apiResponse: V1ResponseBase = response.body;
        expect(apiResponse.status).toBe("error");
        expect(apiResponse.message).toBe("Error: Must send param \"postBody\" when sending a POST request.");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThanOrEqual(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);
    });

    test("Cmd 'sessions.create' should return OK", async () => {
        const payload = {
            "cmd": "sessions.create"
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSession = response.body;
        expect(apiResponse.status).toBe("ok");
        expect(apiResponse.message).toBe("Session created successfully.");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThan(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);
        expect(apiResponse.session.length).toBe(36);
    });

    test("Cmd 'sessions.create' should return OK with session", async () => {
        const payload = {
            "cmd": "sessions.create",
            "session": "2bc6bb20-2f56-11ec-9543-test"
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSession = response.body;
        expect(apiResponse.status).toBe("ok");
        expect(apiResponse.message).toBe("Session created successfully.");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThan(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);
        expect(apiResponse.session).toBe("2bc6bb20-2f56-11ec-9543-test");
    });

    test("Cmd 'sessions.list' should return OK", async () => {
        // create one session for testing
        const payload0 = {
            "cmd": "sessions.create"
        }
        const response0: Response = await request(app).post("/v1").send(payload0);
        expect(response0.statusCode).toBe(200);

        const payload = {
            "cmd": "sessions.list"
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSessions = response.body;
        expect(apiResponse.status).toBe("ok");
        expect(apiResponse.message).toBe("");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThanOrEqual(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);
        expect(apiResponse.sessions.length).toBeGreaterThan(0)
    });

    test("Cmd 'sessions.destroy' should return OK", async () => {
        // create one session for testing
        const payload0 = {
            "cmd": "sessions.create"
        }
        const response0: Response = await request(app).post("/v1").send(payload0);
        expect(response0.statusCode).toBe(200);
        const apiResponse0: V1ResponseSession = response0.body;
        const sessionId0 = apiResponse0.session

        const payload = {
            "cmd": "sessions.destroy",
            "session": sessionId0
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseBase = response.body;
        expect(apiResponse.status).toBe("ok");
        expect(apiResponse.message).toBe("The session has been removed.");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThan(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);
    });

    test("Cmd 'sessions.destroy' should fail", async () => {
        const payload = {
            "cmd": "sessions.destroy",
            "session": "bad-session"
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(500);

        const apiResponse: V1ResponseBase = response.body;
        expect(apiResponse.status).toBe("error");
        expect(apiResponse.message).toBe("Error: This session does not exist.");
        expect(apiResponse.startTimestamp).toBeGreaterThan(1000);
        expect(apiResponse.endTimestamp).toBeGreaterThan(apiResponse.startTimestamp);
        expect(apiResponse.version).toBe(version);
    });

    test("Cmd 'request.get' should use session", async () => {
        // create one session for testing
        const payload0 = {
            "cmd": "sessions.create"
        }
        const response0: Response = await request(app).post("/v1").send(payload0);
        expect(response0.statusCode).toBe(200);
        const apiResponse0: V1ResponseSession = response0.body;
        const sessionId0 = apiResponse0.session

        // first request should solve the challenge
        const payload = {
            "cmd": "request.get",
            "url": cfUrl,
            "session": sessionId0
        }
        const response: Response = await request(app).post("/v1").send(payload);
        expect(response.statusCode).toBe(200);

        const apiResponse: V1ResponseSolution = response.body;
        expect(apiResponse.status).toBe("ok");
        const cfCookie: string = (apiResponse.solution.cookies as any[]).filter(function(cookie) {
            return cookie.name == "cf_clearance";
        })[0].value
        expect(cfCookie.length).toBeGreaterThan(30)

        // second request should have the same cookie
        const response2: Response = await request(app).post("/v1").send(payload);
        expect(response2.statusCode).toBe(200);

        const apiResponse2: V1ResponseSolution = response2.body;
        expect(apiResponse2.status).toBe("ok");
        const cfCookie2: string = (apiResponse2.solution.cookies as any[]).filter(function(cookie) {
            return cookie.name == "cf_clearance";
        })[0].value
        expect(cfCookie2.length).toBeGreaterThan(30)
        expect(cfCookie2).toBe(cfCookie)
    });

});
