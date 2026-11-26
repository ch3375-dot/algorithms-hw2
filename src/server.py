"""HTTP interface for the in-memory URL shortener."""

import argparse
import json
import sys
from collections.abc import Mapping
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import shortener


DEFAULT_PORT = 8000
HOST = "0.0.0.0"
RESERVED_PATHS = ("table", "shorten")


class ShortenerRequestHandler(BaseHTTPRequestHandler):
    def _send_bytes(
        self,
        status: int,
        content_type: str,
        body: bytes,
        headers: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, body: str) -> None:
        self._send_bytes(
            status,
            "text/html; charset=utf-8",
            body.encode("utf-8"),
        )

    def _send_error_text(self, status: int, message: str) -> None:
        self._send_bytes(
            status,
            "text/plain; charset=utf-8",
            message.encode("utf-8"),
        )

    def _read_body(self) -> bytes | None:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            return None
        try:
            length = int(content_length)
        except ValueError:
            return None
        if length < 0:
            return None
        return self.rfile.read(length)

    def _request_origin(self) -> str | None:
        host = self.headers.get("Host")
        if not host or any(character.isspace() for character in host):
            return None
        try:
            parsed_host = urlsplit(f"//{host}")
            if (
                not parsed_host.hostname
                or parsed_host.username is not None
                or parsed_host.password is not None
                or parsed_host.path
                or parsed_host.query
                or parsed_host.fragment
            ):
                return None
            parsed_host.port
        except ValueError:
            return None

        forwarded_proto = (
            self.headers.get("X-Forwarded-Proto", "")
            .split(",", 1)[0]
            .strip()
            .lower()
        )
        scheme = "https" if forwarded_proto == "https" else "http"
        return f"{scheme}://{host}"

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        if request.path == "/":
            self._send_html(
                200,
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                "<title>URL 단축기</title></head><body>"
                "<h1>URL 단축기</h1>"
                '<form method="post" action="/shorten">'
                '<label for="url">긴 URL</label>'
                '<input id="url" name="url" type="url" required>'
                '<button type="submit">단축</button>'
                "</form></body></html>",
            )
            return

        if request.path == "/table":
            self._send_html(200, self._render_table(request.query))
            return

        path_parts = request.path.split("/")
        if (
            len(path_parts) != 2
            or not path_parts[1]
            or path_parts[1] in RESERVED_PATHS
        ):
            self._send_error_text(404, "Not found")
            return

        try:
            url = shortener.expand(path_parts[1])
        except KeyError:
            self._send_error_text(404, "Not found")
            return
        self._send_bytes(
            302,
            "text/plain; charset=utf-8",
            b"",
            (("Location", url),),
        )

    def do_POST(self) -> None:
        request_path = urlsplit(self.path).path
        if request_path != "/shorten":
            self._send_error_text(404, "Not found")
            return

        body = self._read_body()
        if body is None:
            self._send_error_text(400, "Invalid request body")
            return

        content_type = self.headers.get_content_type()
        if content_type == "application/json":
            url = self._read_json_url(body)
        elif content_type == "application/x-www-form-urlencoded":
            url = self._read_form_url(body)
        else:
            self._send_error_text(400, "Unsupported content type")
            return

        if url is None:
            self._send_error_text(400, "Invalid request body")
            return
        origin = None
        if content_type == "application/x-www-form-urlencoded":
            origin = self._request_origin()
            if origin is None:
                self._send_error_text(400, "Invalid Host header")
                return
        try:
            code = shortener.shorten(url)
        except ValueError:
            self._send_error_text(400, "Invalid URL")
            return

        if content_type == "application/json":
            response_body = (
                '{"code":'
                + json.dumps(code, ensure_ascii=False)
                + ',"url":'
                + json.dumps(url, ensure_ascii=False)
                + "}"
            )
            self._send_bytes(
                201,
                "application/json; charset=utf-8",
                response_body.encode("utf-8"),
            )
            return

        short_url = f"{origin}/{code}"
        self._send_html(
            201,
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            "<title>단축 URL</title></head><body>"
            "<h1>단축 URL</h1>"
            f"<p>코드: <code>{escape(code)}</code></p>"
            f'<p>단축 URL: <a href="{escape(short_url, quote=True)}">'
            f"{escape(short_url)}</a></p>"
            '<label for="short-url">복사할 단축 URL</label>'
            f'<input id="short-url" type="text" readonly '
            f'value="{escape(short_url, quote=True)}">'
            f'<p>원본 URL: <a href="{escape(url, quote=True)}">'
            f"{escape(url)}</a></p>"
            '<p><a href="/">다른 URL 단축하기</a></p>'
            "</body></html>",
        )

    @staticmethod
    def _read_json_url(body: bytes) -> str | None:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, Mapping):
            return None
        url = payload.get("url")
        return url if isinstance(url, str) else None

    @staticmethod
    def _read_form_url(body: bytes) -> str | None:
        try:
            fields = parse_qsl(
                body.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
            )
        except (UnicodeDecodeError, ValueError):
            return None
        urls = [value for name, value in fields if name == "url"]
        if len(urls) != 1:
            return None
        return urls[0]

    @staticmethod
    def _table_markup(title: str, table: shortener.ChainedHashTable) -> str:
        parts = [f"<h2>{escape(title)}</h2><ol>"]
        for index, chain in enumerate(table.buckets):
            pairs = " → ".join(
                f"{escape(str(key))}: {escape(str(value))}"
                for key, value in chain
            )
            parts.append(
                f"<li><strong>{index}</strong>: "
                f"<code>{pairs if pairs else '(빈 버킷)'}</code></li>"
            )
        parts.append("</ol>")
        return "".join(parts)

    @staticmethod
    def _hash_steps(key: str, capacity: int) -> str:
        value = 0
        parts = [
            f"<h2>호너 해시 계산: <code>{escape(key)}</code></h2>",
            f"<p>UTF-8 바이트: {key.encode('utf-8').hex(' ')}</p>",
            "<ol>",
            "<li>초기값: h = 0</li>",
        ]
        for byte in key.encode("utf-8"):
            next_value = (31 * value + byte) % capacity
            parts.append(
                f"<li>h = (31 × {value} + {byte}) mod {capacity} "
                f"= {next_value}</li>"
            )
            value = next_value
        parts.extend(
            (
                "</ol>",
                f"<p>버킷 인덱스: {value}</p>",
            )
        )
        return "".join(parts)

    @classmethod
    def _render_table(cls, query: str) -> str:
        parts = [
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            "<title>해시 테이블</title></head><body>"
            "<h1>해시 테이블 버킷</h1>",
            cls._table_markup("URL → 코드", shortener._URL_TO_CODE),
            cls._table_markup("코드 → URL", shortener._CODE_TO_URL),
        ]
        query_key = None
        has_key = False
        for name, value in parse_qsl(query, keep_blank_values=True):
            if name == "key":
                query_key = value
                has_key = True
                break
        if has_key:
            parts.append(
                cls._hash_steps(
                    query_key if query_key is not None else "",
                    shortener._URL_TO_CODE.capacity,
                )
            )
        parts.append("</body></html>")
        return "".join(parts)


def serve(port: int = DEFAULT_PORT) -> None:
    server = HTTPServer((HOST, port), ShortenerRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the URL shortener server.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments = parser.parse_args()
    serve(arguments.port)


if __name__ == "__main__":
    main()
