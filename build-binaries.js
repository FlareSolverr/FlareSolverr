const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')
const archiver = require('archiver')
const https = require('https')
const puppeteer = require('puppeteer')
const version = 'v' + require('./package.json').version;

function getFirefoxNightlyVersion() {
  const firefoxVersions = 'https://product-details.mozilla.org/1.0/firefox_versions.json';
  return new Promise((resolve, reject) => {
    let data = '';
    https
      .get(firefoxVersions, (r) => {
        if (r.statusCode >= 400)
          return reject(new Error(`Got status code ${r.statusCode}`));
        r.on('data', (chunk) => {
          data += chunk;
        });
        r.on('end', () => {
          try {
            const versions = JSON.parse(data);
            return resolve(versions.FIREFOX_NIGHTLY);
          } catch {
            return reject(new Error('Firefox version not found'));
          }
        });
      })
      .on('error', reject);
  });
}

(async () => {
  const builds = [
    {
      platform: 'linux',
      firefoxFolder: 'firefox',
      fsExec: 'flaresolverr-linux',
      fsZipExec: 'flaresolverr',
      fsZipName: 'linux-x64',
      fsLicenseName: 'LICENSE'
    },
    {
      platform: 'win64',
      firefoxFolder: 'firefox',
      fsExec: 'flaresolverr-win.exe',
      fsZipExec: 'flaresolverr.exe',
      fsZipName: 'windows-x64',
      fsLicenseName: 'LICENSE.txt'
    }
    // todo: this has to be build in macOS (hdiutil is required). changes required in sessions.ts too
    // {
    //   platform: 'mac',
    //   firefoxFolder: 'firefox',
    //   fsExec: 'flaresolverr-macos',
    //   fsZipExec: 'flaresolverr',
    //   fsZipName: 'macos',
    //   fsLicenseName: 'LICENSE'
    // }
  ]

  // generate executables
  console.log('Generating executables...')
  if (fs.existsSync('bin')) {
    fs.rmSync('bin', { recursive: true })
  }
  execSync('./node_modules/.bin/pkg -t node16-win-x64,node16-linux-x64 --out-path bin .')
  // execSync('./node_modules/.bin/pkg -t node16-win-x64,node16-mac-x64,node16-linux-x64 --out-path bin .')

  // get firefox revision
  const revision = await getFirefoxNightlyVersion();

  // download firefox and zip together
  for (const os of builds) {
    console.log('Building ' + os.fsZipName + ' artifact')

    // download firefox
    console.log(`Downloading firefox ${revision} for ${os.platform} ...`)
    const f = puppeteer.createBrowserFetcher({
      product: 'firefox',
      platform: os.platform,
      path: path.join(__dirname, 'bin', 'puppeteer')
    })
    await f.download(revision)

    // compress in zip
    console.log('Compressing zip file...')
    const zipName = 'bin/flaresolverr-' + version + '-' + os.fsZipName + '.zip'
    const output = fs.createWriteStream(zipName)
    const archive = archiver('zip')

    output.on('close', function () {
      console.log('File ' + zipName + ' created. Size: ' + archive.pointer() + ' bytes')
    })

    archive.on('error', function (err) {
      throw err
    })

    archive.pipe(output)

    archive.file('LICENSE', { name: 'flaresolverr/' + os.fsLicenseName })
    archive.file('bin/' + os.fsExec, { name: 'flaresolverr/' + os.fsZipExec })
    archive.directory('bin/puppeteer/' + os.platform + '-' + revision + '/' + os.firefoxFolder, 'flaresolverr/firefox')
    if (os.platform === 'linux') {
      archive.file('flaresolverr.service', { name: 'flaresolverr/flaresolverr.service' })
    }

    await archive.finalize()
  }
})()
