"""arXiv API client for clinical-research-mcp.

Searches biomedical/bioinformatics papers from arXiv.
No API key required -- uses the public Atom feed endpoint.
"""

import xml.etree.ElementTree as ET

import httpx

ARXIV_API_URL = "https://export.arxiv.org/api/query"

NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _parse_entry(entry: ET.Element) -> dict:
    """Parse a single Atom entry element into a paper dict."""
    # Extract arxiv ID from <id> tag (e.g. http://arxiv.org/abs/2603.12345v1 -> 2603.12345v1)
    raw_id = entry.findtext("atom:id", default="", namespaces=NAMESPACES).strip()
    arxiv_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id

    # PDF URL: replace /abs/ with /pdf/
    pdf_url = raw_id.replace("/abs/", "/pdf/") if "/abs/" in raw_id else ""

    title = entry.findtext("atom:title", default="", namespaces=NAMESPACES)
    title = " ".join(title.split())

    abstract = entry.findtext("atom:summary", default="", namespaces=NAMESPACES)
    abstract = " ".join(abstract.split())

    published = entry.findtext("atom:published", default="", namespaces=NAMESPACES).strip()

    authors = [
        name_el.text.strip()
        for author_el in entry.findall("atom:author", namespaces=NAMESPACES)
        if (name_el := author_el.find("atom:name", namespaces=NAMESPACES)) is not None
        and name_el.text
    ]

    categories = [
        cat_el.attrib.get("term", "")
        for cat_el in entry.findall("atom:category", namespaces=NAMESPACES)
        if cat_el.attrib.get("term")
    ]

    return {
        "id": arxiv_id,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "published": published,
        "pdf_url": pdf_url,
        "categories": categories,
    }


def search_papers(
    query: str,
    max_results: int = 5,
    sort_by: str = "relevance",
) -> list[dict]:
    """Search arXiv papers by query string.

    Args:
        query: Search query (free text).
        max_results: Maximum number of results to return.
        sort_by: Sort criterion (relevance, submittedDate, lastUpdatedDate).
            Defaults to relevance -- better for clinical research lookups.

    Returns:
        List of paper dicts with keys: id, title, authors, abstract,
        published, pdf_url, categories.
    """
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": "descending",
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(ARXIV_API_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"arXiv API request failed: {exc}") from exc

    root = ET.fromstring(resp.text)
    entries = root.findall("atom:entry", namespaces=NAMESPACES)

    results: list[dict] = []
    for entry in entries:
        paper = _parse_entry(entry)
        # Skip placeholder entries that arXiv returns on empty results
        if paper["id"] and paper["title"]:
            results.append(paper)

    return results


def get_paper(arxiv_id: str) -> dict:
    """Fetch a single paper by its arXiv ID.

    Args:
        arxiv_id: arXiv identifier (e.g. "2603.12345").

    Returns:
        Paper dict with keys: id, title, authors, abstract,
        published, pdf_url, categories.

    Raises:
        RuntimeError: If the paper is not found or the API request fails.
    """
    params = {"id_list": arxiv_id}

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(ARXIV_API_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"arXiv API request failed for {arxiv_id}: {exc}") from exc

    root = ET.fromstring(resp.text)
    entries = root.findall("atom:entry", namespaces=NAMESPACES)

    if not entries:
        raise RuntimeError(f"No paper found for arXiv ID: {arxiv_id}")

    paper = _parse_entry(entries[0])
    if not paper["id"] or not paper["title"]:
        raise RuntimeError(f"No paper found for arXiv ID: {arxiv_id}")

    return paper
