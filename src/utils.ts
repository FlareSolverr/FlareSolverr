import * as fs from 'fs'
import * as Path from 'path'
import { promisify } from 'util'

export const sleep = promisify(setTimeout)

// recursive fs.rmdir needs node version 12:
// https://github.com/ngosang/FlareSolverr/issues/5#issuecomment-655572712
export function deleteFolderRecursive(path: string) {
  if (fs.existsSync(path)) {
    fs.readdirSync(path).forEach((file) => {
      const curPath = Path.join(path, file)
      if (fs.lstatSync(curPath).isDirectory()) { // recurse
        deleteFolderRecursive(curPath)
      } else { // delete file
        fs.unlinkSync(curPath)
      }
    })
    fs.rmdirSync(path)
  }
}

export const removeEmptyFields = (o: Record<string, any>): typeof o => {
  const r: typeof o = {}
  for (const k in o) {
    if (o[k] !== undefined) {
      r[k] = o[k]
    }
  }
  return r
}