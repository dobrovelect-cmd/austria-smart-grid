import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GRID_API_URL = "https://www.ebutilities.at/api/powerstations/list"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_HEADERS = {"User-Agent": "SMART-Grid-Austria/1.0 (research data collection)"}

# Retry temporary API failures (including rate limiting) and honour Retry-After.
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


def fetch_weather(latitude, longitude):
    """Fetch hourly 2024 wind and shortwave radiation with explicit SI units."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "hourly": "wind_speed_100m,shortwave_radiation",
        "wind_speed_unit": "ms",
        "timezone": "Europe/Berlin",
    }
    response = session.get(OPEN_METEO_URL, params=params, timeout=(15, 60))
    response.raise_for_status()
    payload = response.json()

    if payload.get("error"):
        raise ValueError(payload.get("reason", "Open-Meteo returned an error"))

    hourly = payload.get("hourly", {})
    hourly_units = payload.get("hourly_units", {})
    wind_values = hourly.get("wind_speed_100m")
    radiation_values = hourly.get("shortwave_radiation")

    if hourly_units.get("wind_speed_100m") != "m/s":
        raise ValueError(
            "Open-Meteo unit mismatch: expected wind_speed_100m in m/s, "
            f"received {hourly_units.get('wind_speed_100m')!r}"
        )
    if not wind_values or not radiation_values:
        raise ValueError("Open-Meteo returned incomplete hourly weather data")
    if len(wind_values) != len(radiation_values):
        raise ValueError("Wind and radiation arrays have different lengths")

    wind = pd.to_numeric(pd.Series(wind_values), errors="coerce")
    radiation = pd.to_numeric(pd.Series(radiation_values), errors="coerce")

    if wind.isna().any() or radiation.isna().any():
        raise ValueError("Open-Meteo data contain missing or non-numeric values")

    # Hourly mean wind speed at 100 m above ground, expressed in m/s.
    average_wind_ms = round(float(wind.mean()), 2)

    # shortwave_radiation is the hourly mean irradiance in W/m².
    # Sum over hourly intervals and divide by 1000 -> annual irradiation kWh/m².
    annual_shortwave_kwh_m2 = round(float(radiation.sum()) / 1000.0, 1)

    return average_wind_ms, annual_shortwave_kwh_m2


def main():
    print("📡 Schritt 1: Lade österreichische Netzknotendaten...")
    response = session.get(GRID_API_URL, timeout=(15, 60))
    response.raise_for_status()
    powerstations = response.json().get("powerstations", [])

    if not powerstations:
        raise RuntimeError("EbUtilities returned no powerstation records.")

    clean_stations = []
    failed_stations = []
    expected_stations = 0

    print(
        f"Gefunden: {len(powerstations)} Datensätze. "
        "Starte historische Klimadaten-Abfrage für 2024..."
    )

    for idx, item in enumerate(powerstations):
        station_name = item.get("substationName", f"Index {idx}")
        try:
            latitude = parse_float(item.get("latitude"))
            longitude = parse_float(item.get("longitude"))
            if latitude is None or longitude is None or latitude == 0 or longitude == 0:
                print(f"⚠️ Überspringe {station_name}: ungültige Koordinaten")
                continue

            expected_stations += 1
            average_wind_ms, annual_shortwave_kwh_m2 = fetch_weather(
                latitude, longitude
            )

            contact = item.get(
                "contact",
                item.get("contactEmail", item.get("email", "N/A")),
            )
            website = item.get(
                "website",
                item.get("url", item.get("operatorUrl", "N/A")),
            )

            clean_stations.append(
                {
                    "UID": item.get("powerstationId", idx),
                    "Name": station_name,
                    "Frei_MVA": parse_float(item.get("availableCapacity"), 0.0),
                    "Belegt_MVA": parse_float(item.get("bookedCapacity"), 0.0),
                    "Breite": latitude,
                    "Länge": longitude,
                    "Bundesland": item.get("state", "N/A"),
                    "Betreiber": item.get("networkOperator", "N/A"),
                    "Kontakt": str(contact),
                    "Webseite": str(website),
                    "Wind_ms": average_wind_ms,
                    "Solar_kWh": annual_shortwave_kwh_m2,
                }
            )

            if len(clean_stations) % 20 == 0:
                print(
                    f"▓ Fortschritt: {len(clean_stations)}/{expected_stations} "
                    "gültige Netzknoten verarbeitet..."
                )

        except Exception as exc:
            failed_stations.append((station_name, str(exc)))
            print(f"⚠️ Fehler bei {station_name}: {exc}")

        # Conservative spacing between archive API requests.
        time.sleep(0.5)

    if failed_stations:
        failed_names = ", ".join(name for name, _ in failed_stations[:10])
        raise RuntimeError(
            f"{len(failed_stations)} von {expected_stations} Netzknoten konnten "
            f"nicht vollständig verarbeitet werden. Fehlerhafte Datensätze: "
            f"{failed_names}. CSV wurde nicht überschrieben."
        )

    if not clean_stations:
        raise RuntimeError("Keine Netzknoten mit vollständigen Klimadaten erstellt.")

    df = pd.DataFrame(clean_stations)

    if df["UID"].duplicated().any():
        duplicated = df.loc[df["UID"].duplicated(), "UID"].tolist()
        raise RuntimeError(f"Doppelte Netzknoten-IDs gefunden: {duplicated[:10]}")

    if len(df) != expected_stations:
        raise RuntimeError(
            f"Datensatz unvollständig: {len(df)} von {expected_stations} Knoten."
        )

    df.to_csv("substations_climate_base.csv", index=False, encoding="utf-8")

    print(
        f"✅ CSV erfolgreich erstellt: {len(df)} Netzknoten; "
        f"Wind_ms in m/s; Solar_kWh in kWh/m²."
    )
    print(
        "Wind_ms Mittelwert: "
        f"{df['Wind_ms'].mean():.2f} m/s; "
        "Solar_kWh Mittelwert: "
        f"{df['Solar_kWh'].mean():.1f} kWh/m²."
    )


if __name__ == "__main__":
    main()
