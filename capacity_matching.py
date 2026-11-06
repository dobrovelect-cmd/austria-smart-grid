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
    text = re.sub(r"[*†‡¹²³⁴⁵⁶⁷⁸⁹⁰]+$", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return "".join(char for char in text if char.isalnum())


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
