import logging
import os
import urllib.parse

from dtos import V1ResponseBase
from metrics import start_metrics_http_server, REQUEST_COUNTER, REQUEST_DURATION

PROMETHEUS_ENABLED = os.environ.get('PROMETHEUS_ENABLED', 'false').lower() == 'true'
PROMETHEUS_PORT = int(os.environ.get('PROMETHEUS_PORT', 8192))


def setup():
    if PROMETHEUS_ENABLED:
        start_metrics_http_server(PROMETHEUS_PORT)


def prometheus_plugin(callback):
    """
    Bottle plugin to expose Prometheus metrics
    http://bottlepy.org/docs/dev/plugindev.html
    """
    def wrapper(*args, **kwargs):
        actual_response = callback(*args, **kwargs)

        if PROMETHEUS_ENABLED:
            try:
                export_metrics(actual_response)
            except Exception as e:
                logging.warning("Error exporting metrics: " + str(e))

        return actual_response

    def export_metrics(actual_response):
        res = V1ResponseBase(actual_response)

        if res.startTimestamp is None or res.endTimestamp is None:
            # skip management and healthcheck endpoints
            return

        domain = "unknown"
        if res.solution and res.solution.url:
            parsed_url = urllib.parse.urlparse(res.solution.url)
            domain = parsed_url.hostname

        run_time = (res.endTimestamp - res.startTimestamp) / 1000
        REQUEST_DURATION.labels(domain=domain).observe(run_time)

        result = "unknown"
        if res.message == "Challenge solved!":
            result = "solved"
        elif res.message == "Challenge not detected!":
            result = "not_detected"
        elif res.message.startswith("Error"):
            result = "error"
        REQUEST_COUNTER.labels(domain=domain, result=result).inc()

    return wrapper
