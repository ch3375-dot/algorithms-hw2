import unittest
from unittest.mock import patch

from src.hash_table import ChainedHashTable
from src.server import ShortenerRequestHandler


def _colliding_keys(capacity, count):
    keys = []
    home_slot = None
    for number in range(capacity * count * 30):
        key = f"table-collision-{number}"
        value = 0
        for byte in key.encode("utf-8"):
            value = (31 * value + byte) % capacity
        if home_slot is None:
            home_slot = value
        if value == home_slot:
            keys.append(key)
            if len(keys) == count:
                return keys
    raise AssertionError("could not find colliding keys")


class ServerTableComparisonTests(unittest.TestCase):
    def test_table_view_shows_both_tables_and_linear_probe_distance(self):
        capacity = 97
        keys = _colliding_keys(capacity, 3)
        chained_table = ChainedHashTable(capacity)
        reverse_table = ChainedHashTable(capacity)
        for index, key in enumerate(keys):
            chained_table.put(key, f"value-{index}")
            reverse_table.put(f"value-{index}", key)

        with (
            patch("src.server.shortener._URL_TO_CODE", chained_table),
            patch("src.server.shortener._CODE_TO_URL", reverse_table),
        ):
            page = ShortenerRequestHandler._render_table("")

        self.assertIn("개별 체이닝", page)
        self.assertIn("선형 탐지", page)
        self.assertIn("홈 칸", page)
        self.assertIn("이동 거리", page)
        for key in keys:
            self.assertIn(key, page)

    def test_table_view_exposes_the_probed_slots_in_order(self):
        capacity = 7
        keys = _colliding_keys(capacity, 3)
        chained_table = ChainedHashTable(capacity)
        reverse_table = ChainedHashTable(capacity)
        for index, key in enumerate(keys):
            chained_table.put(key, f"value-{index}")
            reverse_table.put(f"value-{index}", key)

        with (
            patch("src.server.shortener._URL_TO_CODE", chained_table),
            patch("src.server.shortener._CODE_TO_URL", reverse_table),
        ):
            page = ShortenerRequestHandler._render_table("")

        self.assertIn("경로", page)


if __name__ == "__main__":
    unittest.main()
