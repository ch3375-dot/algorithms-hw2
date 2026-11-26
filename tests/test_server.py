import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]

        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.opener = urllib.request.build_opener(_NoRedirectHandler)
        cls.server = subprocess.Popen(
            [
                sys.executable,
                "src/server.py",
                "--port",
                str(cls.port),
            ],
            cwd=REPOSITORY_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if cls.server.poll() is not None:
                output, _ = cls.server.communicate()
                raise RuntimeError(
                    "server exited during startup: "
                    + output.decode(errors="replace")
                )
            try:
                with urllib.request.urlopen(
                    f"{cls.base_url}/",
                    timeout=0.2,
                ) as response:
                    if response.status == 200:
                        return
            except urllib.error.URLError:
                time.sleep(0.05)

        cls.server.terminate()
        output, _ = cls.server.communicate(timeout=2)
        raise RuntimeError(
            "server did not start in time: " + output.decode(errors="replace")
        )

    @classmethod
    def tearDownClass(cls):
        if cls.server.poll() is None:
            cls.server.terminate()
            try:
                cls.server.wait(timeout=2)
            except subprocess.TimeoutExpired:
                cls.server.kill()
                cls.server.wait(timeout=2)
        if cls.server.stdout is not None:
            cls.server.stdout.close()

    def _request(self, path, method="GET", body=None, headers=None):
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=headers or {},
            method=method,
        )
        return self.opener.open(request, timeout=2)

    def _assert_http_error(
        self,
        expected_status,
        path,
        method="GET",
        body=None,
        headers=None,
    ):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self._request(path, method=method, body=body, headers=headers)
        self.assertEqual(raised.exception.code, expected_status)
        raised.exception.close()

    def test_home_page_returns_an_html_form(self):
        with self._request("/") as response:
            body = response.read().decode()

        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers.get_content_type(), "text/html")
        self.assertIn("<form", body.lower())
        self.assertIn("/shorten", body)

    def test_json_and_form_submissions_return_created_results(self):
        json_url = "https://json.example/path"
        with self._request(
            "/shorten",
            method="POST",
            body=json.dumps({"url": json_url}).encode(),
            headers={"Content-Type": "application/json"},
        ) as response:
            json_body = json.loads(response.read())
            self.assertEqual(response.status, 201)
            self.assertEqual(response.headers.get_content_type(), "application/json")
        self.assertEqual(json_body["url"], json_url)
        self.assertTrue(json_body["code"])

        form_url = "https://form.example/path"
        with self._request(
            "/shorten",
            method="POST",
            body=urllib.parse.urlencode({"url": form_url}).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as response:
            html_body = response.read().decode()
            self.assertEqual(response.status, 201)
            self.assertEqual(response.headers.get_content_type(), "text/html")
        self.assertIn(form_url, html_body)

    def test_table_page_and_key_hash_calculation_are_rendered(self):
        with self._request("/table") as response:
            table_body = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), "text/html")

        key = "table-key"
        query = urllib.parse.urlencode({"key": key})
        with self._request(f"/table?{query}") as response:
            keyed_body = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), "text/html")
        self.assertIn(key, keyed_body)
        self.assertNotEqual(keyed_body, table_body)

    def test_registered_code_redirects_to_original_url(self):
        original_url = "https://redirect.example/path"
        with self._request(
            "/shorten",
            method="POST",
            body=json.dumps({"url": original_url}).encode(),
            headers={"Content-Type": "application/json"},
        ) as response:
            code = json.loads(response.read())["code"]

        with self.assertRaises(urllib.error.HTTPError) as raised:
            self._request(f"/{urllib.parse.quote(code)}")
        self.assertEqual(raised.exception.code, 302)
        self.assertEqual(raised.exception.headers["Location"], original_url)
        raised.exception.close()

    def test_invalid_json_url_and_request_format_return_bad_request(self):
        self._assert_http_error(
            400,
            "/shorten",
            method="POST",
            body=b'{"url":',
            headers={"Content-Type": "application/json"},
        )
        self._assert_http_error(
            400,
            "/shorten",
            method="POST",
            body=json.dumps({"url": "ftp://example.test"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        self._assert_http_error(
            400,
            "/shorten",
            method="POST",
            body=b"url=https%3A%2F%2Fexample.test",
            headers={"Content-Type": "text/plain"},
        )

    def test_unknown_code_and_unsupported_request_path_return_not_found(self):
        self._assert_http_error(404, "/not-registered-code")
        self._assert_http_error(404, "/unknown-route", method="POST")


if __name__ == "__main__":
    unittest.main()
