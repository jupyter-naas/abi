"""Text handling shared by the exporter and the search API.

Folding happens twice for one reason: the exporter folds the searchable fields
into ``people.search_text`` so matching is a SQL ``LIKE``, and the API folds the
query the same way so the two meet. Both must use these functions, or a search
for "cedric" stops finding "Cédric".
"""

from __future__ import annotations

import re
import unicodedata

# Words too common to narrow a search, in the languages this directory is most
# likely to hold. Dropping them keeps "head of audit" from scoring on "of".
STOPWORDS = frozenset(
    {"and", "the", "of", "in", "at", "de", "la", "le", "et", "du", "des"}
)
_SPLIT = re.compile(r"[^a-z0-9+]+")


def fold(value: object) -> str:
    """Lowercase and strip accents, so "Cédric" and "cedric" are one word."""
    text = "" if value is None else str(value)
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower()


def words(value: object) -> list[str]:
    """The folded words of a value. '+' survives, so "C++" stays one word."""
    return [word for word in _SPLIT.split(fold(value)) if word]


def query_tokens(query: str) -> list[str]:
    """The words of a query worth matching on, in order, without repeats."""
    seen: list[str] = []
    for word in words(query):
        if word in STOPWORDS or word in seen:
            continue
        seen.append(word)
    return seen


def search_text(field_values: dict[str, list[str]]) -> str:
    """One folded string per person, holding every searchable word once.

    Order and field are lost here on purpose: this column decides *whether*
    someone matches, cheaply, in SQL. Which field matched, and how well, is
    scored afterwards against the fields themselves.
    """
    collected: list[str] = []
    seen: set[str] = set()
    for values in field_values.values():
        for value in values:
            for word in words(value):
                if word not in seen:
                    seen.add(word)
                    collected.append(word)
    return " ".join(collected)


def truncate(text: str, limit: int) -> str:
    """Cut at a word boundary, marking that something was cut."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    boundary = cut.rfind(" ")
    return (cut[:boundary] if boundary > 0 else cut).rstrip() + " …"
