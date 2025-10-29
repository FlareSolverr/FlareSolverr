from bottle import response
import logging


def error_plugin(callback):
    """
    Bottle plugin to handle exceptions
    https://stackoverflow.com/a/32764250
    """

    def wrapper(*args, **kwargs):
        try:
            actual_response = callback(*args, **kwargs)
        except Exception as e:
            logging.error(str(e))
            actual_response = {
                "error": str(e)
            }
            response.status = 500
        return actual_response

    return wrapper
