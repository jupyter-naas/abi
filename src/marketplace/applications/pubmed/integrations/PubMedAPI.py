
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

import hashlib

import re

import requests

from abi.integration import Integration, IntegrationConfiguration
from abi.integration.integration import IntegrationConnectionError
from abi import logger
from ratelimit import limits
from abi.services.cache.CacheFactory import CacheFactory
from abi.services.cache.CachePort import DataType
from abi.services.cache.CacheService import CacheService
from src.marketplace.applications.pubmed.ontologies.PubMed import (
    PubMedPaperSummary,
    Journal,
    JournalIssue,
)

cache: CacheService = CacheFactory.CacheFS_find_storage(subpath="pubmed")

PUB_MED_RATE_LIMIT_NUMBER = 3
PUB_MED_RATE_LIMIT_PERIOD = 1

def _clean_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_publication_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None

    date_formats = [
        "%Y %b %d",
        "%Y %B %d",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
        "%Y %b",
        "%Y %B",
        "%Y",
    ]

    for fmt in date_formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    return None


def _parse_sort_pubdate(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None

    datetime_formats = [
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y",
    ]

    for fmt in datetime_formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


@dataclass
class PubMedAPIConfiguration(IntegrationConfiguration):
    """Configuration for the PubMed API integration.

    Attributes:
        base_url: Base URL for NCBI E-utilities.
        api_key: Optional NCBI API key to raise rate limits.
        retmax: Default maximum number of records for simple searches.
        timeout: HTTP timeout in seconds.
        page_size: Page size for paginated ESearch requests.
    """
    base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    api_key: Optional[str] = None
    retmax: int = 20
    timeout: int = 30
    page_size: int = 200


class PubMedIntegration(Integration):
    """PubMed integration providing search and fetch helpers over E-utilities."""
    __configuration: PubMedAPIConfiguration

    def __init__(self, configuration: PubMedAPIConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    @limits(calls=PUB_MED_RATE_LIMIT_NUMBER, period=PUB_MED_RATE_LIMIT_PERIOD)
    def _make_request(self, endpoint: str, params: Dict[str, Optional[str]], *, expect_json: bool = True, method: str = "GET", data: Optional[Dict] = None):
        """Low-level HTTP requester to E-utilities.

        Args:
            endpoint: E-utilities endpoint path (e.g., "/esearch.fcgi").
            params: Querystring parameters, None values are dropped.
            expect_json: If True, parse and return JSON; otherwise return text.
            method: "GET" or "POST".
            data: Optional POST form data.

        Returns:
            Parsed JSON (dict) if expect_json, otherwise response text.

        Raises:
            IntegrationConnectionError: On HTTP or parsing errors.
        """
        url = f"{self.__configuration.base_url}{endpoint}"
        query_params = {k: v for k, v in params.items() if v is not None}
        if self.__configuration.api_key:
            query_params.setdefault("api_key", self.__configuration.api_key)
        query_params.setdefault("db", "pubmed")

        try:
            if method.upper() == "POST":
                response = requests.post(url, params=query_params, data=data, timeout=self.__configuration.timeout)
            else:
                response = requests.get(url, params=query_params, timeout=self.__configuration.timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error(f"PubMed API request failed: {exc}")
            raise IntegrationConnectionError(f"PubMed API request failed: {exc}") from exc

        if expect_json:
            try:
                return response.json()
            except ValueError as exc:
                logger.error(f"PubMed API returned invalid JSON response: {response.text}")
                raise IntegrationConnectionError("PubMed API returned invalid JSON response") from exc
        return response.text

    def _extract_article_id(self, article_ids: List[Dict[str, str]], idtype: str) -> Optional[str]:
        """Extract a specific identifier value from PubMed ESummary "articleids".

        Args:
            article_ids: List of id dicts from ESummary.
            idtype: Target id type (e.g., "doi", "pmcid", "pmc", "url").

        Returns:
            The identifier string if found, else None.
        """
        for article_id in article_ids:
            if article_id.get("idtype") == idtype and article_id.get("value"):
                return article_id["value"]
        return None

    def _extract_pmcid(self, article_ids: List[Dict[str, str]]) -> Optional[str]:
        """Extract normalized PMCID from ESummary ids, handling common variants."""
        pmcid = self._extract_article_id(article_ids, "pmcid")
        if pmcid:
            match = re.search(r"(PMC\d+)", pmcid, flags=re.IGNORECASE)
            if match:
                return match.group(1)

        pmc = self._extract_article_id(article_ids, "pmc")
        if pmc:
            return pmc

        return None

    def _build_summary(self, pmid: str, doc: Optional[Dict]) -> PubMedPaperSummary:
        """Build a PubMedPaperSummary from a single ESummary document entry."""
        article_ids: List[Dict] = doc.get("articleids", []) if doc else []
        doi = self._extract_article_id(article_ids, "doi")
        pmcid = self._extract_pmcid(article_ids)
        url = self._extract_article_id(article_ids, "url") if article_ids else None

        summary = PubMedPaperSummary(
            _uri=f"{PubMedPaperSummary._class_uri}/instances/{pmid}",
            pubmedIdentifier=pmid,
            title=_clean_optional_str(doc.get("title") if doc else None),
            journalTitleLiteral=_clean_optional_str((doc.get("fulljournalname") or doc.get("source")) if doc else None),
            publicationDate=_parse_publication_date(doc.get("pubdate") if doc else None),
            sortPublicationDate=_parse_sort_pubdate(doc.get("sortpubdate") if doc else None),
            authorLiteral="; ".join(
                author.get("name")
                for author in (doc.get("authors", []) if doc else [])
                if author.get("name")
            ) or None,
            doi=_clean_optional_str(doi),
            pmcid=_clean_optional_str(pmcid),
            url=_clean_optional_str(url or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"),
            downloadUrl=_clean_optional_str(
                f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf" if pmcid else None
            ),
            pages=_clean_optional_str(doc.get("pages") if doc else None)
        )

        issn_value = _clean_optional_str((doc.get("issn") or doc.get("essn")) if doc else None)
        volume_value = _clean_optional_str(doc.get("volume") if doc else None)
        issue_value = _clean_optional_str(doc.get("issue") if doc else None)

        journal = Journal(issn=issn_value) if issn_value else None
        if journal:
            summary.aboutJournal = journal

        if volume_value or issue_value:
            journal_issue = JournalIssue(
                volume=volume_value,
                issueLabel=issue_value,
            )
            if journal:
                journal_issue.issueOf = journal
            summary.aboutJournalIssue = journal_issue

        return summary

    
    def _summaries(self, id_list: List[str]) -> List[PubMedPaperSummary]:
        """
        Retrieve PubMedPaperSummary objects for a list of PubMed IDs, using a caching mechanism.

        This method supports batch retrieval of summaries for multiple PubMed IDs at once.
        For each ID, it first checks the cache for an existing summary. If a summary is not found
        in the cache, it fetches the summary from the PubMed API, stores it in the cache, and then
        returns all summaries in the order of the input ID list.

        Args:
            id_list (List[str]): List of PubMed IDs to retrieve summaries for.

        Returns:
            List[PubMedPaperSummary]: List of PubMedPaperSummary objects, in the same order as id_list.
        """
        if not id_list:
            return []
        new_ids = [_id for _id in id_list if not cache.exists(f"pubmed_paper_summary_{_id}")]

        # Process new IDs in chunks of 200
        chunk_size = 200
        all_summaries: List[PubMedPaperSummary] = []
        
        for i in range(0, len(new_ids), chunk_size):
            chunk_ids = new_ids[i:i + chunk_size]
            
            # Grabbing the new summaries for this chunk.
            summary_data = self._make_request(
                "/esummary.fcgi",
                {},
                expect_json=True,
                method="POST",
                data={
                    "id": ",".join(chunk_ids),
                    "retmode": "json",
                },
            )

            result = summary_data.get("result", {})
            
            # Computing new summaries for this chunk.
            chunk_summaries: List[PubMedPaperSummary] = []
            for pmid in chunk_ids:
                doc = result.get(pmid)
                if not doc:
                    continue

                chunk_summaries.append(self._build_summary(pmid, doc))

            # Caching the new summaries for this chunk.
            for _id in chunk_ids:
                try:
                    summary_index = chunk_ids.index(_id)
                    if summary_index < len(chunk_summaries):
                        cache.set_pickle(f"pubmed_paper_summary_{_id}", chunk_summaries[summary_index])
                except ValueError:
                    # ID not found in chunk_summaries, skip caching
                    continue
            
            all_summaries.extend(chunk_summaries)

        # Grabbing all summaries to respect the original order.
        summaries = [cache.get(f"pubmed_paper_summary_{_id}") for _id in id_list]
        
        return summaries


    def _date_to_str(self, d: date) -> str:
        """Convert a date to E-utilities accepted string (YYYY/MM/DD)."""
        return d.strftime("%Y/%m/%d")

    def _count_for_range(
        self,
        query: str,
        *,
        mindate: Optional[str],
        maxdate: Optional[str],
        sort: Optional[str] = None,
    ) -> int:
        """Return the total ESearch count for a query constrained to a date range."""
        params: Dict[str, Optional[str]] = {
            "term": query,
            "retmode": "json",
            "retmax": "0",
            "retstart": "0",
            "sort": sort or "relevance",
            "mindate": mindate,
            "maxdate": maxdate,
            "datetype": "pdat",
        }
        data = self._make_request("/esearch.fcgi", params, expect_json=True)
        esearch_result = data.get("esearchresult", {})
        try:
            return int(esearch_result.get("count", 0))
        except (TypeError, ValueError):
            return 0

    @cache(lambda query, mindate, maxdate, sort, page_size, max_records_cap: hashlib.sha1(
        f"pubmed_ids_{query}_{mindate}_{maxdate}_{sort}_{page_size}_{max_records_cap}".encode("utf-8")
    ).hexdigest(), cache_type=DataType.PICKLE)
    def _fetch_ids_for_range(
            self,
            query: str,
            *,
            mindate: Optional[str],
            maxdate: Optional[str],
            sort: Optional[str] = None,
            page_size: int = 100,
            max_records_cap: int = 9999,
        ) -> List[str]:
            """Fetch all PubMed IDs for a given date range up to a cap, paging as needed."""
            if page_size <= 0:
                page_size = 100
            collected_ids: List[str] = []
            retstart = 0
            total_available: Optional[int] = None

            while True:
                if len(collected_ids) >= max_records_cap:
                    break
                current_batch_size = min(page_size, max_records_cap - len(collected_ids))
                params: Dict[str, Optional[str]] = {
                    "term": query,
                    "retmode": "json",
                    "retmax": str(current_batch_size),
                    "retstart": str(retstart),
                    "sort": sort or "relevance",
                    "mindate": mindate,
                    "maxdate": maxdate,
                    "datetype": "pdat",
                }
                data = self._make_request("/esearch.fcgi", params, expect_json=True)
                esearch_result = data.get("esearchresult", {})

                # API error check
                if "ERROR" in esearch_result:
                    error_msg = esearch_result["ERROR"]
                    logger.error(f"PubMed API error: {error_msg}")
                    raise IntegrationConnectionError(f"PubMed API error: {error_msg}")

                batch_ids = esearch_result.get("idlist", [])
                if not batch_ids:
                    break
                collected_ids.extend(batch_ids)
                retstart += len(batch_ids)

                try:
                    total_available = int(esearch_result.get("count", 0))
                except (TypeError, ValueError):
                    total_available = None

                if total_available is not None and retstart >= total_available:
                    break

            return collected_ids

    def search_date_range(
        self,
        query: str,
        *,
        start_date: str,
        end_date: Optional[str] = None,
        sort: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[PubMedPaperSummary]:
        """Search PubMed over a date range, adaptively splitting windows to avoid the 9,999 cap.

        Dates should be in one of the formats accepted by PubMed (e.g., YYYY/MM/DD or YYYY-MM-DD). If end_date is None,
        it defaults to today's date.

        Args:
            query: PubMed query string.
            start_date: Inclusive start date.
            end_date: Inclusive end date (defaults to today if None).
            sort: Optional sort method (e.g., "relevance").
            max_results: Optional cap on the total number of papers to return across the whole range.
        """
        # Parse input dates ensuring non-optional date types
        start_dt_opt = _parse_publication_date(start_date) or _parse_publication_date(start_date.replace("-", " "))
        if start_dt_opt is None:
            raise IntegrationConnectionError("Invalid start_date format.")
        start_dt: date = start_dt_opt

        if end_date is None:
            end_dt: date = date.today()
        else:
            end_dt_opt = _parse_publication_date(end_date) or _parse_publication_date(end_date.replace("-", " "))
            if end_dt_opt is None:
                raise IntegrationConnectionError("Invalid end_date format.")
            end_dt = end_dt_opt
        if start_dt > end_dt:
            start_dt, end_dt = end_dt, start_dt

        MAX_PUBMED_RECORDS = 9999
        page_size = self.__configuration.page_size or 100
        if page_size <= 0:
            page_size = 100

        # Worklist of (start, end) date windows to process, non-overlapping and inclusive
        windows: List[tuple[date, date]] = [(start_dt, end_dt)]
        all_ids: List[str] = []

        while windows:
            if max_results is not None and len(all_ids) >= max_results:
                break
            w_start, w_end = windows.pop()
            mindate_str = self._date_to_str(w_start)
            maxdate_str = self._date_to_str(w_end)

            count = self._count_for_range(query, mindate=mindate_str, maxdate=maxdate_str, sort=sort)
            if count == 0:
                continue
            if count <= MAX_PUBMED_RECORDS:
                # Fetch all IDs for this window
                per_window_cap = MAX_PUBMED_RECORDS
                if max_results is not None:
                    remaining = max_results - len(all_ids)
                    if remaining <= 0:
                        break
                    per_window_cap = min(per_window_cap, remaining)
                ids = self._fetch_ids_for_range(
                    query,
                    mindate=mindate_str,
                    maxdate=maxdate_str,
                    sort=sort,
                    page_size=page_size,
                    max_records_cap=per_window_cap,
                )
                all_ids.extend(ids)
                continue

            # Too many results: split window into two halves by midpoint date
            if w_start == w_end:
                # Single day still over the cap (very rare) – log and skip to avoid infinite loop
                logger.warning(
                    f"Single-day window {mindate_str} has {count} results exceeding API cap; skipping to avoid loop."
                )
                continue

            total_days = (w_end - w_start).days
            mid = w_start + timedelta(days=total_days // 2)
            left_end = mid
            right_start = mid + timedelta(days=1)
            if right_start > w_end:
                right_start = w_end

            # Process right then left (stack behavior) to keep chronological-ish accumulation
            windows.append((w_start, left_end))
            windows.append((right_start, w_end))

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_ids: List[str] = []
        for _id in all_ids:
            if _id not in seen:
                seen.add(_id)
                unique_ids.append(_id)

        if max_results is not None:
            unique_ids = unique_ids[:max_results]
        return self._summaries(unique_ids)
