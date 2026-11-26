"""A string-keyed hash table using separate chaining."""

from typing import Any


class ChainedHashTable:
    def __init__(self, capacity: int = 97) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be greater than zero")

        self.capacity = capacity
        self.buckets: list[list[tuple[str, Any]]] = [
            [] for _ in range(capacity)
        ]
        self._size = 0

    def _bucket_index(self, key: str) -> int:
        value = 0
        for byte in key.encode("utf-8"):
            value = (31 * value + byte) % self.capacity
        return value

    @staticmethod
    def _pair_index(bucket: list[tuple[str, Any]], key: str) -> int | None:
        for index, (stored_key, _) in enumerate(bucket):
            if stored_key == key:
                return index
        return None

    def put(self, key: str, value: Any) -> None:
        bucket = self.buckets[self._bucket_index(key)]
        pair_index = self._pair_index(bucket, key)
        if pair_index is None:
            bucket.append((key, value))
            self._size += 1
        else:
            bucket[pair_index] = (key, value)

    def get(self, key: str) -> Any:
        bucket = self.buckets[self._bucket_index(key)]
        pair_index = self._pair_index(bucket, key)
        if pair_index is None:
            raise KeyError(key)
        return bucket[pair_index][1]

    def contains(self, key: str) -> bool:
        bucket = self.buckets[self._bucket_index(key)]
        return self._pair_index(bucket, key) is not None

    def __contains__(self, key: str) -> bool:
        return self.contains(key)

    def delete(self, key: str) -> None:
        bucket = self.buckets[self._bucket_index(key)]
        pair_index = self._pair_index(bucket, key)
        if pair_index is None:
            raise KeyError(key)
        del bucket[pair_index]
        self._size -= 1

    def __len__(self) -> int:
        return self._size
