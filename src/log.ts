let requests = 0

const LOG_HTML: boolean = Boolean(process.env.LOG_HTML) || false

export default {
  incRequests: () => { requests++ },
  html(html: string) {
    if (LOG_HTML)
      this.debug(html)
  },
  ...require('console-log-level')(
    {
      level: process.env.LOG_LEVEL || 'debug',
      prefix(level: string) {
        return `${new Date().toISOString()} ${level.toUpperCase()} REQ-${requests}`
      }
    }
  )
}