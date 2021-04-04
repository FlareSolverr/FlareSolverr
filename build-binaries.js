const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')
const archiver = require('archiver')
const puppeteer = require('puppeteer')
const version = 'v' + require('./package.json').version;

(async () => {
  const builds = [
    {
      platform: 'linux',
      version: 756035,
      chromeFolder: 'chrome-linux',
      fsExec: 'flaresolverr-linux',
      fsZipExec: 'flaresolverr',
      fsZipName: 'linux-x64',
      fsLicenseName: 'LICENSE'
    },
    {
      platform: 'win64',
      version: 756035,
      chromeFolder: 'chrome-win',
      fsExec: 'flaresolverr-win.exe',
      fsZipExec: 'flaresolverr.exe',
      fsZipName: 'windows-x64',
      fsLicenseName: 'LICENSE.txt'
    }
    // TODO: this is working but changes are required in session.ts to find chrome path
    // {
    //   platform: 'mac',
    //   version: 756035,
    //   chromeFolder: 'chrome-mac',
    //   fsExec: 'flaresolverr-macos',
    //   fsZipExec: 'flaresolverr',
    //   fsZipName: 'macos',
    //   fsLicenseName: 'LICENSE'
    // }
  ]

  // generate executables
  console.log('Generating executables...')
  if (fs.existsSync('bin')) {
    fs.rmdirSync('bin', { recursive: true })
  }
  execSync('pkg -t node14-win-x64,node14-linux-x64 --out-path bin .')
  // execSync('pkg -t node14-win-x64,node14-mac-x64,node14-linux-x64 --out-path bin .')

  // download Chrome and zip together
  for (const os of builds) {
    console.log('Building ' + os.fsZipName + ' artifact')

    // download chrome
    console.log('Downloading Chrome...')
    const f = puppeteer.createBrowserFetcher({
      platform: os.platform,
      path: path.join(__dirname, 'bin', 'puppeteer')
    })
    await f.download(os.version)

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
    archive.directory('bin/puppeteer/' + os.platform + '-' + os.version + '/' + os.chromeFolder, 'flaresolverr/chrome')

    await archive.finalize()
  }
})()
