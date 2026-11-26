"""A string-keyed hash table using linear probing."""

from typing import Any


class _Tombstone:
    pass


_TOMBSTONE = _Tombstone()


class LinearProbingHashTable:
    def __init__(self, capacity: int = 97) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be greater than zero")

        self.capacity = capacity
        self.buckets: list[tuple[str, Any] | _Tombstone | None] = [
            None for _ in range(capacity)
        ]
        self._size = 0

    def _bucket_index(self, key: str) -> int:
        value = 0
        for byte in key.encode("utf-8"):
            value = (31 * value + byte) % self.capacity
        return value

    def put(self, key: str, value: Any) -> None:
        index = self._bucket_index(key)
        first_tombstone = None

        for _ in range(self.capacity):
            entry = self.buckets[index]
            if entry is None:
                target = first_tombstone if first_tombstone is not None else index
                self.buckets[target] = (key, value)
                self._size += 1
                return
            if entry is _TOMBSTONE:
                if first_tombstone is None:
                    first_tombstone = index
            elif entry[0] == key:
                self.buckets[index] = (key, value)
                return
            index = (index + 1) % self.capacity

        if first_tombstone is not None:
            self.buckets[first_tombstone] = (key, value)
            self._size += 1
            return
        raise OverflowError("hash table is full")

    def _find_index(self, key: str) -> int | None:
        index = self._bucket_index(key)
        for _ in range(self.capacity):
            entry = self.buckets[index]
            if entry is None:
                return None
            if entry is not _TOMBSTONE and entry[0] == key:
                return index
            index = (index + 1) % self.capacity
        return None

    def get(self, key: str) -> Any:
        index = self._find_index(key)
        if index is None:
            raise KeyError(key)
        entry = self.buckets[index]
        if entry is None or entry is _TOMBSTONE:
            raise KeyError(key)
        return entry[1]

    def contains(self, key: str) -> bool:
        return self._find_index(key) is not None

    def __contains__(self, key: str) -> bool:
        return self.contains(key)

    def delete(self, key: str) -> None:
        index = self._find_index(key)
        if index is None:
            raise KeyError(key)
        self.buckets[index] = _TOMBSTONE
        self._size -= 1

    def __len__(self) -> int:
        return self._size
