import unittest

from bottle import Bottle, request
from webtest import TestApp

from bottle_plugins.error_plugin import error_plugin


class TestErrorPlugin(unittest.TestCase):

    def setUp(self):
        app = Bottle()

        @app.post('/json')
        def parse_json():
            return request.json

        @app.get('/error')
        def raise_error():
            raise RuntimeError('unexpected failure')

        app.install(error_plugin)
        self.app = TestApp(app)

    def test_preserves_bottle_http_error_status(self):
        response = self.app.post(
            '/json',
            params='{',
            content_type='application/json',
            status=400
        )

        self.assertEqual(400, response.status_code)

    def test_converts_unexpected_exception_to_500(self):
        response = self.app.get('/error', status=500)

        self.assertEqual(500, response.status_code)
        self.assertEqual({'error': 'unexpected failure'}, response.json)


if __name__ == '__main__':
    unittest.main()
