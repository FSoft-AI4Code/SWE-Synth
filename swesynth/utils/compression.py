"""
JSON friendly compression and decompression functions using base64 and gzip.
"""

import base64
import gzip
import random


def compress(input: str) -> str:
    return base64.b64encode(gzip.compress(input.encode())).decode()


def decompress(input: str) -> str:
    return gzip.decompress(base64.b64decode(input)).decode()


def sample_with_seed(input_set: set, k: int, seed: int = 42) -> set:
    # yes, this is lossy compression :)
    random.seed(seed)  # Set seed for reproducibility
    return set(random.sample(sorted(input_set), k))  # Sample `k` elements from the input_set
