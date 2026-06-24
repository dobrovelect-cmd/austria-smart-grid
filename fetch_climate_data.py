import requests
import pandas as pd
import time

API_URL = "https://www.ebutilities.at/api/powerstations/list"
headers = {'User-Agent': 'Mozilla/5.0'}

print("📡 Schritt 1: Lade Live-Datenbank der Umspannwerke in Österreich...")
try:
    response = requests.get(API_URL, headers=headers, timeout=15)
    response.raise_for_status()
    powerstations = response.json().get('powerstations', [])
except Exception as e:
    print(f"❌ Netzwerkfehler: {e}")
    exit()

clean_stations = []
print(f" Gefunden: {len(powerstations)} Anlagen. Starte ERA5 Klima-Audit (Copernicus)...")

for idx, item in enumerate(powerstations):
    try:
        lat = float(str(item.get('latitude', '0')).replace(',', '.'))
        lon = float(str(item.get('longitude', '0')).replace(',', '.'))
        if lat == 0 or lon == 0: continue
        
        # Расширенный поиск контактов и сайтов (если API изменил ключи)
        contact = item.get('contact', item.get('contactEmail', item.get('email', 'N/A')))
        website = item.get('website', item.get('url', item.get('operatorUrl', 'N/A')))
        
        # Запрос климатических данных
        weather_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date=2024-01-01&end_date=2024-12-31&hourly=windspeed_100m,shortwave_radiation&timezone=Europe%2FBerlin"
        w_res = requests.get(weather_url, timeout=10).json()
        
        avg_wind = round(pd.Series(w_res['hourly']['windspeed_100m']).mean(), 2) 
        total_solar = round(pd.Series(w_res['hourly']['shortwave_radiation']).sum() / 1000, 1) 
        
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
        continue

df = pd.DataFrame(clean_stations)
df.to_csv("substations_climate_base.csv", index=False, encoding="utf-8")
print("✅ Datenbank 'substations_climate_base.csv' erfolgreich auf Deutsch erstellt!")
