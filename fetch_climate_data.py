import os
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GRID_API_URL = "https://www.ebutilities.at/api/powerstations/list"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_HEADERS = {"User-Agent": "SMART-Grid-Austria/1.0 (research data collection)"}
BATCH_SIZE = 10
REQUEST_DELAY_SECONDS = 0.5
OUTPUT_FILE = Path("substations_climate_base.csv")

# Retry temporary API failures and honour Retry-After responses.
retry_policy = Retry(
    total=5,
    connect=5,
    read=5,
    status=5,
    backoff_factor=1.0,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
    respect_retry_after_header=True,
)
session = requests.Session()
session.headers.update(REQUEST_HEADERS)
session.mount("https://", HTTPAdapter(max_retries=retry_policy))


def parse_float(value, default=None):
    """Parse Austrian decimal notation and reject missing coordinate values."""
    if value is None or str(value).strip() == "":
        return default
    return float(str(value).strip().replace(",", "."))


def prepare_station(item, index):
    """Normalise one EbUtilities record before making weather requests."""
    latitude = parse_float(item.get("latitude"))
    longitude = parse_float(item.get("longitude"))
    if latitude is None or longitude is None or latitude == 0 or longitude == 0:
        return None

    return {
        "UID": item.get("powerstationId", index),
        "Name": item.get("substationName", "Unbekannt"),
        "Frei_MVA": parse_float(item.get("availableCapacity"), 0.0),
        "Belegt_MVA": parse_float(item.get("bookedCapacity"), 0.0),
        "Breite": latitude,
        "Länge": longitude,
        "Bundesland": item.get("state", "N/A"),
        "Betreiber": item.get("networkOperator", "N/A"),
        "Kontakt": str(
            item.get("contact", item.get("contactEmail", item.get("email", "N/A")))
        ),
        "Webseite": str(
            item.get("website", item.get("url", item.get("operatorUrl", "N/A")))
        ),
    }


def parse_weather_response(payload, expected_count):
    """Normalise Open-Meteo's single-location and multi-location response formats."""
    if isinstance(payload, dict):
        if payload.get("error"):
            raise ValueError(payload.get("reason", "Open-Meteo returned an error"))
        responses = [payload]
    elif isinstance(payload, list):
        responses = payload
    else:
        raise ValueError("Unexpected Open-Meteo response format")

    if len(responses) != expected_count:
        raise ValueError(
            f"Open-Meteo returned {len(responses)} locations; "
            f"expected {expected_count}"
        )

    results = []
    for location_index, weather in enumerate(responses):
        if weather.get("error"):
            raise ValueError(
                f"Open-Meteo location {location_index}: "
                f"{weather.get('reason', 'API error')}"
            )

        hourly = weather.get("hourly", {})
        hourly_units = weather.get("hourly_units", {})
        wind_values = hourly.get("wind_speed_100m")
        radiation_values = hourly.get("shortwave_radiation")

        if hourly_units.get("wind_speed_100m") != "m/s":
            raise ValueError(
                "Open-Meteo unit mismatch: expected wind_speed_100m in m/s, "
                f"received {hourly_units.get('wind_speed_100m')!r}"
            )
        if not wind_values or not radiation_values:
            raise ValueError(
                f"Open-Meteo location {location_index} returned incomplete hourly data"
            )
        if len(wind_values) != len(radiation_values):
            raise ValueError(
                f"Open-Meteo location {location_index}: weather arrays differ in length"
            )

        wind = pd.to_numeric(pd.Series(wind_values), errors="coerce")
        radiation = pd.to_numeric(pd.Series(radiation_values), errors="coerce")
        if wind.isna().any() or radiation.isna().any():
            raise ValueError(
                f"Open-Meteo location {location_index}: missing or non-numeric values"
            )

        # Hourly mean wind speed at 100 m above ground, expressed in m/s.
        average_wind_ms = round(float(wind.mean()), 2)

        # shortwave_radiation is the hourly mean irradiance in W/m².
        # Sum over hourly intervals and divide by 1000 -> annual irradiation kWh/m².
        annual_shortwave_kwh_m2 = round(float(radiation.sum()) / 1000.0, 1)
        results.append((average_wind_ms, annual_shortwave_kwh_m2))

    return results


def fetch_weather_batch(stations):
    """Fetch historical weather for up to BATCH_SIZE locations in one API call."""
    params = {
        "latitude": ",".join(f"{station['Breite']:.6f}" for station in stations),
        "longitude": ",".join(f"{station['Länge']:.6f}" for station in stations),
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "hourly": "wind_speed_100m,shortwave_radiation",
        "wind_speed_unit": "ms",
        "timezone": "Europe/Vienna",
    }
    response = session.get(OPEN_METEO_URL, params=params, timeout=(15, 90))
    response.raise_for_status()
    return parse_weather_response(response.json(), len(stations))


def main():
    print("📡 Schritt 1: Lade österreichische Netzknotendaten...")
    response = session.get(GRID_API_URL, timeout=(15, 60))
    response.raise_for_status()
    powerstations = response.json().get("powerstations", [])
    if not powerstations:
        raise RuntimeError("EbUtilities returned no powerstation records.")

    stations = []
    skipped_coordinates = []
    for index, item in enumerate(powerstations):
        station = prepare_station(item, index)
        if station is None:
            skipped_coordinates.append(item.get("substationName", f"Index {index}"))
        else:
            stations.append(station)

    if not stations:
        raise RuntimeError("No powerstation records contain valid coordinates.")

    print(
        f"Gefunden: {len(powerstations)} Datensätze; "
        f"{len(stations)} mit gültigen Koordinaten. "
        f"Starte historische Klimadaten-Abfrage für 2024 in Paketen zu {BATCH_SIZE}..."
    )
    if skipped_coordinates:
        print(
            f"⚠️ {len(skipped_coordinates)} Datensätze ohne gültige Koordinaten "
            "werden nicht verarbeitet."
        )

    clean_stations = []
    total_batches = (len(stations) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_index in range(total_batches):
        start = batch_index * BATCH_SIZE
        batch = stations[start : start + BATCH_SIZE]
        weather_results = fetch_weather_batch(batch)

        for station, (average_wind_ms, annual_shortwave_kwh_m2) in zip(
            batch, weather_results
        ):
            output_record = dict(station)
            output_record["Wind_ms"] = average_wind_ms
            output_record["Solar_kWh"] = annual_shortwave_kwh_m2
            clean_stations.append(output_record)

        print(
            f"▓ Fortschritt: Paket {batch_index + 1}/{total_batches}; "
            f"{len(clean_stations)}/{len(stations)} Netzknoten verarbeitet."
        )
        if batch_index + 1 < total_batches:
            time.sleep(REQUEST_DELAY_SECONDS)

    df = pd.DataFrame(clean_stations)

    if df.empty or len(df) != len(stations):
        raise RuntimeError(
            f"Datensatz unvollständig: {len(df)} von {len(stations)} Knoten."
        )
    if df["UID"].duplicated().any():
        duplicated = df.loc[df["UID"].duplicated(), "UID"].tolist()
        raise RuntimeError(f"Doppelte Netzknoten-IDs gefunden: {duplicated[:10]}")
    if df[["Wind_ms", "Solar_kWh", "Frei_MVA", "Belegt_MVA"]].isna().any().any():
        raise RuntimeError("Final dataset contains missing numeric values.")
    if not df["Wind_ms"].between(0, 100).all():
        raise RuntimeError("Wind_ms contains implausible values outside 0–100 m/s.")
    if not df["Solar_kWh"].between(0, 3000).all():
        raise RuntimeError("Solar_kWh contains implausible values outside 0–3000 kWh/m².")

    # Write to a temporary file first; replace the previous snapshot only after
    # every location was retrieved and all validation checks have passed.
    temporary_file = OUTPUT_FILE.with_suffix(OUTPUT_FILE.suffix + ".tmp")
    df.to_csv(temporary_file, index=False, encoding="utf-8")
    os.replace(temporary_file, OUTPUT_FILE)

    print(
        f"✅ CSV erfolgreich erstellt: {len(df)} Netzknoten; "
        f"Wind_ms in m/s; Solar_kWh in kWh/m²."
    )
    print(
        f"Wind_ms Mittelwert: {df['Wind_ms'].mean():.2f} m/s; "
        f"Solar_kWh Mittelwert: {df['Solar_kWh'].mean():.1f} kWh/m²."
    )


if __name__ == "__main__":
    main()
