# Changelog

## v3.0.4 (2023/03/07

* Click on the Cloudflare's 'Verify you are human' button if necessary

## v3.0.3 (2023/03/06)

* Update undetected_chromedriver version to 3.4.6

## v3.0.2 (2023/01/08)

* Detect Cloudflare blocked access
* Check Chrome / Chromium web browser is installed correctly

## v3.0.1 (2023/01/06)

* Kill Chromium processes properly to avoid defunct/zombie processes
* Update undetected-chromedriver
* Disable Zygote sandbox in Chromium browser
* Add more selectors to detect blocked access
* Include procps (ps), curl and vim packages in the Docker image

## v3.0.0 (2023/01/04)

* This is the first release of FlareSolverr v3. There are some breaking changes
* Docker images for linux/386, linux/amd64, linux/arm/v7 and linux/arm64/v8
* Replaced Firefox with Chrome
* Replaced NodeJS / Typescript with Python
* Replaced Puppeter with Selenium
* No binaries for Linux / Windows. You have to use the Docker image or install from Source code
* No proxy support
* No session support

## v2.2.10 (2022/10/22)

* Detect DDoS-Guard through title content

## v2.2.9 (2022/09/25)

* Detect Cloudflare Access Denied
* Commit the complete changelog

## v2.2.8 (2022/09/17)

* Remove 30 s delay and clean legacy code

## v2.2.7 (2022/09/12)

* Temporary fix: add 30s delay
* Update README.md

## v2.2.6 (2022/07/31)

* Fix Cloudflare detection in POST requests

## v2.2.5 (2022/07/30)

* Update GitHub actions to build executables with NodeJs 16
* Update Cloudflare selectors and add HTML samples
* Install Firefox 94 instead of the latest Nightly
* Update dependencies
* Upgrade Puppeteer (#396)

## v2.2.4 (2022/04/17)

* Detect DDoS-Guard challenge

## v2.2.3 (2022/04/16)

* Fix 2000 ms navigation timeout
* Update README.md (libseccomp2 package in Debian)
* Update README.md (clarify proxy parameter) (#307)
* Update NPM dependencies
* Disable Cloudflare ban detection

## v2.2.2 (2022/03/19)

* Fix ban detection. Resolves #330 (#336)

## v2.2.1 (2022/02/06)

* Fix max timeout error in some pages
* Avoid crashing in NodeJS 17 due to Unhandled promise rejection
* Improve proxy validation and debug traces
* Remove @types/puppeteer dependency

## v2.2.0 (2022/01/31)

* Increase default BROWSER_TIMEOUT=40000 (40 seconds)
* Fix Puppeter deprecation warnings
* Update base Docker image Alpine 3.15 / NodeJS 16
* Build precompiled binaries with NodeJS 16
* Update Puppeter and other dependencies
* Add support for Custom CloudFlare challenge
* Add support for DDoS-GUARD challenge

## v2.1.0 (2021/12/12)

* Add aarch64 to user agents to be replaced (#248)
* Fix SOCKSv4 and SOCKSv5 proxy. resolves #214 #220
* Remove redundant JSON key (postData) (#242)
* Make test URL configurable with TEST_URL env var. resolves #240
* Bypass new Cloudflare protection
* Update donation links

## v2.0.2 (2021/10/31)

* Fix SOCKS5 proxy. Resolves #214
* Replace Firefox ERS with a newer version
* Catch startup exceptions and give some advices
* Add env var BROWSER_TIMEOUT for slow systems
* Fix NPM warning in Docker images

## v2.0.1 (2021/10/24)

* Check user home dir before testing web browser installation

## v2.0.0 (2021/10/20)

FlareSolverr 2.0.0 is out with some important changes:

* It is capable of solving the automatic challenges of Cloudflare. CAPTCHAs (hCaptcha) cannot be resolved and the old solvers have been removed.
* The Chrome browser has been replaced by Firefox. This has caused some functionality to be removed. Parameters: `userAgent`, `headers`, `rawHtml` and `downloadare` no longer available.
* Included `proxy` support without user/password credentials. If you are writing your own integration with FlareSolverr, make sure your client uses the same User-Agent header and Proxy that FlareSolverr uses. Those values together with the Cookie are checked and detected by Cloudflare.
* FlareSolverr has been rewritten from scratch. From now on it should be easier to maintain and test.
* If you are using Jackett make sure you have version v0.18.1041 or higher. FlareSolverSharp v2.0.0 is out too.

Complete changelog:

* Bump version 2.0.0
* Set puppeteer timeout half of maxTimeout param. Resolves #180
* Add test for blocked IP
* Avoid reloading the page in case of error
* Improve Cloudflare detection
* Fix version
* Fix browser preferences and proxy
* Fix request.post method and clean error traces
* Use Firefox ESR for Docker images
* Improve Firefox start time and code clean up
* Improve bad request management and tests
* Build native packages with Firefox
* Update readme
* Improve Docker image and clean TODOs
* Add proxy support
* Implement request.post method for Firefox
* Code clean up, remove returnRawHtml, download, headers params
* Remove outdated chaptcha solvers
* Refactor the app to use Express server and Jest for tests
* Fix Cloudflare resolver for Linux ARM builds
* Fix Cloudflare resolver
* Replace Chrome web browser with Firefox
* Remove userAgent parameter since any modification is detected by CF
* Update dependencies
* Remove Puppeter steath plugin

## v1.2.9 (2021/08/01)

* Improve "Execution context was destroyed" error handling
* Implement returnRawHtml parameter. resolves #172 resolves #165
* Capture Docker stop signal. resolves #158
* Reduce Docker image size 20 MB
* Fix page reload after challenge is solved. resolves #162 resolves #143
* Avoid loading images/css/fonts to speed up page load
* Improve Cloudflare IP ban detection
* Fix vulnerabilities

## v1.2.8 (2021/06/01)

* Improve old JS challenge waiting. Resolves #129

## v1.2.7 (2021/06/01)

* Improvements in Cloudflare redirect detection. Resolves #140
* Fix installation instructions

## v1.2.6 (2021/05/30)

* Handle new Cloudflare challenge. Resolves #135 Resolves #134
* Provide reference Systemd unit file. Resolves #72
* Fix EACCES: permission denied, open '/tmp/flaresolverr.txt'. Resolves #120
* Configure timezone with TZ env var. Resolves #109
* Return the redirected URL in the response (#126)
* Show an error in hcaptcha-solver. Resolves #132
* Regenerate package-lock.json lockfileVersion 2
* Update issue template. Resolves #130
* Bump ws from 7.4.1 to 7.4.6 (#137)
* Bump hosted-git-info from 2.8.8 to 2.8.9 (#124)
* Bump lodash from 4.17.20 to 4.17.21 (#125)

## v1.2.5 (2021/04/05)

* Fix memory regression, close test browser
* Fix release-docker GitHub action

## v1.2.4 (2021/04/04)

* Include license in release zips. resolves #75
* Validate Chrome is working at startup
* Speedup Docker image build
* Add health check endpoint
* Update issue template
* Minor improvements in debug traces
* Validate environment variables at startup. resolves #101
* Add FlareSolverr logo. resolves #23

## v1.2.3 (2021/01/10)

* CI/CD: Generate release changelog from commits. resolves #34
* Update README.md
* Add donation links
* Simplify docker-compose.yml
* Allow to configure "none" captcha resolver
* Override docker-compose.yml variables via .env resolves #64 (#66)

## v1.2.2 (2021/01/09)

* Add documentation for precompiled binaries installation
* Add instructions to set environment variables in Windows
* Build Windows and Linux binaries. resolves #18
* Add release badge in the readme
* CI/CD: Generate release changelog from commits. resolves #34
* Add a notice about captcha solvers
* Add Chrome flag --disable-dev-shm-usage to fix crashes. resolves #45
* Fix Docker CLI documentation
* Add traces with captcha solver service. resolves #39
* Improve logic to detect Cloudflare captcha. resolves #48
* Move Cloudflare provider logic to his own class
* Simplify and document the "return only cookies" parameter
* Show message when debug log is enabled
* Update readme to add more clarifications. resolves #53 (#60)
* issue_template: typo fix (#52)

## v1.2.1 (2020/12/20)

* Change version to match release tag / 1.2.0 => v1.2.0
* CI/CD Publish release in GitHub repository. resolves #34
* Add welcome message in / endpoint
* Rewrite request timeout handling (maxTimeout) resolves #42
* Add http status for better logging
* Return an error when no selectors are found, #25
* Add issue template, fix #32
* Moving log.html right after loading the page and add one on reload, fix #30
* Update User-Agent to match chromium version, ref: #15 (#28)
* Update install from source code documentation
* Update readme to add Docker instructions (#20)
* Clean up readme (#19)
* Add docker-compose
* Change default log level to info

## v1.2.0 (2020/12/20)

* Fix User-Agent detected by CouldFlare (Docker ARM) resolves #15
* Include exception message in error response
* CI/CD: Rename GitHub Action build => publish
* Bump version
* Fix TypeScript compilation and bump minor version
* CI/CD: Bump minor version
* CI/CD: Configure GitHub Actions
* CI/CD: Configure GitHub Actions
* CI/CD: Bump minor version
* CI/CD: Configure Build GitHub Action
* CI/CD: Configure AutoTag GitHub Action (#14)
* CI/CD: Build the Docker images with GitHub Actions (#13)
* Update dependencies
* Backport changes from Cloudproxy (#11)
