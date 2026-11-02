# SMART Grid Austria & Speicher AI

Intelligentes Monitoring-Tool zur räumlichen Vorauswahl österreichischer Netzknoten für Windenergie, Photovoltaik und Batteriespeicher (BESS).

## Ausführung via Docker (Empfohlen)

1. Docker-Image bauen:
```bash
docker build -t austria-grid-dashboard:latest .
```

## Klimadaten und Einheiten

Die Klimakennwerte beziehen sich auf das Kalenderjahr 2024 und werden über die Open-Meteo Historical Weather API abgefragt.

- `Wind_ms`: arithmetischer Mittelwert der stündlichen Variable `wind_speed_100m` in **m/s**. Der API-Aufruf setzt `wind_speed_unit=ms` ausdrücklich und prüft die zurückgemeldete Einheit.
- `Solar_kWh`: jährliche Summe der stündlichen Mittelwerte von `shortwave_radiation`, geteilt durch 1000. Die resultierende Einheit ist **kWh/m²** (globale kurzwellige Einstrahlung auf eine horizontale Fläche), nicht die elektrische PV-Erzeugung.
- Die Wetterwerte stammen aus räumlichen Reanalyse-/Modellgitterzellen und sind keine standortspezifischen Messungen oder Ertragsprognosen.

Das bestehende CSV-Snapshot wurde korrigiert: Die zuvor mit der Open-Meteo-Standardkonfiguration gespeicherten Windwerte in km/h wurden durch 3,6 geteilt und in m/s umgerechnet. Bei einer erneuten Ausführung von `fetch_climate_data.py` werden die Klimadaten direkt in m/s angefordert. Da Netzkapazitätsdaten und Wetter-API aktualisiert werden können, kann ein neu erzeugter Snapshot von diesem Stand abweichen.

## Dateien

- `fetch_climate_data.py`: Abruf der Netzknoten- und Klimadaten.
- `substations_climate_base.csv`: zusammengeführter Datensatz für 440 Netzknoten.
- `app_climate_analysis.py`: Streamlit-Anwendung für Filterung, Klassifikation und räumliche Darstellung.

Die Klassifikation und die BESS-Leistungsansätze sind heuristische Screening-Parameter. Sie ersetzen weder eine elektrische Lastflussrechnung noch eine zeitaufgelöste Speicheroptimierung.
