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
- Der PV-Vollbenutzungsstunden-Proxy in der App wird als `Solar_kWh / 1 kW/m² × 0,85` berechnet. Der Faktor 0,85 ist ein vereinfachter Performance-Ratio-Ansatz; die Rechnung ist kein PV-Ertragsmodell für eine konkrete Modulfläche, Neigung oder Anlagenkonfiguration.
- Die Kategorien und BESS-Leistungswerte sind heuristische Screening-Ausgaben. Die App führt weder Lastfluss- noch Dispatch- oder Kostenoptimierung durch.
- Die Wetterwerte stammen aus räumlichen Reanalyse-/Modellgitterzellen und sind keine standortspezifischen Messungen oder Ertragsprognosen.

Das bestehende CSV-Snapshot wurde korrigiert: Die zuvor mit der Open-Meteo-Standardkonfiguration gespeicherten Windwerte in km/h wurden durch 3,6 geteilt und in m/s umgerechnet. Bei einer erneuten Ausführung von `fetch_climate_data.py` werden die Klimadaten direkt in m/s angefordert. Da Netzkapazitätsdaten und Wetter-API aktualisiert werden können, kann ein neu erzeugter Snapshot von diesem Stand abweichen.

## Dateien

- `fetch_climate_data.py`: Abruf der Netzknoten- und Klimadaten.
- `substations_climate_base.csv`: zusammengeführter Datensatz für 440 Netzknoten.
- `app_climate_analysis.py`: Streamlit-Anwendung für Filterung, Klassifikation und räumliche Darstellung.

Die Klassifikation und die BESS-Leistungsansätze sind heuristische Screening-Parameter. Sie ersetzen weder eine elektrische Lastflussrechnung noch eine zeitaufgelöste Speicheroptimierung.

## Vollständige Aktualisierung des Datensatzes

Nach dem Zusammenführen des Pull Requests kann der vollständige Abruf über GitHub Actions gestartet werden:

1. Repository öffnen und den Tab **Actions** auswählen.
2. Den Workflow **Refresh network and climate dataset** öffnen.
3. **Run workflow** auswählen und den gewünschten Branch angeben.
4. Der Workflow lädt die Netzknotendaten neu, fragt die historischen Wetterdaten für alle gültigen Koordinaten paketweise ab, prüft den vollständigen Datensatz und committet die aktualisierte CSV auf den ausgewählten Branch.

Der Workflow verwendet für Windgeschwindigkeit explizit m/s. Bei Fehlern oder unvollständigen Wetterantworten wird der bisherige CSV-Snapshot nicht überschrieben. Der Workflow kann manuell gestartet werden; es erfolgt keine automatische Änderung von `main` ohne einen manuellen Workflow-Start auf diesem Branch.
