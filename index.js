const log = require('console-log-level')(
{
  level: process.env.LOG_LEVEL || 'info',
  prefix: function (level) {
    return reqCounter.toString() + " " + new Date().toISOString() + " " + level.toUpperCase();
  }
});
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const http = require('http');
const pjson = require('./package.json');
const version = pjson.version;
const serverPort = process.env.PORT || 8191;
const serverHost = process.env.HOST || '0.0.0.0';
const logHtml = process.env.LOG_HTML || false;

// setting "user-agent-override" evasion is not working for us because it can't be changed
// in each request. we set the user-agent in the browser args instead
puppeteer.use(StealthPlugin());

// Help logging
var reqCounter = 0;

http.createServer(function(req, res) {
  reqCounter++;
  const startTimestamp = Date.now();
  log.info('Incoming request: ' + req.method + " " + req.url);
  var body = [];
  req.on('data', function(chunk) {
      body.push(chunk);
  }).on('end', function() {
      // parse params
      body = Buffer.concat(body).toString();
      var params = {};
      try {
        params = JSON.parse(body);
      }
      catch (err) {
        errorResponse("Body must be in JSON format", res, startTimestamp);
        return;
      }

      // validate params
      if (!validateIncomingRequest(params, req, res, startTimestamp))
        return;

      // process request
      processRequest(params, req, res, startTimestamp);
  });
}).listen(serverPort, serverHost, function() {
  log.info("FlareSolverr v" + version + " listening on http://" + serverHost + ":" + serverPort);
})

function errorResponse(errorMsg, res, startTimestamp) {
  log.error(errorMsg);
  const response = {
    status: "error",
    message: errorMsg,
    startTimestamp: startTimestamp,
    endTimestamp: Date.now(),
    version: version
  }
  res.writeHead(500, {
    'Content-Type': 'application/json'
  });
  res.write(JSON.stringify(response));
  res.end();
}

function validateIncomingRequest(params, req, res, startTimestamp) {
  log.info('Params: ' + JSON.stringify(params));

  if (req.method != 'POST') {
    errorResponse("Only POST method is allowed", res, startTimestamp);
    return false;
  }

  if (req.url != '/v1') {
    errorResponse("Only /v1 endpoint is allowed", res, startTimestamp);
    return false;
  }

  if (!params['url']) {
    errorResponse("Parameter 'url' is mandatory", res, startTimestamp);
    return false;
  }

  return true;
}

function processRequest(params, req, res, startTimestamp) {
  puppeteerArgs = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-infobars',
    '--window-position=0,0',
    '--ignore-certifcate-errors',
    '--ignore-certifcate-errors-spki-list'
  ];
  const reqUserAgent = params["userAgent"];
  if (reqUserAgent) {
    log.debug('Using custom User-Agent: ' + reqUserAgent);
    puppeteerArgs.push('--user-agent=' + reqUserAgent);
  }

  log.debug('Launching headless browser...');
  puppeteer.launch({
    headless: true,
    args: puppeteerArgs
  }).then(async browser => {
    try {
      await resolveCallenge(params, browser, res, startTimestamp);
    } catch (error) {
      errorResponse(error.message, res, startTimestamp);
    } finally {
      await browser.close();
    }
  }).catch(error => {
    errorResponse(error.message, res, startTimestamp);
  });;
}

async function resolveCallenge(params, browser, res, startTimestamp) {
  const page = await browser.newPage();
  const userAgent = await page.evaluate(() => navigator.userAgent);
  log.debug("User-Agent: " + userAgent);
  const reqUrl = params["url"];
  const reqCookies = params["cookies"];

  if (reqCookies) {
    log.debug('Applying cookies');
    await page.setCookie(...reqCookies);
  }

  log.debug("Navegating to... " + reqUrl);
  await page.goto(reqUrl, {waitUntil: 'networkidle0'});

  // detect cloudflare
  const cloudflareRay = await page.$('.ray_id');
  if (cloudflareRay) {
    log.debug('Waiting for Cloudflare challenge...');

    // page.waitForNavigation and page.waitFor don't work well because Cloudflare refresh the page
    // await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 30000 })
    // await page.waitFor(() => !document.querySelector('.ray_id'), {timeout: 30000});

    // TODO: get maxTimeout from params
    while(Date.now() - startTimestamp < 60000) {
      await page.waitFor(1000);

      // TODO: catch exception timeout in waitForNavigation
      await page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 5000 });
      const cloudflareRay = await page.$('.ray_id');
      if (!cloudflareRay)
        break;

      // TODO: throw timeout exception when maxTimeout is exceded
    }
  
    log.debug("Validating HTML code...");
    const html = await page.content();
    if (html.includes("captcha-bypass") || html.includes("__cf_chl_captcha_tk__")) {
      errorResponse("Chaptcha detected!", res, startTimestamp);
      return;
    }
  } else {
    log.debug("No challenge detected");
  }

  const url = await page.url();
  log.debug("Response URL: " + url);
  const cookies = await page.cookies();
  log.debug("Response cookies: " + JSON.stringify(cookies));
  const html = await page.content();
  if (logHtml)
    log.debug(html);

  const endTimestamp = Date.now();
  log.info("Successful response in " + (endTimestamp - startTimestamp) / 1000 + " s");
  const response = {
    status: "ok",
    message: "",
    startTimestamp: startTimestamp,
    endTimestamp: endTimestamp,
    version: version,
    solution: {
      url: url,
      response: html,
      cookies: cookies,
      userAgent: userAgent
    }
  }
  res.writeHead(200, {
    'Content-Type': 'application/json'
  });
  res.write(JSON.stringify(response));
  res.end();
}
