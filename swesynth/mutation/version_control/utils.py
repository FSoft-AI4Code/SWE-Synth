import hashlib


def hash_to_n_chars(input_string: str, n: int = 8) -> str:
    """
    Hashes the input string using SHA-256 and returns the first n characters of the hash.

    Args:
        input_string (str): The input string to hash.
        n (int, optional): The number of characters to return. Defaults to 8.

    Returns:
        str: The first n characters of the SHA-256 hash of the input string.

    Example:
        >>> hash_to_n_chars("Hello, World", 8)
        03675ac5
    """
    # Use a hash function (e.g., SHA-256) to generate a hash from the input string
    hash_object = hashlib.sha256(input_string.encode())

    # Convert the hash to a hexadecimal string
    hex_dig = hash_object.hexdigest()

    # Return the first 8 characters of the hash
    return hex_dig[:n]
