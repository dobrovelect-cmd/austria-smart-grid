"""Stable station matching for EbUtilities records.

The API UID is not stable across imports. Use the reporting network operator
and the operator-reported substation name as the station key instead.
"""

import re
import unicodedata


def normalize_station_label(value):
    """Normalize labels while removing trailing source footnote markers."""
    if value is None:
        return ""
    text = str(value).strip().casefold()
    text = re.sub(r"[*†‡⁰¹²³⁴⁵⁶⁷⁸⁹]+$", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    # Preserve punctuation: it can distinguish two separately listed nodes
    # (for example, "UW Eibesbrunn" and "UW Eibesbrunn'").
    return re.sub(r"\\s+", " ", text).strip()


def station_match_key(operator, station_name):
    """Build a stable key from the reporting operator and station name."""
    return (
        normalize_station_label(operator),
        normalize_station_label(station_name),
    )


def index_api_stations(powerstations):
    """Index API stations by stable operator/name key and reject ambiguity."""
    indexed = {}
    for item in powerstations:
        key = station_match_key(
            item.get("networkOperator"),
            item.get("substationName"),
        )
        if not all(key):
            continue
        if key in indexed:
            raise ValueError(
                "Mehrdeutiger API-Schlüssel für Netzbetreiber/Netzknoten: "
                f"{item.get('networkOperator')} / {item.get('substationName')}"
            )
        indexed[key] = item
    return indexed
