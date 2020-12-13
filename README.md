# FlareSolverr

[![GitHub issues](https://img.shields.io/github/issues/FlareSolverr/FlareSolverr.svg?maxAge=60&style=flat-square)](https://github.com/FlareSolverr/FlareSolverr/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/FlareSolverr/FlareSolverr.svg?maxAge=60&style=flat-square)](https://github.com/FlareSolverr/FlareSolverr/pulls)
[![Docker Pulls](https://img.shields.io/docker/pulls/flaresolverr/flaresolverr.svg?maxAge=60&style=flat-square)](https://hub.docker.com/r/flaresolverr/flaresolverr/)

FlareSolverr is a proxy server to bypass Cloudflare protection

:warning: This project is in beta state. Some things may not work and the API can change at any time.

## How it works

FlareSolverr starts a proxy server and it waits for user requests in an idle state using few resources.
When some request arrives, it uses [puppeteer](https://github.com/puppeteer/puppeteer) with the
[stealth plugin](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth)
to create a headless browser (Chrome). It opens the URL with user parameters and waits until the Cloudflare challenge
is solved (or timeout). The HTML code and the cookies are sent back to the user, and those cookies can be used to
bypass Cloudflare using other HTTP clients.

**NOTE**: Web browsers consume a lot of memory. If you are running FlareSolverr on a machine with few RAM, do not make
many requests at once. With each request a new browser is launched.

It is also possible to use a permanent session. However, if you use sessions, you should make sure to close them as
soon as you are done using them.

## Installation

### Docker

It is recommended to install using a Docker container because the project depends on an external browser that is
already included within the image.

Docker images are available in:
* GitHub Registry => https://github.com/orgs/FlareSolverr/packages/container/package/flaresolverr
* DockerHub => https://hub.docker.com/r/flaresolverr/flaresolverr

Supported architectures are:
| Architecture | Tag |
| :----: | --- |
| x86-64 | linux/amd64 |
| ARM64 | linux/arm64 |
| ARM32 | linux/arm/v7 |

We provide a `docker-compose.yml` configuration file. Clone this repository and execute `docker-compose up -d` to start
the container.

If you prefer the `docker cli` execute the following command.
```bash
docker run -d \
  --name=flaresolverr \
  -e LOG_LEVEL=info \
  --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest
```

### From source code

This is the recommended way for Windows / MacOS users and for developers.
* Install [NodeJS](https://nodejs.org/)
* Clone this repository and open a shell in that path
* Run `npm install` command to install FlareSolverr dependencies
* Run `npm run build` command to compile TypeScript code
* Run `npm start` command to start FlareSolverr

## Usage

Example request:
```bash
curl -L -X POST 'http://localhost:8191/v1' \
-H 'Content-Type: application/json' \
--data-raw '{
  "cmd": "request.get",
  "url":"http://www.google.com/",
  "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleW...",
  "maxTimeout": 60000,
  "headers": {
    "X-Test": "Testing 123..."
  }
}'
```

### Commands

#### + `sessions.create`

This will launch a new browser instance which will retain cookies until you destroy it with `sessions.destroy`.
This comes in handy, so you don't have to keep solving challenges over and over and you won't need to keep sending
cookies for the browser to use.

This also speeds up the requests since it won't have to launch a new browser instance for every request.

Parameter | Notes
|--|--|
session | Optional. The session ID that you want to be assigned to the instance. If isn't set a random UUID will be assigned.
userAgent | Optional. Will be used by the headless browser.

#### + `sessions.list`

Returns a list of all the active sessions. More for debugging if you are curious to see how many sessions are running.
You should always make sure to properly close each session when you are done using them as too many may slow your
computer down.

Example response:

```json
{
  "sessions": [
    "session_id_1",
    "session_id_2",
    "session_id_3..."
  ]
}
```

#### + `sessions.destroy`

This will properly shutdown a browser instance and remove all files associated with it to free up resources for a new
session. When you no longer need to use a session you should make sure to close it.

Parameter | Notes
|--|--|
session | The session ID that you want to be destroyed.

#### + `request.get`

Parameter | Notes
|--|--|
url | Mandatory
session | Optional. Will send the request from and existing browser instance. If one is not sent it will create a temporary instance that will be destroyed immediately after the request is completed.
headers | Optional. To specify user headers.
maxTimeout | Optional. Max timeout to solve the challenge
cookies | Optional. Will be used by the headless browser. Follow [this](https://github.com/puppeteer/puppeteer/blob/v3.3.0/docs/api.md#pagesetcookiecookies) format

Example response from running the `curl` above:

```json
{
    "solution": {
        "url": "https://www.google.com/?gws_rd=ssl",
        "status": 200,
        "headers": {
            "status": "200",
            "date": "Thu, 16 Jul 2020 04:15:49 GMT",
            "expires": "-1",
            "cache-control": "private, max-age=0",
            "content-type": "text/html; charset=UTF-8",
            "strict-transport-security": "max-age=31536000",
            "p3p": "CP=\"This is not a P3P policy! See g.co/p3phelp for more info.\"",
            "content-encoding": "br",
            "server": "gws",
            "content-length": "61587",
            "x-xss-protection": "0",
            "x-frame-options": "SAMEORIGIN",
            "set-cookie": "1P_JAR=2020-07-16-04; expires=Sat..."
        },
        "response":"<!DOCTYPE html>...",
        "cookies": [
            {
                "name": "NID",
                "value": "204=QE3Ocq15XalczqjuDy52HeseG3zAZuJzID3R57...",
                "domain": ".google.com",
                "path": "/",
                "expires": 1610684149.307722,
                "size": 178,
                "httpOnly": true,
                "secure": true,
                "session": false,
                "sameSite": "None"
            },
            {
                "name": "1P_JAR",
                "value": "2020-07-16-04",
                "domain": ".google.com",
                "path": "/",
                "expires": 1597464949.307626,
                "size": 19,
                "httpOnly": false,
                "secure": true,
                "session": false,
                "sameSite": "None"
            }
        ],
        "userAgent": "Windows NT 10.0; Win64; x64) AppleWebKit/5..."
    },
    "status": "ok",
    "message": "",
    "startTimestamp": 1594872947467,
    "endTimestamp": 1594872949617,
    "version": "1.0.0"
}
```

### + `request.post`

This is the same as `request.get` but it takes one more param:

Parameter | Notes
|--|--|
postData | Must be a string. If you want to POST a form, don't forget to set the `Content-Type` header to `application/x-www-form-urlencoded` or the server might not understand your request.

### Download small files

If you need to access an image/pdf or small file, you should pass the `download` parameter to `request.get` setting it
to `true`. Rather than access the html and return text it will return the buffer **base64** encoded which you will be
able to decode and save the image/pdf.

This method isn't recommended for videos or anything larger. As that should be streamed back to the client and at the
moment there is nothing setup to do so. If this is something you need feel free to create an issue and/or submit a PR.

## Environment variables

To set the environment vars in Linux run `export LOG_LEVEL=debug` and then start FlareSolverr in the same shell.

Name | Default | Notes
|--|--|--|
LOG_LEVEL | info | Used to change the verbosity of the logging.
LOG_HTML | false | Used for debugging. If `true` all HTML that passes through the proxy will be logged to the console in `debug` level.
PORT | 8191 | Change this if you already have a process running on port `8191`.
HOST | 0.0.0.0 | This shouldn't need to be messed with but if you insist, it's here!
CAPTCHA_SOLVER | None | This is used to select which captcha solving method it used when a captcha is encountered.
HEADLESS | true | This is used to debug the browser by not running it in headless mode.

## Captcha Solvers

Sometimes CF not only gives mathematical computations and browser tests, sometimes they also require the user to solve
a captcha. If this is the case, FlareSolverr will return the captcha page. But that's not very helpful to you is it?

FlareSolverr can be customized to solve the captchas automatically by setting the environment variable `CAPTCHA_SOLVER`
to the file name of one of the adapters inside the [/captcha](src/captcha) directory.

### hcaptcha-solver

This method makes use of the [hcaptcha-solver](https://github.com/JimmyLaurent/hcaptcha-solver) project which attempts
to solve hCaptcha by randomly selecting images.

To use this solver you must first install it and then set it as the `CAPTCHA_SOLVER`.

```bash
npm i hcaptcha-solver
CAPTCHA_SOLVER=hcaptcha-solver
```

### CaptchaHarvester

This method makes use of the [CaptchaHarvester](https://github.com/NoahCardoza/CaptchaHarvester) project which allows
users to collect thier own tokens from ReCaptcha V2/V3 and hCaptcha for free.

To use this method you must set these ENV variables:

```bash
CAPTCHA_SOLVER=harvester
HARVESTER_ENDPOINT=https://127.0.0.1:5000/token
```

**Note**: above I set `HARVESTER_ENDPOINT` to the default configuration of the captcha harvester's server, but that
could change if you customize the command line flags. Simply put, `HARVESTER_ENDPOINT` should be set to the URI of the
route that returns a token in plain text when called.

## Related projects

* C# implementation => https://github.com/FlareSolverr/FlareSolverrSharp
