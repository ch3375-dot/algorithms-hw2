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
from src.hash_table import ChainedHashTable
from src.linear_probing import LinearProbingHashTable


DEFAULT_PORT = 8000
DEFAULT_CAPACITY = 97
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
        forwarded_host = self.headers.get("X-Forwarded-Host")
        if forwarded_host is None:
            host = self.headers.get("Host")
        else:
            host = forwarded_host.split(",", 1)[0].strip()
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

    @classmethod
    def _comparison_markup(
        cls,
        title: str,
        chained_table: shortener.ChainedHashTable,
    ) -> str:
        parts = [
            f"<section><h2>{escape(title)}</h2>"
            f"<p>버킷 수: capacity {chained_table.capacity}</p>"
            '<div class="table-method"><h3>개별 체이닝</h3><ol>'
        ]
        for index, chain in enumerate(chained_table.buckets):
            parts.append(
                f"<li><strong>칸 {index}</strong>: "
                f"{cls._chain_entries(chain, index, chained_table.capacity)}"
                "</li>"
            )
        parts.append("</ol></div>")

        linear_table = LinearProbingHashTable(chained_table.capacity)
        keys_inserted = 0
        insertion_failed = False
        for chain in chained_table.buckets:
            for key, value in chain:
                try:
                    linear_table.put(key, value)
                except OverflowError:
                    insertion_failed = True
                    break
                keys_inserted += 1
            if insertion_failed:
                break

        parts.append(
            '<div class="table-method"><h3>선형 탐지</h3>'
            f"<p>같은 키-값 쌍 {keys_inserted}개를 삽입했습니다.</p><ol>"
        )
        for index, entry in enumerate(linear_table.buckets):
            if entry is None:
                parts.append(f"<li><strong>칸 {index}</strong>: (빈 칸)</li>")
            elif isinstance(entry, tuple):
                key, value = entry
                home = linear_table._bucket_index(key)
                displacement = (index - home) % linear_table.capacity
                path = " → ".join(
                    str((home + offset) % linear_table.capacity)
                    for offset in range(displacement + 1)
                )
                parts.append(
                    cls._entry_markup(
                        key,
                        value,
                        linear_table.capacity,
                        home,
                        collision=displacement > 0,
                        location=index,
                        probe_path=path,
                        displacement=displacement,
                    )
                )
            else:
                parts.append(
                    f"<li><strong>칸 {index}</strong>: (삭제 표시)</li>"
                )
        parts.append("</ol></div>")
        if insertion_failed:
            parts.append(
                "<p>선형 탐지 테이블이 가득 차 나머지 키를 삽입하지 못했습니다.</p>"
            )
        parts.append("</section>")
        return "".join(parts)

    @classmethod
    def _chain_entries(
        cls,
        chain: list[tuple[str, object]],
        bucket_index: int,
        capacity: int,
    ) -> str:
        if not chain:
            return "<code>(빈 버킷)</code>"
        entries = [
            cls._entry_markup(
                key,
                value,
                capacity,
                bucket_index,
                collision=len(chain) > 1,
                location=bucket_index,
            )
            for key, value in chain
        ]
        return "<ul>" + "".join(entries) + "</ul>"

    @classmethod
    def _entry_markup(
        cls,
        key: str,
        value: object,
        capacity: int,
        home: int,
        *,
        collision: bool,
        location: int,
        probe_path: str | None = None,
        displacement: int | None = None,
    ) -> str:
        key_text = escape(str(key))
        value_text = escape(str(value))
        collision_class = ' class="collision"' if collision else ""
        collision_badge = (
            '<strong class="collision-badge">충돌</strong> '
            if collision
            else ""
        )
        details = cls._hash_steps(key, capacity)
        position = f"홈 칸 {home}, 실제 칸 {location}"
        if displacement is not None:
            position += f", 이동 거리 {displacement}, 탐색 경로 {probe_path}"
        return (
            f"<li{collision_class}>{collision_badge}"
            f"<code>{key_text}: {value_text}</code> "
            f"<span>({position})</span>{details}</li>"
        )

    @staticmethod
    def _hash_steps(key: str, capacity: int) -> str:
        value = 0
        parts = [
            '<details><summary>호너 해시 계산 과정</summary>',
            f"<p>키: <code>{escape(key)}</code></p>",
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
                f"<p>최종 칸: {value}</p>",
                "</details>",
            )
        )
        return "".join(parts)

    @classmethod
    def _render_table(cls, query: str) -> str:
        parts = [
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            "<title>해시 테이블</title></head><body>"
            "<style>.collision{background:#fff0c2;border-left:4px solid "
            "#d97706;padding:.4em}.collision-badge{color:#92400e}"
            ".table-method{margin:1em 0}</style>"
            "<h1>해시 테이블 상태 비교</h1>",
            cls._comparison_markup("URL → 코드", shortener._URL_TO_CODE),
            cls._comparison_markup("코드 → URL", shortener._CODE_TO_URL),
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

    @staticmethod
    def _configure_capacity(capacity: int) -> None:
        shortener._URL_TO_CODE = ChainedHashTable(capacity)
        shortener._CODE_TO_URL = ChainedHashTable(capacity)
        shortener._NEXT_ID = 0


def serve(port: int = DEFAULT_PORT, capacity: int = DEFAULT_CAPACITY) -> None:
    ShortenerRequestHandler._configure_capacity(capacity)
    server = HTTPServer((HOST, port), ShortenerRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the URL shortener server.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--capacity", type=int, default=DEFAULT_CAPACITY)
    return parser


def main() -> None:
    arguments = _argument_parser().parse_args()
    if arguments.capacity <= 0:
        raise SystemExit("--capacity must be greater than zero")
    serve(arguments.port, arguments.capacity)


if __name__ == "__main__":
    main()
