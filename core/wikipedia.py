"""Wikipedia API client for clinical-research-mcp.

Provides functions to search Wikipedia articles, retrieve summaries,
and look up equivalent article titles across languages.
Uses the MediaWiki Action API and REST API. No API key required.
"""

import re
from urllib.parse import quote

import httpx

HEADERS = {
    "User-Agent": "clinical-research-mcp/0.1.0",
}

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return _TAG_RE.sub("", text)


def search(
    query: str,
    lang: str = "en",
    limit: int = 5,
) -> list[dict]:
    """Search Wikipedia articles.

    Args:
        query: Search query string.
        lang: Wikipedia language code (e.g. "en", "ko").
        limit: Maximum number of results to return.

    Returns:
        List of dicts with keys: title, snippet, pageid, url.
    """
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }

    try:
        with httpx.Client(headers=HEADERS, timeout=15.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Wikipedia search failed: {exc}") from exc

    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"Wikipedia API error: {data['error'].get('info', str(data['error']))}")

    results = []
    for item in data.get("query", {}).get("search", []):
        title = item["title"]
        results.append(
            {
                "title": title,
                "snippet": _strip_html(item.get("snippet", "")),
                "pageid": item["pageid"],
                "url": f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
            }
        )
    return results


def get_summary(
    title: str,
    lang: str = "en",
    sentences: int = 3,
) -> dict:
    """Get a summary of a Wikipedia article.

    Args:
        title: Article title.
        lang: Wikipedia language code.
        sentences: Number of sentences to include.

    Returns:
        Dict with keys: title, summary, url, description.
    """
    encoded_title = quote(title.replace(" ", "_"))
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"

    try:
        with httpx.Client(headers=HEADERS, timeout=15.0) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                raise RuntimeError(f"Wikipedia article not found: {title}")
            resp.raise_for_status()
    except RuntimeError:
        raise
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Wikipedia summary request failed: {exc}") from exc

    data = resp.json()

    extract = data.get("extract", "")
    if sentences and extract:
        parts = re.split(r"(?<=\.)\s+", extract)
        if len(parts) > sentences:
            extract = " ".join(parts[:sentences])

    return {
        "title": data.get("title", title),
        "summary": extract,
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "description": data.get("description", ""),
    }


def get_links_for_lang(
    title: str,
    from_lang: str = "en",
    to_lang: str = "ko",
) -> str | None:
    """Get the equivalent article title in another language.

    Args:
        title: Article title in the source language.
        from_lang: Source Wikipedia language code.
        to_lang: Target Wikipedia language code.

    Returns:
        The article title in the target language, or None.
    """
    url = f"https://{from_lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "langlinks",
        "lllang": to_lang,
        "format": "json",
    }

    try:
        with httpx.Client(headers=HEADERS, timeout=15.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Wikipedia langlinks request failed: {exc}") from exc

    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        langlinks = page.get("langlinks", [])
        for link in langlinks:
            if link.get("lang") == to_lang:
                return link.get("*")
    return None
