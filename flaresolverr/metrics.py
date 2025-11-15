import logging

from prometheus_client import Counter, Histogram, start_http_server
import time

REQUEST_COUNTER = Counter(
    name='flaresolverr_request',
    documentation='Total requests with result',
    labelnames=['domain', 'result']
)
REQUEST_DURATION = Histogram(
    name='flaresolverr_request_duration',
    documentation='Request duration in seconds',
    labelnames=['domain'],
    buckets=[0, 10, 25, 50]
)


def serve(port):
    start_http_server(port=port)
    while True:
        time.sleep(600)


def start_metrics_http_server(prometheus_port: int):
    logging.info(f"Serving Prometheus exporter on http://0.0.0.0:{prometheus_port}/metrics")
    from threading import Thread
    Thread(
        target=serve,
        kwargs=dict(port=prometheus_port),
        daemon=True,
    ).start()
