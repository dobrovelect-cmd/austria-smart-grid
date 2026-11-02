import requests
import pandas as pd
import time

API_URL = "https://www.ebutilities.at/api/powerstations/list"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
headers = {'User-Agent': 'Mozilla/5.0'}

print("📡 Schritt 1: Lade Datenbank der Umspannwerke in Österreich...")
try:
    response = requests.get(API_URL, headers=headers, timeout=15)
    response.raise_for_status()
    powerstations = response.json().get('powerstations', [])
except Exception as e:
    print(f"❌ Netzwerkfehler beim Laden der Netzdaten: {e}")
    raise SystemExit(1)

clean_stations = []
print(f" Gefunden: {len(powerstations)} Anlagen. Starte Klimadaten-Abfrage für 2024...")

for idx, item in enumerate(powerstations):
    try:
        lat = float(str(item.get('latitude', '0')).replace(',', '.'))
        lon = float(str(item.get('longitude', '0')).replace(',', '.'))
        if lat == 0 or lon == 0:
            continue

        # Erweiterte Suche nach Kontakten und Websites.
        contact = item.get('contact', item.get('contactEmail', item.get('email', 'N/A')))
        website = item.get('website', item.get('url', item.get('operatorUrl', 'N/A')))

        # Open-Meteo: Windgeschwindigkeit explizit in m/s anfordern.
        # wind_speed_100m ist die dokumentierte API-Variable (100 m über Grund).
        weather_params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "hourly": "wind_speed_100m,shortwave_radiation",
            "wind_speed_unit": "ms",
            "timezone": "Europe/Berlin",
        }
        w_response = requests.get(OPEN_METEO_URL, params=weather_params, timeout=30)
        w_response.raise_for_status()
        weather = w_response.json()

        if weather.get("error"):
            raise ValueError(weather.get("reason", "Open-Meteo returned an error"))

        hourly = weather.get("hourly", {})
        wind_values = hourly.get("wind_speed_100m")
        solar_values = hourly.get("shortwave_radiation")
        hourly_units = weather.get("hourly_units", {})
        wind_unit = hourly_units.get("wind_speed_100m")

        if not wind_values or not solar_values:
            raise ValueError("Open-Meteo returned incomplete hourly weather data")
        if wind_unit != "m/s":
            raise ValueError(
                f"Expected wind_speed_100m in m/s, received {wind_unit!r}"
            )

        # Wind_ms: Mittelwert der stündlichen Windgeschwindigkeit auf 100 m in m/s.
        avg_wind = round(pd.Series(wind_values, dtype="float64").mean(), 2)

        # shortwave_radiation is hourly mean irradiance in W/m².
        # Summing hourly values and dividing by 1000 yields annual irradiation in kWh/m².
        total_solar = round(pd.Series(solar_values, dtype="float64").sum() / 1000, 1)

        clean_stations.append({
            "UID": item.get('powerstationId', idx),
            "Name": item.get('substationName', 'Unbekannt'),
            "Frei_MVA": float(str(item.get('availableCapacity', '0')).replace(',', '.')),
            "Belegt_MVA": float(str(item.get('bookedCapacity', '0')).replace(',', '.')),
            "Breite": lat,
            "Länge": lon,
            "Bundesland": item.get('state', 'N/A'),
            "Betreiber": item.get('networkOperator', 'N/A'),
            "Kontakt": str(contact),
            "Webseite": str(website),
            "Wind_ms": avg_wind,
            "Solar_kWh": total_solar
        })

        if (idx + 1) % 40 == 0 or (idx + 1) == len(powerstations):
            print(f"▓ Fortschritt: {idx + 1}/{len(powerstations)} Umspannwerke verarbeitet...")

        time.sleep(0.05)
    except Exception as e:
        station_name = item.get('substationName', f'Index {idx}')
        print(f"⚠️ Überspringe {station_name}: {e}")
        continue

df = pd.DataFrame(clean_stations)
if df.empty:
    raise RuntimeError("Es konnten keine Netzknoten mit vollständigen Klimadaten erstellt werden.")

df.to_csv("substations_climate_base.csv", index=False, encoding="utf-8")
print(
    f"✅ Datenbank 'substations_climate_base.csv' erstellt: "
    f"{len(df)} Netzknoten; Wind_ms in m/s, Solar_kWh in kWh/m²."
)
