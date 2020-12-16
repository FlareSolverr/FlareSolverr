const solveCaptcha = require('@antiadmin/anticaptchaofficial');
const ANTI_CAPTCHA_APIKEY: string = process.env.ANTI_CAPTCHA_APIKEY || '0123456789abcdefghijklmnopqrstuvwxyz'
let task = "";

import { SolverOptions } from '.'
/*
    This method uses the @antiadmin/anticaptchaofficial project:
        https://github.com/AdminAnticaptcha/anticaptcha-npm
    TODO: 
    ENV:
        
*/

export default async function solve({ url }: SolverOptions, { sitekey }: SolverOptions, { type }: SolverOptions): Promise<string> {
  try {
    solveCaptcha.Setapikey(ANTI_CAPTCHA_APIKEY)
    solveCaptcha.getBalance()
     .then((balance: string) => console.log('my anti-captcha balance is $'+balance))
     .catch((error: string) => console.log('received error '+error))
    //switch between functions given captchatype
    switch(type) {
      case 'funCaptcha':
        task = await solveCaptcha.solveFunCaptchaProxyless(url, sitekey)
        .then((gresponse: string) => {
            console.log('result: '+gresponse);
        })
        .catch((error: string) => console.log('test received error '+error));
        break;
      case 'reCaptcha':
        task = await solveCaptcha.solveRecaptchaV3(url, 
            sitekey,
            0.3, //minimum score required: 0.3, 0.7 or 0.9
            'PAGE_ACTION_CAN_BE_EMPTY')
            .then((gresponse: string) => {
                console.log('g-response: '+gresponse);
            })
            .catch((error: string) => console.log('test received error '+error));
        break;
      case 'hCaptcha':
        task = await solveCaptcha.solveHCaptchaProxyless(url, sitekey)
            .then((gresponse: string) => {
            console.log('g-response: '+gresponse);
            })
            .catch((error: string) => console.log('test received error '+error));
        break;
      default:
        // code block
    }
    console.log('task result:' + task)
    return task
  } catch (e) {
    console.error(e)
    return null
  }
}
