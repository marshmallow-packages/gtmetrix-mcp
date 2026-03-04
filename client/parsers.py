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
