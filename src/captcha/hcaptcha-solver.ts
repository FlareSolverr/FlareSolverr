const solveCaptcha = require('hcaptcha-solver');
import { SolverOptions } from '.'
/*
    This method uses the hcaptcha-solver project:
        https://github.com/JimmyLaurent/hcaptcha-solver

    TODO: allow user pass custom options to the solver.

    ENV:
        There are no other variables that must be set to get this to work
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
