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

- Bei unvollständigen oder fehlerhaft formatierten Open-Meteo-JSON-Antworten wird der betreffende Standort-Batch erneut abgefragt und bei Bedarf rekursiv in kleinere Teil-Batches zerlegt. Der CSV-Snapshot wird erst nach erfolgreicher Verarbeitung aller gültigen Netzknoten ersetzt.

Der aktuelle CSV-Snapshot wurde am 3. November 2026 vollständig neu erzeugt. Dabei wurden die Netzknotendaten erneut von EbUtilities und die stündlichen Klimadaten für 2024 von Open-Meteo abgerufen. Die Windgeschwindigkeit wurde von der API explizit in m/s angefordert; der Collector prüft die zurückgemeldete Einheit. Der Snapshot umfasst 443 Netzknoten mit eindeutigen UIDs. Kennwerte dieses Snapshots: mittlere Windgeschwindigkeit 3,84 m/s (1,36–6,81 m/s), mittlere jährliche Globalstrahlung 1.309,5 kWh/m², 252 Netzknoten mit positiver freier Einspeisekapazität und 191 Netzknoten ohne ausgewiesene freie Kapazität.

## Dateien

- `fetch_climate_data.py`: Abruf der Netzknoten- und Klimadaten.
- `substations_climate_base.csv`: am 3. November 2026 aktualisierter Datensatz für 443 Netzknoten.
- `app_climate_analysis.py`: Streamlit-Anwendung für Filterung, Klassifikation und räumliche Darstellung.

Die Klassifikation und die BESS-Leistungsansätze sind heuristische Screening-Parameter. Sie ersetzen weder eine elektrische Lastflussrechnung noch eine zeitaufgelöste Speicheroptimierung.


## Interaktive Web-Demonstration

Die Streamlit-Anwendung kann über Streamlit Community Cloud öffentlich bereitgestellt werden:

1. Bei [Streamlit Community Cloud](https://share.streamlit.io/) mit GitHub anmelden und den GitHub-Zugriff autorisieren.
2. **Create app** auswählen.
3. Repository: `dobrovelect-cmd/austria-smart-grid`; Branch: `main`; App file path: `app_climate_analysis.py`.
4. Unter **Advanced settings** Python **3.11** auswählen, damit die Laufzeit zur GitHub-Actions-Umgebung passt.
5. **Deploy** wählen. Streamlit erstellt eine öffentliche `*.streamlit.app`-URL, die anschließend in Publikationen und Präsentationen verlinkt werden kann.

Die Anwendung verwendet den im Repository gespeicherten CSV-Snapshot. Sie ruft beim Öffnen der Web-Demo nicht selbstständig alle Wetterdaten erneut ab. Die vollständige Datenaktualisierung erfolgt separat über den GitHub-Actions-Workflow **Refresh network and climate dataset**.

## Vollständige Aktualisierung des Datensatzes

Der vollständige Abruf kann bei Bedarf manuell über GitHub Actions gestartet werden:

1. Repository öffnen und den Tab **Actions** auswählen.
2. Den Workflow **Refresh network and climate dataset** öffnen.
3. **Run workflow** auswählen und den gewünschten Branch angeben.
4. Der Workflow lädt die Netzknotendaten neu, fragt die historischen Wetterdaten für alle gültigen Koordinaten paketweise ab, prüft den vollständigen Datensatz und committet die aktualisierte CSV auf den ausgewählten Branch.

Der Workflow verwendet für Windgeschwindigkeit explizit m/s. Bei Fehlern oder unvollständigen Wetterantworten wird der bisherige CSV-Snapshot nicht überschrieben. Der Workflow schreibt die aktualisierte CSV nach erfolgreicher Validierung auf den ausgewählten Branch. Der zuletzt erfolgreich aktualisierte Snapshot liegt auf `main`.
