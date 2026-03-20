"""ClinicalTrials.gov v2 API client.

Provides functions to search and retrieve clinical trial data from
the ClinicalTrials.gov v2 REST API. No API key required.

API documentation: https://clinicaltrials.gov/data-api/api
"""

import httpx

BASE_URL = "https://clinicaltrials.gov/api/v2/"
TIMEOUT = 30


def _get(path: str, params: dict | None = None) -> dict:
    """Send a GET request to the ClinicalTrials.gov v2 API."""
    url = BASE_URL + path
    try:
        resp = httpx.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"ClinicalTrials.gov API returned HTTP {exc.response.status_code} "
            f"for {url}: {exc.response.text[:300]}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Failed to connect to ClinicalTrials.gov API at {url}: {exc}"
        ) from exc


def _parse_study_summary(study: dict) -> dict:
    """Extract common fields from a v2 API study object."""
    protocol = study.get("protocolSection", {})

    id_mod = protocol.get("identificationModule", {})
    status_mod = protocol.get("statusModule", {})
    design_mod = protocol.get("designModule", {})
    conditions_mod = protocol.get("conditionsModule", {})
    arms_mod = protocol.get("armsInterventionsModule", {})
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})

    nct_id = id_mod.get("nctId", "")

    # Title: prefer officialTitle, fall back to briefTitle
    title = id_mod.get("officialTitle") or id_mod.get("briefTitle", "")

    # Phase: may be a list
    phases = design_mod.get("phases", [])
    if isinstance(phases, list) and phases:
        phase = " / ".join(phases)
    else:
        phase = "N/A"

    # Interventions: list of intervention name strings
    interventions_raw = arms_mod.get("interventions", [])
    interventions = []
    for item in interventions_raw:
        name = item.get("name", "")
        if name:
            interventions.append(name)

    # Enrollment
    enrollment_info = design_mod.get("enrollmentInfo", {})
    enrollment = enrollment_info.get("count")

    # Dates
    start_date = status_mod.get("startDateStruct", {}).get("date", "")
    completion_date = status_mod.get("completionDateStruct", {}).get("date", "")

    # Sponsor
    sponsor = sponsor_mod.get("leadSponsor", {}).get("name", "")

    return {
        "nct_id": nct_id,
        "title": title,
        "status": status_mod.get("overallStatus", ""),
        "phase": phase,
        "conditions": conditions_mod.get("conditions", []),
        "interventions": interventions,
        "enrollment": enrollment,
        "start_date": start_date,
        "completion_date": completion_date,
        "sponsor": sponsor,
        "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
    }


def search_studies(
    query: str,
    max_results: int = 10,
    status: str = "",
) -> list[dict]:
    """Search ClinicalTrials.gov for studies matching a query.

    Args:
        query: Free-text search term (e.g. disease, drug, or NCT ID).
        max_results: Maximum number of results to return (1-1000).
        status: Optional filter by overall status. Accepted values include
            RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING, NOT_YET_RECRUITING,
            TERMINATED, WITHDRAWN, SUSPENDED, etc.

    Returns:
        List of dicts, each containing summary fields for one study.

    Raises:
        RuntimeError: On HTTP or connection errors.
    """
    params: dict[str, str | int] = {
        "query.term": query,
        "pageSize": max_results,
    }
    if status:
        params["filter.overallStatus"] = status

    data = _get("studies", params=params)

    studies = data.get("studies", [])
    results: list[dict] = []
    for study in studies:
        results.append(_parse_study_summary(study))

    return results


def get_study(nct_id: str) -> dict:
    """Retrieve detailed information for a single study by NCT ID.

    Args:
        nct_id: The NCT identifier (e.g. "NCT12345678").

    Returns:
        Dict with detailed study fields including summary, eligibility,
        locations, and references.

    Raises:
        RuntimeError: On HTTP or connection errors.
    """
    data = _get(f"studies/{nct_id}")

    result = _parse_study_summary(data)

    protocol = data.get("protocolSection", {})

    # Description
    desc_mod = protocol.get("descriptionModule", {})
    result["brief_summary"] = desc_mod.get("briefSummary", "")

    detailed = desc_mod.get("detailedDescription", "")
    if len(detailed) > 500:
        detailed = detailed[:500] + "..."
    result["detailed_description"] = detailed

    # Eligibility
    elig_mod = protocol.get("eligibilityModule", {})
    eligibility = elig_mod.get("eligibilityCriteria", "")
    if len(eligibility) > 500:
        eligibility = eligibility[:500] + "..."
    result["eligibility"] = eligibility

    # Locations (first 5 facility names)
    contacts_mod = protocol.get("contactsLocationsModule", {})
    locations_raw = contacts_mod.get("locations", [])
    locations: list[str] = []
    for loc in locations_raw[:5]:
        facility = loc.get("facility", "")
        if facility:
            locations.append(facility)
    result["locations"] = locations

    # References (first 5)
    refs_mod = protocol.get("referencesModule", {})
    refs_raw = refs_mod.get("references", [])
    references: list[dict] = []
    for ref in refs_raw[:5]:
        references.append({
            "pmid": ref.get("pmid", ""),
            "citation": ref.get("citation", ""),
        })
    result["references"] = references

    return result
