import unittest
from unittest.mock import patch

from src.hash_table import ChainedHashTable
from src import shortener
from src.server import ShortenerRequestHandler, _argument_parser


def _bucket_index(key, capacity):
    value = 0
    for byte in key.encode("utf-8"):
        value = (31 * value + byte) % capacity
    return value


def _colliding_keys(capacity, count):
    first = "https://naver.com"
    keys = [first]
    target = _bucket_index(first, capacity)
    for candidate in (
        "https://google.com",
        "https://github.com",
        "https://example.com",
        "https://openai.com",
        "https://python.org",
        "https://wikipedia.org",
        "https://microsoft.com",
        "https://apple.com",
        "https://amazon.com",
        "https://youtube.com",
        "https://daum.net",
        "https://kakao.com",
    ):
        if _bucket_index(candidate, capacity) == target:
            keys.append(candidate)
            if len(keys) == count:
                return keys

    number = 0
    while len(keys) < count:
        candidate = f"https://collision-{number}.example"
        if _bucket_index(candidate, capacity) == target:
            keys.append(candidate)
        number += 1
    return keys


class ServerCollisionDemoTests(unittest.TestCase):
    def test_capacity_option_defaults_to_97_and_accepts_custom_value(self):
        parser = _argument_parser()

        self.assertEqual(parser.parse_args([]).capacity, 97)
        self.assertEqual(parser.parse_args(["--capacity", "8"]).capacity, 8)

    def test_capacity_configures_both_shortener_tables(self):
        with (
            patch.object(shortener, "_URL_TO_CODE"),
            patch.object(shortener, "_CODE_TO_URL"),
            patch.object(shortener, "_NEXT_ID", 123),
        ):
            ShortenerRequestHandler._configure_capacity(8)

            self.assertEqual(shortener._URL_TO_CODE.capacity, 8)
            self.assertEqual(shortener._CODE_TO_URL.capacity, 8)
            self.assertEqual(shortener._NEXT_ID, 0)

    def test_table_page_shows_each_hash_calculation_and_collision_marker(self):
        capacity = 8
        keys = _colliding_keys(capacity, 2)
        self.assertEqual(
            _bucket_index(keys[0], capacity),
            _bucket_index(keys[1], capacity),
        )
        chained_table = ChainedHashTable(capacity)
        reverse_table = ChainedHashTable(capacity)
        for index, key in enumerate(keys):
            chained_table.put(key, f"code-{index}")
            reverse_table.put(f"code-{index}", key)

        with (
            patch("src.server.shortener._URL_TO_CODE", chained_table),
            patch("src.server.shortener._CODE_TO_URL", reverse_table),
        ):
            page = ShortenerRequestHandler._render_table("")

        self.assertIn("capacity 8", page)
        self.assertIn("호너 해시 계산 과정", page)
        self.assertIn("h = (31 ×", page)
        self.assertIn("최종 칸", page)
        self.assertIn("충돌", page)
        self.assertIn("collision", page)
        for key in keys:
            self.assertIn(key, page)


if __name__ == "__main__":
    unittest.main()
