import got from 'got'
import { sleep } from '../utils'

/*
    This method uses the captcha-harvester project:
        https://github.com/NoahCardoza/CaptchaHarvester

    While the function must take url/sitekey/type args,
    they aren't used because the harvester server must
    be preconfigured.

    ENV:
        HARVESTER_ENDPOINT: This must be the full path
        to the /token endpoint of the harvester.
        E.G. "https://127.0.0.1:5000/token"
*/

export default async function solve(): Promise<string> {
  const endpoint = process.env.HARVESTER_ENDPOINT
  if (!endpoint) { throw Error('ENV variable `HARVESTER_ENDPOINT` must be set.') }
  while (true) {
    try {
      return (await got.get(process.env.HARVESTER_ENDPOINT, {
        https: { rejectUnauthorized: false }
      })).body
    } catch (e) {
      if (e.response.statusCode !== 418) { throw e }
    }
    await sleep(3000)
  }
}
