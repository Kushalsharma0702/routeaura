import re
import unicodedata
from collections.abc import Callable


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
    return slug[:80] or "item"


def unique_slug(base: str, exists: Callable[[str], bool]) -> str:
    slug = slugify(base)
    if not exists(slug):
        return slug
    n = 2
    while exists(f"{slug}-{n}"):
        n += 1
    return f"{slug}-{n}"
