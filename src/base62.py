"""Base62 encoding using digits, uppercase letters, then lowercase letters."""

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def encode(n: int) -> str:
    """Encode a non-negative integer as a base62 string."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be a non-negative integer")
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    if n == 0:
        return "0"

    encoded = []
    while n:
        n, remainder = divmod(n, len(ALPHABET))
        encoded.append(ALPHABET[remainder])
    return "".join(reversed(encoded))


def decode(s: str) -> int:
    """Decode a base62 string into a non-negative integer."""
    if not isinstance(s, str):
        raise TypeError("s must be a string")
    if not s:
        raise ValueError("s must not be empty")

    value = 0
    for character in s:
        digit = ALPHABET.find(character)
        if digit == -1:
            raise ValueError(f"invalid base62 character: {character!r}") from None
        value = value * len(ALPHABET) + digit
    return value
