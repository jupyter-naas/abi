"""
RSS news adapter — BBC / Al Jazeera / Reuters.

Relevance filter: title must contain a REGION or BREAKING keyword.
Severity classification: BREAKING > ALERT > UPDATE.
Output: up to 40 items sorted newest-first.
"""

import asyncio
import re
import time

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import NewsItem, SeverityLevel
from services.news.NewsPort import INewsAdapter

_BREAKING_KEYWORDS = [
    "retaliation", "retaliates", "strike", "strikes", "struck", "attack", "attacked",
    "bombing", "bombed", "missile", "missiles", "explosion", "explosions", "imminent",
    "intercept", "intercepted", "drone attack", "airstrike", "air strike", "kills", "killed",
]
_ALERT_KEYWORDS = [
    "military", "threat", "escalation", "escalates", "nuclear", "war", "troops", "forces",
    "deploy", "deployed", "warship", "carrier", "sanctions", "ceasefire", "hostilities",
    "hezbollah", "hamas", "irgc", "centcom", "iron dome", "ballistic",
]
_REGION_KEYWORDS = [
    "iran", "iranian", "israel", "israeli", "tehran", "tel aviv", "jerusalem",
    "gaza", "lebanon", "beirut", "syria", "iraq", "persian gulf", "strait of hormuz",
    "middle east", "biden", "netanyahu", "khamenei", "pentagon",
]

_FEEDS = [
    ("http://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "BBC"),
    ("https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera"),
    ("https://feeds.reuters.com/reuters/topNews", "Reuters"),
]

_CDATA_RE = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.DOTALL)
_TAGS_RE  = re.compile(r"<[^>]+>")
_ITEM_RE  = re.compile(r"<item>(.*?)</item>", re.DOTALL)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
_LINK_RE  = re.compile(r"<link>(.*?)</link>|<guid[^>]*>(.*?)</guid>", re.DOTALL)
_DATE_RE  = re.compile(r"<pubDate>(.*?)</pubDate>", re.DOTALL)


def _extract_cdata(text: str) -> str:
    m = _CDATA_RE.search(text)
    return m.group(1).strip() if m else _TAGS_RE.sub("", text).strip()


def _detect_severity(title: str) -> SeverityLevel:
    lower = title.lower()
    if any(k in lower for k in _BREAKING_KEYWORDS):
        return "breaking"
    if any(k in lower for k in _ALERT_KEYWORDS):
        return "alert"
    return "update"


def _is_relevant(title: str) -> bool:
    lower = title.lower()
    return any(k in lower for k in _REGION_KEYWORDS) or any(k in lower for k in _BREAKING_KEYWORDS)


def _parse_rss(xml: str, source: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    for idx, m in enumerate(_ITEM_RE.finditer(xml)):
        block = m.group(1)
        raw_title = (_TITLE_RE.search(block) or _TAGS_RE).group(1) if _TITLE_RE.search(block) else ""  # type: ignore[union-attr]
        title = _extract_cdata(raw_title) if raw_title else ""
        if not title or not _is_relevant(title):
            continue

        link_m = _LINK_RE.search(block)
        raw_link = (link_m.group(1) or link_m.group(2) or "") if link_m else ""
        link = _extract_cdata(raw_link)

        date_m = _DATE_RE.search(block)
        if date_m:
            try:
                from email.utils import parsedate_to_datetime
                pub_date_ms = int(parsedate_to_datetime(date_m.group(1)).timestamp() * 1000)
            except Exception:
                pub_date_ms = int(time.time() * 1000)
        else:
            pub_date_ms = int(time.time() * 1000)

        items.append(NewsItem(
            id=f"{source}-{pub_date_ms}-{idx}",
            title=title,
            source=source,
            url=link,
            pubDate=pub_date_ms,
            severity=_detect_severity(title),
        ))
    return items


class RSSNewsAdapter(INewsAdapter):
    def __init__(self) -> None:
        self._cache: TTLCache[list[NewsItem]] = TTLCache(ttl_seconds=180)

    async def fetch(self) -> list[NewsItem]:
        return await self._cache.get_or_fetch("news", self._fetch)

    async def _fetch(self) -> list[NewsItem]:
        tasks = [self._fetch_feed(url, src) for url, src in _FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        merged = [item for feed in results for item in feed]
        merged.sort(key=lambda x: x.pub_date, reverse=True)
        return merged[:40]

    async def _fetch_feed(self, url: str, source: str) -> list[NewsItem]:
        try:
            resp = await get_client().get(
                url, headers={"User-Agent": "WSR-Intel/1.0"}, timeout=8,
            )
            if not resp.is_success:
                return []
            return _parse_rss(resp.text, source)
        except Exception:
            return []
