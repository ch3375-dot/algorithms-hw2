import unittest

from src.hash_table import ChainedHashTable


def _bucket_index(key, capacity):
    value = 0
    for byte in key.encode("utf-8"):
        value = (31 * value + byte) % capacity
    return value


def _collision_keys(capacity, count):
    by_bucket = {}
    for number in range(capacity * count * 10):
        key = f"collision-{number}"
        index = _bucket_index(key, capacity)
        keys = by_bucket.setdefault(index, [])
        keys.append(key)
        if len(keys) == count:
            return keys
    raise AssertionError(f"could not find {count} colliding keys")


def _get_buckets(table):
    buckets = table.buckets
    return buckets() if callable(buckets) else buckets


class ChainedHashTableTests(unittest.TestCase):
    def test_default_and_custom_capacity(self):
        default_table = ChainedHashTable()
        custom_table = ChainedHashTable(capacity=7)

        self.assertEqual(len(_get_buckets(default_table)), 97)
        self.assertEqual(len(_get_buckets(custom_table)), 7)

    def test_rejects_non_positive_capacity(self):
        for capacity in (0, -1):
            with self.subTest(capacity=capacity):
                with self.assertRaises(ValueError):
                    ChainedHashTable(capacity=capacity)

    def test_empty_table_lookup_and_delete_raise_key_error(self):
        table = ChainedHashTable(capacity=5)

        self.assertEqual(len(table), 0)
        self.assertFalse(table.contains("missing"))
        self.assertNotIn("missing", table)
        with self.assertRaises(KeyError):
            table.get("missing")
        with self.assertRaises(KeyError):
            table.delete("missing")

    def test_reinserting_a_key_overwrites_its_value(self):
        table = ChainedHashTable(capacity=5)

        table.put("key", "first")
        table.put("key", "second")

        self.assertEqual(table.get("key"), "second")
        self.assertEqual(len(table), 1)
        self.assertTrue(table.contains("key"))
        self.assertIn("key", table)

    def test_colliding_keys_can_be_looked_up_and_deleted_from_chain_middle(self):
        capacity = 7
        keys = _collision_keys(capacity, 3)
        self.assertEqual(
            len({_bucket_index(key, capacity) for key in keys}),
            1,
        )
        table = ChainedHashTable(capacity=capacity)
        for key in keys:
            table.put(key, f"value:{key}")

        self.assertEqual(len(table), 3)
        self.assertEqual(
            table.get(keys[1]),
            f"value:{keys[1]}",
        )
        table.delete(keys[1])

        self.assertEqual(len(table), 2)
        self.assertFalse(table.contains(keys[1]))
        with self.assertRaises(KeyError):
            table.get(keys[1])
        self.assertEqual(table.get(keys[0]), f"value:{keys[0]}")
        self.assertEqual(table.get(keys[2]), f"value:{keys[2]}")

        chain = _get_buckets(table)[_bucket_index(keys[0], capacity)]
        self.assertEqual({pair[0] for pair in chain}, {keys[0], keys[2]})


if __name__ == "__main__":
    unittest.main()
