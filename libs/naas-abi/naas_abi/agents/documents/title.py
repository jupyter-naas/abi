"""Name a document after the topic the user asked about.

``create_documents_project`` takes a title from the model, which often arrives as
the raw request ("fais des sections sur les materiaux de construction") or not at
all. The document then shows up as "Untitled document" in the sidebar tree, as
"Untitled Mtq5Mtz0" on the chat card, and as ``untitled-mtq5mtz0`` in the URL.

Derivation is deliberately conservative: a title is only derived when the text
reads like a document request, meaning a document noun followed by a topic connector
("sur", "about", "on", "concernant"). "Change the cover title to X" is an edit
instruction, not a name, so it derives nothing and the document keeps its title.
The topic is kept in the user's own language and capitalisation, so a French
brief stays French and "Saint-Gobain" stays spelled that way.
"""

from __future__ import annotations

import re

MAX_TITLE_WORDS = 8
MAX_TITLE_CHARS = 64

_DECK_NOUN_RE = re.compile(
    r"\b(?:pr[ée]sentations?|documents?|section\s*documents?|sectionshows?|sections?"
    r"|documents?|pitchs?|expos[ée]s?)\b",
    re.IGNORECASE,
)

# A connector is required: it is what separates "make a document" from the topic.
_CONNECTOR_RE = re.compile(
    r"^[\s,:;-]*(?:"
    r"au\s+sujet\s+d[eu']|[àa]\s+propos\s+d[eu']|concernant|regarding|covering"
    r"|about|around|sur|on|pour|for"
    r"|de\s+la|de\s+l['’]|des|du|d['’]|de"
    r")(?=[\s'’])[\s'’]*",
    re.IGNORECASE,
)

_LEADING_ARTICLE_RE = re.compile(
    r"^(?:l['’]|d['’]|(?:les|le|la|des|du|de|un|une|the|a|an|some|my|our)\s+)",
    re.IGNORECASE,
)

# Words that read as an unfinished phrase when a long topic is cut short.
_TRAILING_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "au",
        "aux",
        "avec",
        "by",
        "dans",
        "de",
        "des",
        "du",
        "en",
        "et",
        "for",
        "from",
        "in",
        "la",
        "le",
        "les",
        "of",
        "on",
        "or",
        "ou",
        "par",
        "pour",
        "sur",
        "the",
        "to",
        "un",
        "une",
        "with",
    }
)

_PLACEHOLDER_TITLES = frozenset(
    {
        "document",
        "my document",
        "new document",
        "new document",
        "nouveau document",
        "nouvelle document",
        "document",
        "document title",
        "sans titre",
        "sections",
        "titre de la document",
        "untitled",
        "untitled document",
        "untitled document",
        "untitled sections",
    }
)

_UNTITLED_RE = re.compile(r"^untitled[\s_-]*[a-z0-9]*$", re.IGNORECASE)
_HAS_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u00a0", " ")).strip()


def _fold(text: str) -> str:
    """Lowercase and drop accents so 'Nouvelle document' matches."""
    import unicodedata

    stripped = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in stripped if not unicodedata.combining(ch))


def is_placeholder_document_title(title: str) -> bool:
    """True when a title carries no topic (template filler or auto-generated)."""
    text = _normalize(title)
    if not text:
        return True
    folded = _fold(text).strip(" .:-")
    if folded in _PLACEHOLDER_TITLES:
        return True
    return bool(_UNTITLED_RE.match(folded))


def _cut_at_sentence_end(text: str) -> str:
    return re.split(r"[.!?;\n]", text, maxsplit=1)[0]


def _trim_edges(text: str) -> str:
    return text.strip(" \t,:;·-–—\"'“”«»()[]")


def _limit(text: str) -> str:
    words = text.split()
    words = words[:MAX_TITLE_WORDS]
    while words and len(" ".join(words)) > MAX_TITLE_CHARS:
        words.pop()
    while words and _fold(_trim_edges(words[-1])) in _TRAILING_STOPWORDS:
        words.pop()
    return " ".join(words)


def _capitalize_first(text: str) -> str:
    for i, ch in enumerate(text):
        if ch.isalpha():
            if ch.islower():
                return text[:i] + ch.upper() + text[i + 1 :]
            return text
    return text


def _tidy_topic(topic: str) -> str:
    text = _trim_edges(_cut_at_sentence_end(_normalize(topic)))
    text = _LEADING_ARTICLE_RE.sub("", text, count=1)
    text = _limit(_trim_edges(text))
    if not _HAS_LETTER_RE.search(text):
        return ""
    return _capitalize_first(text)


def derive_document_title(brief: str) -> str:
    """Topic of a document request, or "" when the text is not a document request."""
    text = _normalize(brief)
    if not text or is_placeholder_document_title(text):
        return ""
    for noun in _DECK_NOUN_RE.finditer(text):
        connector = _CONNECTOR_RE.match(text[noun.end() :])
        if not connector:
            continue
        topic = _tidy_topic(text[noun.end() + connector.end() :])
        if topic:
            return topic
    return ""


def _looks_like_a_request(title: str) -> bool:
    """A title long enough to be a sentence is really the user's brief."""
    return len(_normalize(title).split()) > MAX_TITLE_WORDS


def resolve_document_title(title: str, brief: str = "") -> str:
    """Display title for a document, given the model's title and the turn's brief.

    Returns "" when neither carries a topic, leaving the caller to decide
    whether that is an error (create) or a reason to keep the current name.
    """
    candidate = _normalize(title)
    if candidate and not is_placeholder_document_title(candidate):
        derived = derive_document_title(candidate)
        if derived:
            return derived
        if not _looks_like_a_request(candidate):
            return _tidy_topic(candidate) or candidate
    return derive_document_title(brief)
