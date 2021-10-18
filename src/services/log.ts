let requests = 0

const LOG_HTML: boolean = process.env.LOG_HTML == 'true';

function toIsoString(date: Date) {
  // this function fixes Date.toISOString() adding timezone
  let tzo = -date.getTimezoneOffset(),
      dif = tzo >= 0 ? '+' : '-',
      pad = function(num: number) {
        let norm = Math.floor(Math.abs(num));
        return (norm < 10 ? '0' : '') + norm;
      };

  return date.getFullYear() +
      '-' + pad(date.getMonth() + 1) +
      '-' + pad(date.getDate()) +
      'T' + pad(date.getHours()) +
      ':' + pad(date.getMinutes()) +
      ':' + pad(date.getSeconds()) +
      dif + pad(tzo / 60) +
      ':' + pad(tzo % 60);
}

export default {
  incRequests: () => {
      requests++
  },
  html(html: string) {
    if (LOG_HTML) {
        this.debug(html)
    }
  },
  ...require('console-log-level')(
    {level: process.env.LOG_LEVEL || 'info',
      prefix(level: string) {
        const req = (requests > 0) ? ` REQ-${requests}` : '';
        return `${toIsoString(new Date())} ${level.toUpperCase()}${req}`
      }
    }
  )
}
