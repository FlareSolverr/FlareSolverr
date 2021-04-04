let requests = 0

const LOG_HTML: boolean = process.env.LOG_HTML == 'true';

export default {
  incRequests: () => { requests++ },
  html(html: string) {
    if (LOG_HTML)
      this.debug(html)
  },
  ...require('console-log-level')(
    {level: process.env.LOG_LEVEL || 'info',
      prefix(level: string) {
        const req = (requests > 0) ? ` REQ-${requests}` : '';
        return `${new Date().toISOString()} ${level.toUpperCase()}${req}`
      }
    }
  )
}
