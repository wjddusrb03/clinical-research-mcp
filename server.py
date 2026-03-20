"""
clinical-research-mcp — MCP server for clinical & medical research
PubMed papers, clinical trials, medical concepts, biomedical papers.
All features work without any API key.
"""

import argparse
import sys
import datetime

from mcp.server.fastmcp import FastMCP

import core.pubmed as pubmed
import core.trials as trials
import core.arxiv as arxiv
import core.wikipedia as wikipedia

mcp = FastMCP("clinical-research")

DISCLAIMER = (
    "\n---\n"
    "*For informational purposes only. "
    "Always consult a healthcare professional for medical decisions.*"
)


# ──────────────────────────────────────────────
# API Status
# ──────────────────────────────────────────────

@mcp.tool()
def api_status() -> str:
    """Check which APIs are available."""
    lines = ["## API Status\n"]
    lines.append("  PubMed (NCBI):       [OK] Ready (no key needed)")
    lines.append("  ClinicalTrials.gov:  [OK] Ready (no key needed)")
    lines.append("  arXiv:               [OK] Ready (no key needed)")
    lines.append("  Wikipedia:           [OK] Ready (no key needed)")
    lines.append("")
    lines.append("All features available. No API keys required.")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# PubMed Search
# ──────────────────────────────────────────────

@mcp.tool()
def search_pubmed(query: str, count: int = 5, sort: str = "relevance") -> str:
    """Search PubMed for medical/scientific papers.

    - query: Search keywords (e.g. 'CGRP migraine treatment')
    - count: Number of results (default: 5)
    - sort: 'relevance' or 'date' (default: relevance)
    """
    try:
        articles = pubmed.search_and_fetch(query, max_results=count, sort=sort)
    except Exception as e:
        return f"[Error] PubMed search failed: {e}"

    if not articles:
        return f"No PubMed articles found for '{query}'."

    lines = [f"## PubMed Search: '{query}'\n"]
    for i, a in enumerate(articles, 1):
        authors = ", ".join(a["authors"][:3])
        if len(a["authors"]) > 3:
            authors += " et al."
        lines.append(f"  {i}. **{a['title']}**")
        lines.append(f"     Authors: {authors}")
        lines.append(f"     Journal: {a['journal']} ({a['year']})")
        lines.append(f"     PMID: {a['pmid']}")
        if a.get("doi"):
            lines.append(f"     DOI: {a['doi']}")
        abstract = a.get("abstract", "")
        if abstract:
            lines.append(f"     Abstract: {abstract[:200]}...")
        lines.append(f"     Link: {a['url']}")
        lines.append("")

    lines.append(DISCLAIMER)
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Paper Detail
# ──────────────────────────────────────────────

@mcp.tool()
def paper_detail(pmid: str) -> str:
    """Get detailed info about a PubMed paper and find related articles.

    - pmid: PubMed ID (e.g. '39876543')
    """
    # Fetch the main article
    try:
        articles = pubmed.fetch_articles([pmid])
    except Exception as e:
        return f"[Error] Could not fetch paper: {e}"

    if not articles:
        return f"No paper found for PMID: {pmid}"

    a = articles[0]
    sections = [f"## {a['title']}\n"]

    authors = ", ".join(a["authors"][:5])
    if len(a["authors"]) > 5:
        authors += " et al."
    sections.append(f"**Authors:** {authors}")
    sections.append(f"**Journal:** {a['journal']} ({a['year']})")
    sections.append(f"**PMID:** {a['pmid']}")
    if a.get("doi"):
        sections.append(f"**DOI:** {a['doi']}")
    sections.append(f"**Link:** {a['url']}")
    sections.append("")

    abstract = a.get("abstract", "")
    if abstract:
        sections.append(f"### Abstract\n\n{abstract}\n")
    else:
        sections.append("### Abstract\n\nNot available.\n")

    # Related articles
    try:
        related_pmids = pubmed.get_related(pmid, max_results=5)
        if related_pmids:
            related = pubmed.fetch_articles(related_pmids)
            if related:
                sections.append("### Related Articles\n")
                for i, r in enumerate(related, 1):
                    sections.append(f"  {i}. {r['title']}")
                    sections.append(f"     {r['journal']} ({r['year']}) | PMID: {r['pmid']}")
                sections.append("")
    except Exception:
        pass

    sections.append(DISCLAIMER)
    return "\n".join(sections)


# ──────────────────────────────────────────────
# Clinical Trials Search
# ──────────────────────────────────────────────

@mcp.tool()
def search_trials(query: str, count: int = 5, status: str = "") -> str:
    """Search ClinicalTrials.gov for clinical trials.

    - query: Search keywords (e.g. 'Alzheimer's disease immunotherapy')
    - count: Number of results (default: 5)
    - status: Filter by status (optional). Values: RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING, NOT_YET_RECRUITING
    """
    try:
        studies = trials.search_studies(query, max_results=count, status=status)
    except Exception as e:
        return f"[Error] Clinical trials search failed: {e}"

    if not studies:
        msg = f"No clinical trials found for '{query}'"
        if status:
            msg += f" (status: {status})"
        return msg + "."

    lines = [f"## Clinical Trials: '{query}'"]
    if status:
        lines[0] += f" (Status: {status})"
    lines.append("")

    for i, s in enumerate(studies, 1):
        lines.append(f"  {i}. **{s['title']}**")
        lines.append(f"     NCT ID: {s['nct_id']}")
        lines.append(f"     Status: {s['status']} | Phase: {s['phase']}")
        if s.get("conditions"):
            lines.append(f"     Conditions: {', '.join(s['conditions'][:3])}")
        if s.get("interventions"):
            lines.append(f"     Interventions: {', '.join(s['interventions'][:3])}")
        if s.get("enrollment"):
            lines.append(f"     Enrollment: {s['enrollment']} participants")
        if s.get("sponsor"):
            lines.append(f"     Sponsor: {s['sponsor']}")
        dates = []
        if s.get("start_date"):
            dates.append(f"Start: {s['start_date']}")
        if s.get("completion_date"):
            dates.append(f"Est. completion: {s['completion_date']}")
        if dates:
            lines.append(f"     {' | '.join(dates)}")
        lines.append(f"     Link: {s['url']}")
        lines.append("")

    lines.append(DISCLAIMER)
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Trial Detail
# ──────────────────────────────────────────────

@mcp.tool()
def trial_detail(nct_id: str) -> str:
    """Get detailed info about a specific clinical trial.

    - nct_id: ClinicalTrials.gov NCT ID (e.g. 'NCT06123456')
    """
    try:
        s = trials.get_study(nct_id)
    except Exception as e:
        return f"[Error] Could not fetch trial: {e}"

    lines = [f"## {s['title']}\n"]
    lines.append(f"**NCT ID:** {s['nct_id']}")
    lines.append(f"**Status:** {s['status']}")
    lines.append(f"**Phase:** {s['phase']}")
    lines.append(f"**Sponsor:** {s.get('sponsor', 'N/A')}")
    if s.get("enrollment"):
        lines.append(f"**Enrollment:** {s['enrollment']} participants")
    dates = []
    if s.get("start_date"):
        dates.append(f"Start: {s['start_date']}")
    if s.get("completion_date"):
        dates.append(f"Est. completion: {s['completion_date']}")
    if dates:
        lines.append(f"**Dates:** {' | '.join(dates)}")
    lines.append(f"**Link:** {s['url']}")
    lines.append("")

    if s.get("conditions"):
        lines.append(f"**Conditions:** {', '.join(s['conditions'])}")
    if s.get("interventions"):
        lines.append(f"**Interventions:** {', '.join(s['interventions'])}")
    lines.append("")

    if s.get("brief_summary"):
        lines.append(f"### Summary\n\n{s['brief_summary']}\n")

    if s.get("eligibility"):
        lines.append(f"### Eligibility\n\n{s['eligibility']}\n")

    if s.get("locations"):
        lines.append("### Locations\n")
        for loc in s["locations"]:
            lines.append(f"  - {loc}")
        lines.append("")

    if s.get("references"):
        lines.append("### References\n")
        for ref in s["references"]:
            pmid = ref.get("pmid", "")
            citation = ref.get("citation", "")
            if pmid:
                lines.append(f"  - PMID {pmid}: {citation[:150]}")
            elif citation:
                lines.append(f"  - {citation[:150]}")
        lines.append("")

    lines.append(DISCLAIMER)
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Medical Concept (Wikipedia)
# ──────────────────────────────────────────────

@mcp.tool()
def get_medical_concept(term: str, lang: str = "en") -> str:
    """Look up a medical/scientific concept on Wikipedia.

    - term: Medical term (e.g. 'CGRP', 'monoclonal antibody', 'randomized controlled trial')
    - lang: Language code ('en', 'ko', 'ja', etc.) Default: en
    """
    # Get summary
    try:
        summary = wikipedia.get_summary(term, lang=lang, sentences=5)
    except Exception:
        # Try search instead
        try:
            results = wikipedia.search(term, lang=lang, limit=1)
            if results:
                summary = wikipedia.get_summary(results[0]["title"], lang=lang, sentences=5)
            else:
                return f"No Wikipedia article found for '{term}'."
        except Exception as e:
            return f"[Error] Wikipedia lookup failed: {e}"

    lines = [f"## {summary['title']}\n"]
    if summary.get("description"):
        lines.append(f"*{summary['description']}*\n")
    lines.append(summary["summary"])
    lines.append("")
    if summary.get("url"):
        lines.append(f"Link: {summary['url']}")

    # Try Korean link if lang is English
    if lang == "en":
        try:
            ko_title = wikipedia.get_links_for_lang(summary["title"], from_lang="en", to_lang="ko")
            if ko_title:
                lines.append(f"Korean: https://ko.wikipedia.org/wiki/{ko_title}")
        except Exception:
            pass

    lines.append(DISCLAIMER)
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Combined Research Report (killer feature)
# ──────────────────────────────────────────────

@mcp.tool()
def research_medical(topic: str, count: int = 5) -> str:
    """All-in-one medical research: PubMed papers + clinical trials + concept explanation + biomedical papers.
    This is the main tool -- generates a comprehensive medical research report.

    - topic: Research topic (e.g. 'CGRP migraine treatment', 'CAR-T cell therapy lymphoma')
    - count: Number of results per section (default: 5)
    """
    sections = []
    sections.append(f"# Medical Research Report: {topic}\n")
    sections.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    sections.append("---\n")

    # 1. Key Concept (Wikipedia)
    sections.append("## 1. Key Concept (Wikipedia)\n")
    try:
        wiki_results = wikipedia.search(topic, lang="en", limit=1)
        if wiki_results:
            summary = wikipedia.get_summary(wiki_results[0]["title"], lang="en", sentences=3)
            sections.append(f"  **{summary['title']}**")
            sections.append(f"  {summary['summary'][:300]}")
            if summary.get("url"):
                sections.append(f"  Link: {summary['url']}")
            # Korean link
            try:
                ko = wikipedia.get_links_for_lang(wiki_results[0]["title"], "en", "ko")
                if ko:
                    sections.append(f"  Korean: https://ko.wikipedia.org/wiki/{ko}")
            except Exception:
                pass
        else:
            sections.append("  No Wikipedia article found.")
    except Exception as e:
        sections.append(f"  [Skipped] Wikipedia error: {e}")
    sections.append("")
    sections.append("---\n")

    # 2. Latest Research (PubMed)
    sections.append("## 2. Latest Research (PubMed)\n")
    try:
        articles = pubmed.search_and_fetch(topic, max_results=count, sort="date")
        if articles:
            for i, a in enumerate(articles, 1):
                authors = ", ".join(a["authors"][:3])
                if len(a["authors"]) > 3:
                    authors += " et al."
                sections.append(f"  {i}. **{a['title']}**")
                sections.append(f"     Authors: {authors}")
                sections.append(f"     Journal: {a['journal']} ({a['year']})")
                sections.append(f"     PMID: {a['pmid']}")
                abstract = a.get("abstract", "")
                if abstract:
                    sections.append(f"     Abstract: {abstract[:150]}...")
                sections.append(f"     Link: {a['url']}")
                sections.append("")
        else:
            sections.append("  No PubMed articles found.\n")
    except Exception as e:
        sections.append(f"  [Skipped] PubMed error: {e}\n")
    sections.append("---\n")

    # 3. Active Clinical Trials
    sections.append("## 3. Active Clinical Trials\n")
    try:
        recruiting = trials.search_studies(topic, max_results=count, status="RECRUITING")
        if not recruiting:
            recruiting = trials.search_studies(topic, max_results=count)
        if recruiting:
            for i, s in enumerate(recruiting, 1):
                sections.append(f"  {i}. **{s['title']}**")
                sections.append(f"     NCT ID: {s['nct_id']} | Status: {s['status']}")
                sections.append(f"     Phase: {s['phase']}")
                if s.get("sponsor"):
                    sections.append(f"     Sponsor: {s['sponsor']}")
                if s.get("enrollment"):
                    sections.append(f"     Enrollment: {s['enrollment']} participants")
                sections.append(f"     Link: {s['url']}")
                sections.append("")
        else:
            sections.append("  No clinical trials found.\n")
    except Exception as e:
        sections.append(f"  [Skipped] ClinicalTrials.gov error: {e}\n")
    sections.append("---\n")

    # 4. Biomedical Papers (arXiv) - bonus section
    sections.append("## 4. Related Biomedical Papers (arXiv)\n")
    try:
        papers = arxiv.search_papers(topic, max_results=3)
        if papers:
            for i, p in enumerate(papers, 1):
                authors = ", ".join(p["authors"][:3])
                if len(p["authors"]) > 3:
                    authors += " et al."
                sections.append(f"  {i}. **{p['title']}**")
                sections.append(f"     {authors} ({p['published'][:10]})")
                sections.append(f"     PDF: {p['pdf_url']}")
                sections.append("")
        else:
            sections.append("  No related arXiv papers found.\n")
    except Exception as e:
        sections.append(f"  [Skipped] arXiv error: {e}\n")

    sections.append("---\n")
    sections.append("*Report generated by clinical-research-mcp*")
    sections.append(DISCLAIMER)

    return "\n".join(sections)


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Clinical Research MCP Server")
    args = parser.parse_args()

    print("clinical-research-mcp: server starting", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
