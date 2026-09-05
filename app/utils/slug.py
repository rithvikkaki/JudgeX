"""Slug generation with collision handling."""

from __future__ import annotations

import re
import unicodedata
from typing import Callable

_NON_WORD = re.compile(r"[^a-z0-9]+")


def slugify(value: str, max_length: int = 200) -> str:
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_WORD.sub("-", ascii_only).strip("-")
    return slug[:max_length] or "item"


def unique_slug(value: str, exists: Callable[[str], bool], max_length: int = 200) -> str:
    """``slugify`` plus a ``-2``, ``-3`` … suffix until ``exists`` says no."""
    base = slugify(value, max_length)
    if not exists(base):
        return base

    counter = 2
    while True:
        suffix = f"-{counter}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
        if not exists(candidate):
            return candidate
        counter += 1
