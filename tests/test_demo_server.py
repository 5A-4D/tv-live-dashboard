"""The browser demo must not expose credentials, build outputs or repository internals."""
import importlib.util
from pathlib import Path
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

SPEC = importlib.util.spec_from_file_location('demo_serve', Path(__file__).resolve().parents[1] / 'demo/serve.py')
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


class DemoServerTests(unittest.TestCase):
    def test_static_dashboard_and_fictional_fixtures_are_available(self):
        with demo.demo_server() as origin:
            for path, marker in [('/demo/', b'TV Live Dashboard'),
                                 ('/demo/demo.js', b'Fictional offline fixtures'),
                                 ('/web/style.css', b'background')]:
                with urlopen(origin + path, timeout=3) as response:
                    self.assertIn(marker, response.read())

    def test_private_state_build_outputs_and_git_are_never_served(self):
        with demo.demo_server() as origin:
            for path in ['/state/private/tv-config.json', '/build/tv-live-dashboard.apk',
                         '/.git/config', '/demo/../state/private/dashboard_token',
                         '/demo/%2e%2e/state/private/signing_password', '/demo/capture.py']:
                with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                    urlopen(origin + path, timeout=3)
                self.assertEqual(error.exception.code, 403)

    def test_asset_directories_do_not_expose_file_listings(self):
        with demo.demo_server() as origin:
            with self.assertRaises(HTTPError) as error:
                urlopen(origin + '/web/assets/', timeout=3)
            self.assertEqual(error.exception.code, 403)
