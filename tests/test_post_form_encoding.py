import ast
import unittest
from html import escape, unescape
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qsl, quote, unquote
from unittest.mock import Mock


class PostFormEncodingTests(unittest.TestCase):
    def test_spaces_and_special_characters(self):
        source = Path("src/flaresolverr_service.py").read_text()
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_post_request"
        )

        namespace = {
            "escape": escape,
            "parse_qsl": parse_qsl,
            "quote": quote,
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]),
                     "<test>", "exec"), namespace)

        driver = Mock()
        request = SimpleNamespace(
            url="https://example.com/login",
            postData="username=Gordo+Geklo&password=a%2Bb%26c&empty=",
        )

        namespace["_post_request"](request, driver)

        data_url = driver.get.call_args.args[0]
        html = unescape(unquote(data_url.split(",", 1)[1]))

        self.assertIn('value="Gordo Geklo"', html)
        self.assertIn('value="a+b&amp;c"', unquote(data_url.split(",", 1)[1]))
        self.assertIn('name="empty" value=""', html)


if __name__ == "__main__":
    unittest.main()
