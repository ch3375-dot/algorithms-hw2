"""In-memory URL shortening backed by chained hash tables."""

from urllib.parse import urlsplit

from src.base62 import encode
from src.hash_table import ChainedHashTable


_URL_TO_CODE = ChainedHashTable()
_CODE_TO_URL = ChainedHashTable()
_NEXT_ID = 0
_RESERVED_CODES = ("table", "shorten")


def _validate_url(url: str) -> None:
    if not isinstance(url, str) or any(character.isspace() for character in url):
        raise ValueError("url must be a whitespace-free HTTP or HTTPS URL")
    try:
        parsed = urlsplit(url)
    except ValueError as error:
        raise ValueError("url must be a valid HTTP or HTTPS URL") from error
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise ValueError("url must have an HTTP or HTTPS scheme and a host")


def shorten(url: str) -> str:
    global _NEXT_ID

    _validate_url(url)
    if _URL_TO_CODE.contains(url):
        return _URL_TO_CODE.get(url)

    while True:
        code = encode(_NEXT_ID)
        _NEXT_ID += 1
        if code in _RESERVED_CODES or _CODE_TO_URL.contains(code):
            continue
        _URL_TO_CODE.put(url, code)
        _CODE_TO_URL.put(code, url)
        return code


def expand(code: str) -> str:
    return _CODE_TO_URL.get(code)
