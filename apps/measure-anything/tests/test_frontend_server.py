from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
from util.frontend_server import FrontendServer


class FrontendServerTests(unittest.TestCase):
    def test_built_assets_are_served_with_explicit_backend_connection(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / "index.html").write_text('<script src="asset.js"></script>')
            (directory / "asset.js").write_text('console.log("frontend")')
            server = FrontendServer("127.0.0.1", 0, directory)
            server.start()
            try:
                url = server.url(9876)
                self.assertEqual(
                    parse_qs(urlsplit(url).query), {"ws_url": ["ws://127.0.0.1:9876"]}
                )
                with urlopen(url, timeout=2) as response:
                    self.assertIn(b"asset.js", response.read())
                with urlopen(
                    f"http://127.0.0.1:{server.port}/asset.js", timeout=2
                ) as response:
                    self.assertEqual(response.read(), b'console.log("frontend")')
                with self.assertRaises(HTTPError) as error:
                    urlopen(f"http://127.0.0.1:{server.port}/missing.js", timeout=2)
                self.assertEqual(error.exception.code, 404)
            finally:
                server.stop()

    def test_missing_build_reports_the_build_command_before_binding(self):
        with TemporaryDirectory() as folder:
            with self.assertRaisesRegex(
                FileNotFoundError, "npm --prefix frontend run build"
            ):
                FrontendServer("127.0.0.1", 0, Path(folder))

    def test_server_can_close_before_start(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / "index.html").touch()
            server = FrontendServer("0.0.0.0", 0, directory)
            self.assertIn("127.0.0.1", server.url(8765))
            server.stop()


if __name__ == "__main__":
    unittest.main()
