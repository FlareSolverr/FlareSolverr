## FlareSolverr

Proxy server to bypass Cloudflare protection

:warning: This project is in beta state. Some things may not work and the API can change at any time.
See the known issues section.

### How it works

FlareSolverr starts a proxy server and it waits for user requests in idle state using few resources.
When some request arrives, it uses [puppeteer](https://github.com/puppeteer/puppeteer) with the
[stealth plugin](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth)
to create an headless browser (Chrome). It opens the URL with user parameters and waits until the Cloudflare
challenge is solved (or timeout). The HTML code and the cookies are sent back to the user and those cookies can
be used to bypass Cloudflare using other HTTP clients.

### Installation

It requires NodeJS.

Run `npm install` to install FlareSolverr dependencies.

### Usage

Run `node index.js` to start FlareSolverr.

Example request:
```bash
curl -L -X POST 'http://localhost:8191/v1' \
-H 'Content-Type: application/json' \
--data-raw '{
	"url":"http://www.google.com/",
	"userAgent": "Mozilla/5.0 (X11; Linux x86_64; rv:76.0) Gecko/20100101 Firefox/76.0"
}'
```
Parameter | Notes
|--|--|
url | Mandatory
userAgent | Optional. Will be used by the headless browser

Example response:
```json
{
  "status": "ok",
  "message": "",
  "startTimestamp": 1591679463498,
  "endTimestamp": 1591679472781,
  "version": "1.0.0",
  "solution": {
    "url": "https://www.google.com/?gws_rd=ssl",
    "response": "<!DOCTYPE html><html ...",
    "cookies": [
      {
        "name": "ANID",
        "value": "AHWqTUnRRMcmD0SxIOLAhv88SiY555FZpb4jeYCaSNZPHtYyBuY85AmaZEqLFTHe",
        "domain": ".google.com",
        "path": "/",
        "expires": 1625375465.915947,
        "size": 68,
        "httpOnly": true,
        "secure": true,
        "session": false,
        "sameSite": "None"
      },
      {
        "name": "1P_JAR",
        "value": "2020-6-9-5",
        "domain": ".google.com",
        "path": "/",
        "expires": 1594271465,
        "size": 16,
        "httpOnly": false,
        "secure": true,
        "session": false
      }
    ],
    "userAgent": " Mozilla/5.0 (X11; Linux x86_64; rv:76.0) Gecko/20100101 Firefox/76.0"
  }
}
```

#### Environment variables

To set the environment vars in Linux run `export LOG_LEVEL=debug` and then start FlareSolverr in the same shell.

Name | Default value
|--|--|
LOG_LEVEL | info
LOG_HTML | false
PORT | 8191
HOST | 0.0.0.0

### Docker

You can edit environment variables in `./Dockerfile` and build your own image.

```bash
docker build -t flaresolverr:latest .
docker run --restart=always --name flaresolverr -p 8191:8191 -d flaresolverr:latest
```

### Known issues / Roadmap

The current implementation is not able to bypass Cloudflare because they are detecting the headless browser.
I hope this will be fixed soon in the [puppeteer stealth plugin](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth)

TODO:
* Fix remaining issues in the code (see TODOs)
* Make the maxTimeout configurable by the user
* Add support for more HTTP methods (POST, PUT, DELETE ...)
* Add support for user HTTP headers
* Hide sensitive information in logs 
* Reduce Docker image size
