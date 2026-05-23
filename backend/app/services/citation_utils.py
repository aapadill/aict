from __future__ import annotations

import re
from hashlib import sha256

_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
    }
)


def normalize_for_citation(text: str) -> str:
    normalized = text.translate(_QUOTE_TRANSLATION).lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip(" \t\n\r.,;:!?\"'()[]{}")


def quote_hash(text: str) -> str:
    return sha256(normalize_for_citation(text).encode("utf-8")).hexdigest()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9-]{1,}", normalize_for_citation(text))
