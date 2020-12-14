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
    const token = await solveCaptcha(url)
    return token
  } catch (e) {
    console.error(e)
    return null
  }
}
