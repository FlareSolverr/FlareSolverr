const solveCaptcha = require('@antiadmin/anticaptchaofficial');
import { SolverOptions } from '.'
/*
    This method uses the @antiadmin/anticaptchaofficial project:
        https://github.com/AdminAnticaptcha/anticaptcha-npm
    TODO: 
    ENV:
        
*/

export default async function solve({ url }: SolverOptions): Promise<string> {
  try {
    solveCaptcha.Setapikey(ANTI_CAPTCHA_APIKEY)
    solveCaptcha.getBalance()
     .then(balance => console.log('my anti-captcha balance is $'+balance))
     .catch(error => console.log('received error '+error))
    //switch between functions given captchatype
    switch(type) {
      case funCaptcha:
        const task = await solveCaptcha.solveFunCaptchaProxyless(url, sitekey)
        .then(gresponse => {
            console.log('result: '+gresponse);
        })
        .catch(error => console.log('test received error '+error));
        break;
      case reCaptcha:
        const task = await solveCaptcha.solveRecaptchaV3(url, 
            sitekey,
            0.3, //minimum score required: 0.3, 0.7 or 0.9
            'PAGE_ACTION_CAN_BE_EMPTY')
            .then(gresponse => {
                console.log('g-response: '+gresponse);
            })
            .catch(error => console.log('test received error '+error));
        break;
      case hCaptcha:
        const task = await solveCaptcha.solveHCaptchaProxyless(url, sitekey)
            .then(gresponse => {
            console.log('g-response: '+gresponse);
            })
            .catch(error => console.log('test received error '+error));
        break;
      default:
        // code block
    }
    console.log('task result:' + task)
    return task.solution
  } catch (e) {
    console.error(e)
    return null
  }
}
