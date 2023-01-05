import json
import logging
import os
import sys

from bottle import run, response, Bottle, request

from flaresolverr.bottle_plugins.error_plugin import error_plugin
from flaresolverr.bottle_plugins.logger_plugin import logger_plugin
from flaresolverr.dtos import IndexResponse, V1RequestBase
import flaresolverr.flaresolverr_service as flaresolverr_service
import flaresolverr.utils as utils


class JSONErrorBottle(Bottle):
    """
    Handle 404 errors
    """
    def default_error_handler(self, res):
        response.content_type = 'application/json'
        return json.dumps(dict(error=res.body, status_code=res.status_code))


app = JSONErrorBottle()

# plugin order is important
app.install(logger_plugin)
app.install(error_plugin)


@app.route('/')
def index():
    """
    Show welcome message
    """
    res = flaresolverr_service.index_endpoint()
    return utils.object_to_dict(res)


@app.route('/health')
def health():
    """
    Healthcheck endpoint.
    This endpoint is special because it doesn't print traces
    """
    res = flaresolverr_service.health_endpoint()
    return utils.object_to_dict(res)


@app.post('/v1')
def controller_v1():
    """
    Controller v1
    """
    req = V1RequestBase(request.json)
    res = flaresolverr_service.controller_v1_endpoint(req)
    if res.__error_500__:
        response.status = 500
    return utils.object_to_dict(res)


def cli_run():
    # validate configuration
    log_level = os.environ.get('LOG_LEVEL', 'info').upper()
    log_html = utils.get_config_log_html()
    headless = utils.get_config_headless()
    server_host = os.environ.get('HOST', '0.0.0.0')
    server_port = int(os.environ.get('PORT', 8191))

    # configure logger
    logger_format = '%(asctime)s %(levelname)-8s %(message)s'
    if log_level == 'DEBUG':
        logger_format = '%(asctime)s %(levelname)-8s ReqId %(thread)s %(message)s'
    logging.basicConfig(
        format=logger_format,
        level=log_level,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # disable warning traces from urllib3
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.WARNING)
    logging.getLogger('undetected_chromedriver').setLevel(logging.WARNING)

    logging.info(f'FlareSolverr {utils.get_flaresolverr_version()}')
    logging.debug('Debug log enabled')

    # test browser installation
    flaresolverr_service.test_browser_installation()

    # start webserver
    # default server 'wsgiref' does not support concurrent requests
    run(app, host=server_host, port=server_port, quiet=True, server='waitress')


if __name__ == "__main__":
    cli_run()
