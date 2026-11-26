import unittest
from unittest.mock import patch

from src import shortener


class ShortenerTests(unittest.TestCase):
    def test_repeated_url_returns_the_existing_code(self):
        url = "https://same.example/path"

        first_code = shortener.shorten(url)
        second_code = shortener.shorten(url)

        self.assertEqual(second_code, first_code)
        self.assertEqual(shortener.expand(first_code), url)

    def test_different_urls_receive_unique_codes_and_expand_both_directions(self):
        first_url = "https://first.example/path"
        second_url = "https://second.example/path"

        first_code = shortener.shorten(first_url)
        second_code = shortener.shorten(second_url)

        self.assertNotEqual(first_code, second_code)
        self.assertEqual(shortener.expand(first_code), first_url)
        self.assertEqual(shortener.expand(second_code), second_url)

    def test_reserved_code_is_skipped(self):
        url = "https://reserved.example/path"
        with patch.object(shortener, "encode", side_effect=("table", "usable")):
            code = shortener.shorten(url)

        self.assertEqual(code, "usable")
        self.assertEqual(shortener.expand(code), url)

    def test_http_and_https_urls_are_valid_and_distinct(self):
        http_url = "http://example.test/path"
        https_url = "https://example.test/path"

        http_code = shortener.shorten(http_url)
        https_code = shortener.shorten(https_url)

        self.assertNotEqual(http_code, https_code)
        self.assertEqual(shortener.expand(http_code), http_url)
        self.assertEqual(shortener.expand(https_code), https_url)

    def test_invalid_scheme_host_or_surrounding_whitespace_is_rejected(self):
        invalid_urls = (
            "ftp://example.test/path",
            "https:///path",
            "https://",
            " https://example.test/path",
            "https://example.test/path ",
        )
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    shortener.shorten(url)

    def test_unregistered_code_raises_key_error(self):
        with self.assertRaises(KeyError):
            shortener.expand("not-registered-code")


if __name__ == "__main__":
    unittest.main()
