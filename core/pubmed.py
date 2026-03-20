"""PubMed/NCBI E-utilities API client.

Provides functions to search PubMed, fetch article metadata, find related
articles, and perform combined search-and-fetch operations. Uses the NCBI
E-utilities REST API (no API key required; an optional key raises rate limits
from 3 to 10 requests per second).

Base URL: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

import httpx

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
TIMEOUT = 30


def search(
    query: str,
    max_results: int = 10,
    sort: str = "relevance",
) -> list[str]:
    """Search PubMed and return a list of PMID strings.

    Args:
        query: PubMed search query (supports full PubMed query syntax).
        max_results: Maximum number of results to return.
        sort: Sort order -- "relevance" or "date".

    Returns:
        List of PMID strings matching the query.

    Raises:
        RuntimeError: If the search request fails or returns an error.
    """
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": sort,
    }

    try:
        response = httpx.get(
            f"{BASE_URL}esearch.fcgi",
            params=params,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"PubMed search request failed with status {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"PubMed search request failed: {exc}"
        ) from exc

    data = response.json()

    esearch_result = data.get("esearchresult")
    if esearch_result is None:
        raise RuntimeError(
            "Unexpected response from PubMed esearch: missing 'esearchresult' key"
        )

    if "ERROR" in esearch_result:
        raise RuntimeError(
            f"PubMed search returned an error: {esearch_result['ERROR']}"
        )

    return esearch_result.get("idlist", [])


def fetch_articles(pmids: list[str]) -> list[dict]:
    """Fetch article metadata for the given PMIDs.

    Args:
        pmids: List of PubMed ID strings.

    Returns:
        List of dicts, each containing: pmid, title, abstract, authors,
        journal, year, doi, and url.

    Raises:
        RuntimeError: If the fetch request fails.
    """
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "xml",
        "retmode": "xml",
    }

    try:
        response = httpx.get(
            f"{BASE_URL}efetch.fcgi",
            params=params,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"PubMed fetch request failed with status {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"PubMed fetch request failed: {exc}"
        ) from exc

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise RuntimeError(
            f"Failed to parse PubMed XML response: {exc}"
        ) from exc

    articles: list[dict] = []
    for article_elem in root.findall(".//PubmedArticle"):
        articles.append(_parse_article(article_elem))

    return articles


def search_and_fetch(
    query: str,
    max_results: int = 5,
    sort: str = "relevance",
) -> list[dict]:
    """Search PubMed and fetch article metadata in one call.

    Convenience wrapper that combines :func:`search` and
    :func:`fetch_articles`.

    Args:
        query: PubMed search query.
        max_results: Maximum number of articles to return.
        sort: Sort order -- "relevance" or "date".

    Returns:
        List of article dicts (same structure as :func:`fetch_articles`).
    """
    pmids = search(query, max_results=max_results, sort=sort)
    if not pmids:
        return []
    return fetch_articles(pmids)


def get_related(pmid: str, max_results: int = 5) -> list[str]:
    """Find PMIDs of articles related to the given PMID.

    Args:
        pmid: A PubMed ID string.
        max_results: Maximum number of related PMIDs to return.

    Returns:
        List of related PMID strings.

    Raises:
        RuntimeError: If the elink request fails or returns unexpected data.
    """
    params = {
        "dbfrom": "pubmed",
        "db": "pubmed",
        "id": pmid,
        "linkname": "pubmed_pubmed",
        "retmode": "json",
    }

    try:
        response = httpx.get(
            f"{BASE_URL}elink.fcgi",
            params=params,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"PubMed elink request failed with status {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"PubMed elink request failed: {exc}"
        ) from exc

    data = response.json()

    linksets = data.get("linksets", [])
    if not linksets:
        return []

    linkset = linksets[0]
    linksetdbs = linkset.get("linksetdbs", [])
    if not linksetdbs:
        return []

    links = linksetdbs[0].get("links", [])
    return [str(link_id) for link_id in links[:max_results]]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _text(element: Optional[ET.Element]) -> str:
    """Return the text content of an XML element, or empty string if None."""
    if element is None:
        return ""
    # itertext() collects text from the element and all children, which
    # handles inline markup like <i>, <b>, <sup> inside titles/abstracts.
    return "".join(element.itertext()).strip()


def _parse_article(article_elem: ET.Element) -> dict:
    """Parse a single <PubmedArticle> element into a dict."""
    medline = article_elem.find("MedlineCitation")
    article = medline.find("Article") if medline is not None else None

    # PMID
    pmid_elem = medline.find("PMID") if medline is not None else None
    pmid = _text(pmid_elem)

    # Title
    title_elem = article.find("ArticleTitle") if article is not None else None
    title = _text(title_elem)

    # Abstract -- may have multiple <AbstractText> children with Label attrs
    abstract = ""
    if article is not None:
        abstract_elem = article.find("Abstract")
        if abstract_elem is not None:
            parts: list[str] = []
            for abs_text in abstract_elem.findall("AbstractText"):
                label = abs_text.get("Label")
                text = _text(abs_text)
                if label:
                    parts.append(f"{label}: {text}")
                else:
                    parts.append(text)
            abstract = "\n".join(parts)

    # Authors
    authors: list[str] = []
    if article is not None:
        author_list = article.find("AuthorList")
        if author_list is not None:
            for author in author_list.findall("Author"):
                last = _text(author.find("LastName"))
                initials = _text(author.find("Initials"))
                if last:
                    name = f"{last} {initials}" if initials else last
                    authors.append(name)

    # Journal title
    journal = ""
    if article is not None:
        journal_elem = article.find("Journal")
        if journal_elem is not None:
            journal = _text(journal_elem.find("Title"))

    # Publication year
    year = ""
    if article is not None:
        journal_elem = article.find("Journal")
        if journal_elem is not None:
            ji = journal_elem.find("JournalIssue")
            if ji is not None:
                pub_date = ji.find("PubDate")
                if pub_date is not None:
                    year = _text(pub_date.find("Year"))
                    if not year:
                        # Some entries use MedlineDate instead of Year
                        medline_date = _text(pub_date.find("MedlineDate"))
                        if medline_date:
                            year = medline_date[:4]

    # DOI
    doi: Optional[str] = None
    pub_data = article_elem.find(".//PubmedData")
    if pub_data is not None:
        article_id_list = pub_data.find("ArticleIdList")
        if article_id_list is not None:
            for aid in article_id_list.findall("ArticleId"):
                if aid.get("IdType") == "doi":
                    doi = _text(aid)
                    break

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "journal": journal,
        "year": year,
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }
