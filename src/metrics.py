from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

REQUEST_COUNTER = Counter(
    name='flaresolverr_requests',
    documentation='Total Flaresolverr Requests',
    labelnames=[
        'domain',
        'status_code']
    )

REQUEST_DURATION = Histogram(
    name='flaresolverr_request_duration',
    documentation='Request Duration in seconds',
    labelnames=[
        'domain'
    ],
    buckets=[0, 10, 20, 30, 40, 50, 60, 70]
    )
CHALLENGE_COUNTER = Counter(
    name='flaresolverr_challenges',
    documentation='Total cloudflare Challenges',
    labelnames=[
        'domain',
        'status']
    )
REQUEST_IN_PROGRESS = Gauge(
    name='flaresolverr_active_requests',
    documentation='Total active requests',
    )


def serve(port):
    start_http_server(port=port)
    while True:
        time.sleep(5)


def start_metrics_http_server():
    """Main entry point"""
    from threading import Thread
    exporter_port = 8190
    Thread(
        target=serve,
        kwargs=dict(port=exporter_port),
        daemon=True,
    ).start()
