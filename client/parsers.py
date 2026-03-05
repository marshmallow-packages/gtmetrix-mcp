"""JSON:API v1.1 response transformations.

All GTMetrix API responses use JSON:API envelopes. These pure functions
strip the envelope and return flat dicts that tools can work with directly.
"""


def unwrap_jsonapi(response: dict) -> dict:
    """Strip the JSON:API envelope and return a flat dict of attributes.

    Extracts data.id, data.type, and all data.attributes into a single
    flat dict. Tools never need to navigate the JSON:API structure.

    Args:
        response: Raw JSON:API response dict from the GTMetrix API.

    Returns:
        Flat dict with 'id', 'type', and all attributes merged at top level.
        Returns empty dict if 'data' key is absent.
    """
    data = response.get("data")
    if not data:
        return {}
    return {
        "id": data.get("id"),
        "type": data.get("type"),
        **data.get("attributes", {}),
    }


def unwrap_jsonapi_list(response: dict) -> list[dict]:
    """Strip JSON:API envelope from a list response.

    Returns list of flat dicts, each with id, type, and all attributes.
    Returns empty list if 'data' key is absent or not a list.
    """
    data = response.get("data")
    if not data or not isinstance(data, list):
        return []
    return [
        {"id": item.get("id"), "type": item.get("type"), **item.get("attributes", {})}
        for item in data
    ]


def extract_vitals(report: dict) -> dict:
    """Extract Core Web Vitals from a report dict.

    Returns a dict with 5 keys: performance_score, structure_score,
    largest_contentful_paint_ms, total_blocking_time_ms, cumulative_layout_shift.
    Missing fields are returned as None.
    """
    return {
        "performance_score": report.get("performance_score"),
        "structure_score": report.get("structure_score"),
        "largest_contentful_paint_ms": report.get("largest_contentful_paint"),
        "total_blocking_time_ms": report.get("total_blocking_time"),
        "cumulative_layout_shift": report.get("cumulative_layout_shift"),
    }


def filter_failing_audits(lighthouse_json: dict) -> list[dict]:
    """Extract failing Lighthouse audits (score < 1).

    Returns a list of dicts with id, title, description, displayValue, score.
    Excludes audits with scoreDisplayMode in (notApplicable, manual, informative)
    and audits with score=None. Sorted by score ascending (worst first).
    """
    audits = lighthouse_json.get("audits", {})
    failing = []
    for audit_id, audit in audits.items():
        score = audit.get("score")
        mode = audit.get("scoreDisplayMode", "")
        if score is None or mode in ("notApplicable", "manual", "informative"):
            continue
        if score < 1:
            failing.append({
                "id": audit_id,
                "title": audit.get("title", ""),
                "description": audit.get("description", ""),
                "displayValue": audit.get("displayValue", ""),
                "score": score,
            })
    failing.sort(key=lambda a: a["score"])
    return failing


def extract_top_resources(har_json: dict, limit: int = 10) -> list[dict]:
    """Extract the top N slowest resources from a HAR file.

    Returns a list of dicts with url, size_bytes, duration_ms.
    Sorted by duration descending. Entries with time <= 0 are skipped.
    Falls back from _transferSize to bodySize for size; None if both missing.
    """
    entries = har_json.get("log", {}).get("entries", [])
    resources = []
    for entry in entries:
        duration = entry.get("time", 0)
        if duration <= 0:
            continue
        url = entry.get("request", {}).get("url", "")
        response = entry.get("response", {})
        size = response.get("_transferSize")
        if not size or size <= 0:
            size = response.get("bodySize")
        if size is not None and size <= 0:
            size = None
        resources.append({
            "url": _truncate_url(url),
            "size_bytes": size,
            "duration_ms": round(duration, 1),
        })
    resources.sort(key=lambda r: r["duration_ms"], reverse=True)
    return resources[:limit]


def _truncate_url(url: str, max_length: int = 120) -> str:
    """Truncate a URL for display, adding '...' if it exceeds max_length."""
    if len(url) <= max_length:
        return url
    return url[:max_length - 3] + "..."
