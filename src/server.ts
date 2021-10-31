import log from './services/log'
import {testWebBrowserInstallation} from "./services/sessions";

const app = require("./app");
const version: string = 'v' + require('../package.json').version
const serverPort: number = Number(process.env.PORT) || 8191
const serverHost: string = process.env.HOST || '0.0.0.0'

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
  // todo: fix resolvers
  // try {
  //   getCaptchaSolver();
  // } catch (e) {
  //   log.error(`The environment variable 'CAPTCHA_SOLVER' is wrong. ${e.message}`);
  //   process.exit(1);
  // }
}

// Init
log.info(`FlareSolverr ${version}`);
log.debug('Debug log enabled');

process.on('SIGTERM', () => {
  // Capture signal on Docker Stop #158
  log.info("Process interrupted")
  process.exit(0)
})

validateEnvironmentVariables();

testWebBrowserInstallation().then(() => {
  // Start server
  app.listen(serverPort, serverHost, () => {
    log.info(`Listening on http://${serverHost}:${serverPort}`);
  })
}).catch(function(e) {
  log.error(e);
  const msg: string = "" + e;
  if (msg.includes('while trying to connect to the browser!')) {
    log.error(`It seems that the system is too slow to run FlareSolverr. 
    If you are running with Docker, try to remove CPU limits in the container. 
    If not, try setting the 'BROWSER_TIMEOUT' environment variable and the 'maxTimeout' parameter to higher values.`);
  }
  process.exit(1);
})
