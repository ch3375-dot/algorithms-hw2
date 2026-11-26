import unittest

from src.linear_probing import LinearProbingHashTable


def _keys_with_home_slot(capacity, home_slot, count):
    keys = []
    for number in range(capacity * count * 20):
        key = f"wraparound-{number}"
        value = 0
        for byte in key.encode("utf-8"):
            value = (31 * value + byte) % capacity
        if value == home_slot:
            keys.append(key)
            if len(keys) == count:
                return keys
    raise AssertionError(f"could not find {count} keys for slot {home_slot}")


class LinearProbingHashTableTests(unittest.TestCase):
    def test_probe_wraps_from_last_bucket_to_bucket_zero(self):
        capacity = 5
        keys = _keys_with_home_slot(capacity, capacity - 1, 3)
        table = LinearProbingHashTable(capacity=capacity)
        for key in keys:
            table.put(key, key)

        self.assertEqual(table.buckets[capacity - 1], (keys[0], keys[0]))
        self.assertEqual(table.buckets[0], (keys[1], keys[1]))
        self.assertEqual(table.buckets[1], (keys[2], keys[2]))
        for key in keys:
            self.assertEqual(table.get(key), key)

    def test_full_table_rejects_new_key_but_allows_existing_key_update(self):
        table = LinearProbingHashTable(capacity=2)
        table.put("first", 1)
        table.put("second", 2)

        with self.assertRaises(OverflowError):
            table.put("new", 3)

        table.put("first", 10)
        self.assertEqual(table.get("first"), 10)
        self.assertEqual(table.get("second"), 2)
        self.assertEqual(len(table), 2)

    def test_lookup_continues_through_deleted_slot(self):
        capacity = 5
        keys = _keys_with_home_slot(capacity, 2, 3)
        table = LinearProbingHashTable(capacity=capacity)
        for key in keys:
            table.put(key, f"value:{key}")

        table.delete(keys[1])

        self.assertFalse(table.contains(keys[1]))
        self.assertEqual(table.get(keys[0]), f"value:{keys[0]}")
        self.assertEqual(table.get(keys[2]), f"value:{keys[2]}")
        table.put("replacement", "replacement value")
        self.assertEqual(table.get("replacement"), "replacement value")
        self.assertEqual(len(table), 3)


if __name__ == "__main__":
    unittest.main()
