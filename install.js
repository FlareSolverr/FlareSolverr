const fs = require('fs');
const puppeteer = require('puppeteer');

(async () => {

  // Puppeteer does not allow to download Firefox revisions, just the last Nightly
  // We this script we can download any version
  const revision = '94.0a1';
  const downloadHost = 'https://archive.mozilla.org/pub/firefox/nightly/2021/10/2021-10-01-09-33-23-mozilla-central';

  // skip installation (for Dockerfile)
  if (process.env.PUPPETEER_EXECUTABLE_PATH) {
    console.log('Skipping Firefox installation because the environment variable "PUPPETEER_EXECUTABLE_PATH" is set.');
    return;
  }

  // check if Firefox is already installed
  const f = puppeteer.createBrowserFetcher({
    product: 'firefox',
    host: downloadHost
  })
  if (fs.existsSync(f._getFolderPath(revision))) {
    console.log(`Firefox ${revision} already installed...`)
    return;
  }

  console.log(`Installing firefox ${revision} ...`)
  const downloadPath = f._downloadsFolder;
  console.log(`Download path: ${downloadPath}`)
  if (fs.existsSync(downloadPath)) {
    console.log(`Removing previous downloads...`)
    fs.rmSync(downloadPath, { recursive: true })
  }

  console.log(`Downloading firefox ${revision} ...`)
  await f.download(revision)

  console.log('Installation complete...')

})()
