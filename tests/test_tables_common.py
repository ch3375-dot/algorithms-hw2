import unittest

from src.hash_table import ChainedHashTable
from src.linear_probing import LinearProbingHashTable


def _bucket_index(key, capacity):
    value = 0
    for byte in key.encode("utf-8"):
        value = (31 * value + byte) % capacity
    return value


def _colliding_keys(capacity, count):
    keys = []
    target_index = None
    for number in range(capacity * count * 20):
        key = f"shared-home-{number}"
        index = _bucket_index(key, capacity)
        if target_index is None:
            target_index = index
        if index == target_index:
            keys.append(key)
            if len(keys) == count:
                return keys
    raise AssertionError(f"could not find {count} keys with the same home slot")


class TableBehaviorMixin:
    table_type = None

    def test_default_and_custom_capacity(self):
        default_table = self.table_type()
        custom_table = self.table_type(capacity=7)

        self.assertEqual(len(default_table.buckets), 97)
        self.assertEqual(len(custom_table.buckets), 7)

    def test_non_positive_capacity_is_rejected(self):
        for capacity in (0, -1):
            with self.subTest(capacity=capacity):
                with self.assertRaises(ValueError):
                    self.table_type(capacity=capacity)

    def test_empty_lookup_and_delete_raise_key_error(self):
        table = self.table_type(capacity=7)

        self.assertEqual(len(table), 0)
        self.assertFalse(table.contains("absent"))
        self.assertNotIn("absent", table)
        with self.assertRaises(KeyError):
            table.get("absent")
        with self.assertRaises(KeyError):
            table.delete("absent")

    def test_put_overwrites_existing_value_without_changing_size(self):
        table = self.table_type(capacity=7)

        table.put("key", "first")
        table.put("key", "updated")

        self.assertEqual(table.get("key"), "updated")
        self.assertTrue(table.contains("key"))
        self.assertIn("key", table)
        self.assertEqual(len(table), 1)

    def test_collisions_support_lookup_and_deletion_without_losing_other_keys(self):
        keys = _colliding_keys(capacity=7, count=3)
        table = self.table_type(capacity=7)
        for key in keys:
            table.put(key, f"value:{key}")

        self.assertEqual(len(table), 3)
        for key in keys:
            self.assertEqual(table.get(key), f"value:{key}")

        table.delete(keys[1])

        self.assertEqual(len(table), 2)
        self.assertFalse(table.contains(keys[1]))
        with self.assertRaises(KeyError):
            table.get(keys[1])
        self.assertEqual(table.get(keys[0]), f"value:{keys[0]}")
        self.assertEqual(table.get(keys[2]), f"value:{keys[2]}")


class ChainedHashTableCommonTests(TableBehaviorMixin, unittest.TestCase):
    table_type = ChainedHashTable


class LinearProbingHashTableCommonTests(TableBehaviorMixin, unittest.TestCase):
    table_type = LinearProbingHashTable


if __name__ == "__main__":
    unittest.main()
