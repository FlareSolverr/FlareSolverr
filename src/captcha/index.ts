export enum CaptchaType {
  re = 'reCaptcha',
  h = 'hCaptcha'
}

export interface SolverOptions {
  url: string
  sitekey: string
  type: CaptchaType
}

export type Solver = (options: SolverOptions) => Promise<string>

const captchaSolvers: { [key: string]: Solver } = {}

export default (): Solver => {
  const method = process.env.CAPTCHA_SOLVER

  if (!method) { return null }

  if (!(method in captchaSolvers)) {
    try {
      captchaSolvers[method] = require('./' + method).default as Solver
    } catch (e) {
      if (e.code === 'MODULE_NOT_FOUND') {
        throw Error(`The solver '${method}' is not a valid captcha solving method.`)
      } else {
        console.error(e)
        throw Error(`An error occured loading the solver '${method}'.`)
      }
    }
  }

  return captchaSolvers[method]
}