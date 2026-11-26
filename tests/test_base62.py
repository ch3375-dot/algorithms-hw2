import unittest

from src.base62 import decode, encode


class Base62Tests(unittest.TestCase):
    def test_encode_zero_and_alphabet_boundaries(self):
        self.assertEqual(encode(0), "0")
        self.assertEqual(encode(9), "9")
        self.assertEqual(encode(10), "A")
        self.assertEqual(encode(35), "Z")
        self.assertEqual(encode(36), "a")
        self.assertEqual(encode(61), "z")
        self.assertEqual(encode(62), "10")

    def test_decode_alphabet_boundaries(self):
        self.assertEqual(decode("0"), 0)
        self.assertEqual(decode("9"), 9)
        self.assertEqual(decode("A"), 10)
        self.assertEqual(decode("Z"), 35)
        self.assertEqual(decode("a"), 36)
        self.assertEqual(decode("z"), 61)
        self.assertEqual(decode("10"), 62)

    def test_round_trip_large_integer(self):
        value = 2**128 + 987654321
        self.assertEqual(decode(encode(value)), value)

    def test_decode_accepts_leading_zeroes(self):
        self.assertEqual(decode("00"), 0)
        self.assertEqual(decode("00010"), 62)

    def test_encode_rejects_negative_and_non_integer_values(self):
        with self.assertRaises(ValueError):
            encode(-1)
        with self.assertRaises(TypeError):
            encode(1.5)
        with self.assertRaises(TypeError):
            encode(True)

    def test_decode_rejects_empty_or_invalid_values(self):
        with self.assertRaises(ValueError):
            decode("")
        with self.assertRaises(ValueError):
            decode("a!")
        with self.assertRaises(TypeError):
            decode(62)


if __name__ == "__main__":
    unittest.main()
