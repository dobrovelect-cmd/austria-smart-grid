# SMART Grid Austria & Speicher AI

Intelligentes Monitoring-Tool zur räumlichen Vorauswahl österreichischer Netzknoten für Windenergie, Photovoltaik und Batteriespeicher (BESS).

## Lokaler Start mit Docker (empfohlen)

Die Anwendung läuft lokal auf dem Computer des Anwenders in einem Docker-Container. Python und die benötigten Bibliotheken müssen nicht separat installiert werden.

### Voraussetzungen

- Git
- Docker Desktop (Windows/macOS) oder Docker Engine (Linux)

Docker muss vor dem Start ausgeführt werden.

### Installation und Start

Repository klonen und in das Projektverzeichnis wechseln:

```bash
git clone https://github.com/dobrovelect-cmd/austria-smart-grid.git
cd austria-smart-grid
```

Docker-Image erstellen:

```bash
docker build --no-cache -t austria-smart-grid:latest .
```

Container starten:

```bash
docker run --rm --name austria-smart-grid -p 8501:8501 -v austria-smart-grid-data:/app/data austria-smart-grid:latest
```

Der Build prüft beim Erstellen zusätzlich, ob NumPy, pandas, PyArrow und Streamlit gemeinsam importiert werden können. Die Versionen von NumPy und PyArrow sind festgelegt, damit die Streamlit-Tabelle nicht durch eine inkompatible Arrow-Version ausfällt.

Das benannte Docker-Volume `austria-smart-grid-data` speichert aktualisierte Netzkapazitäten dauerhaft. Es enthält nur den Kapazitäts-Override und den Zeitstempel; der Klima-CSV-Snapshot bleibt im Image und kann unabhängig davon aktualisiert werden.

Anschließend die Anwendung im Browser öffnen:

**http://localhost:8501**

Zum Beenden im Terminal, in dem der Container läuft, **Ctrl+C** drücken.

Der Container verwendet den im Repository gespeicherten CSV-Datensatz `substations_climate_base.csv`. Beim normalen Start werden keine Klima- oder Netzdaten aus externen APIs abgerufen.

### Netzkapazitäten bei Bedarf aktualisieren

Im Dashboard befindet sich neben dem angezeigten Datenstand die Schaltfläche **„Netzkapazitäten aktualisieren“**. Sie ruft die aktuelle Netzknotenliste von EbUtilities ab und aktualisiert anhand der eindeutigen UID ausschließlich:

- `Frei_MVA`: verfügbare Einspeisekapazität;
- `Belegt_MVA`: gebuchte bzw. reservierte Kapazität.

Die Aktualisierung wird nur gespeichert, wenn für alle Netzknoten des lokalen CSV-Snapshots passende API-Datensätze und gültige Werte für die freie Kapazität vorliegen. Bei einer unvollständigen API-Antwort bleiben die bisherigen Werte erhalten. Zusätzliche API-Knoten ohne passenden Klima-Datensatz werden nicht automatisch in die Karte aufgenommen.

Der erfolgreiche Aktualisierungszeitpunkt wird in österreichischer Lokalzeit angezeigt und im Docker-Volume gespeichert. Wind- und Solardaten werden durch diese Schaltfläche nicht verändert. Sie bleiben Teil des separaten Klima-Snapshots.

### Aktualisierung des lokalen Datenstands

Die vollständige Aktualisierung des Datensatzes erfolgt separat über GitHub Actions (siehe Abschnitt „Vollständige Aktualisierung des Datensatzes“ weiter unten).

Wenn ein neuer CSV-Snapshot auf GitHub veröffentlicht wurde, kann der lokale Stand aktualisiert und das Docker-Image neu erstellt werden:

```bash
git pull
docker build --no-cache -t austria-smart-grid:latest .
```

`--no-cache` stellt sicher, dass geänderte Python-Abhängigkeiten neu installiert werden.

Danach den Container wie oben beschrieben erneut starten.

## Klimadaten und Einheiten

Die Klimakennwerte beziehen sich auf das Kalenderjahr 2024 und werden über die Open-Meteo Historical Weather API abgefragt.

- `Wind_ms`: arithmetischer Mittelwert der stündlichen Variable `wind_speed_100m` in **m/s**. Der API-Aufruf setzt `wind_speed_unit=ms` ausdrücklich und prüft die zurückgemeldete Einheit.
- **Wind-Screening in der App:** Das modellierte Jahresmittel `Wind_ms` in 100 m Höhe wird mit dem vom Nutzer gewählten Schwellenwert verglichen. Die App zeigt den Modellwert, den Schwellenwert und den Status (`Schwelle erfüllt` bzw. `Unterhalb der Schwelle`) getrennt an. Ein unterschrittener Schwellenwert bedeutet lediglich, dass die heuristische Screening-Aufteilung diesem Netzknoten keinen Wind-Leistungsanteil zuweist. Er bedeutet **nicht**, dass kein Wind vorhanden ist oder dass die tatsächliche Windstromerzeugung null wäre.
- Es werden **keine Wind-Volllaststunden und kein Windenergieertrag** berechnet: Es wird weder eine stündliche Turbinen-Leistungskennlinie noch ein konkretes Anlagenmodell verwendet. Der interne dimensionslose Wind-Gewichtungswert dient ausschließlich der heuristischen Aufteilung der verfügbaren Anschlusskapazität zwischen Wind und PV.
- `Solar_kWh`: jährliche Summe der stündlichen Mittelwerte von `shortwave_radiation`, geteilt durch 1000. Die resultierende Einheit ist **kWh/m²** (globale kurzwellige Einstrahlung auf eine horizontale Fläche), nicht die elektrische PV-Erzeugung.
- Der PV-Vollbenutzungsstunden-Proxy in der App wird als `Solar_kWh / 1 kW/m² × 0,85` berechnet. Der Faktor 0,85 ist ein vereinfachter Performance-Ratio-Ansatz; die Rechnung ist kein PV-Ertragsmodell für eine konkrete Modulfläche, Neigung oder Anlagenkonfiguration.
- Die Kategorien und BESS-Leistungswerte sind heuristische Screening-Ausgaben. Die App führt weder Lastfluss- noch Dispatch- oder Kostenoptimierung durch.
- Die Wetterwerte stammen aus räumlichen Reanalyse-/Modellgitterzellen und sind keine standortspezifischen Messungen oder Ertragsprognosen.
- Bei unvollständigen oder fehlerhaft formatierten Open-Meteo-JSON-Antworten wird der betreffende Standort-Batch erneut abgefragt und bei Bedarf rekursiv in kleinere Teil-Batches zerlegt. Der CSV-Snapshot wird erst nach erfolgreicher Verarbeitung aller gültigen Netzknoten ersetzt.

Der aktuelle CSV-Snapshot wurde am 3. November 2026 vollständig neu erzeugt. Dabei wurden die Netzknotendaten erneut von EbUtilities und die stündlichen Klimadaten für 2024 von Open-Meteo abgerufen. Die Windgeschwindigkeit wurde von der API explizit in m/s angefordert; der Collector prüft die zurückgemeldete Einheit. Der Snapshot umfasst 443 Netzknoten mit eindeutigen UIDs. Kennwerte dieses Snapshots: mittlere Windgeschwindigkeit 3,84 m/s (1,36–6,81 m/s), mittlere jährliche Globalstrahlung 1.309,5 kWh/m², 252 Netzknoten mit positiver freier Einspeisekapazität und 191 Netzknoten ohne ausgewiesene freie Kapazität.

## Dateien

- `fetch_climate_data.py`: Abruf und Aktualisierung der Netzknoten- und Klimadaten.
- `substations_climate_base.csv`: am 3. November 2026 aktualisierter Datensatz für 443 Netzknoten.
- `app_climate_analysis.py`: Streamlit-Anwendung für Filterung, Klassifikation und räumliche Darstellung.
- `Dockerfile`: reproduzierbare lokale Ausführungsumgebung für das Dashboard.

Die Klassifikation und die BESS-Leistungsansätze sind heuristische Screening-Parameter. Sie ersetzen weder eine elektrische Lastflussrechnung noch eine zeitaufgelöste Speicheroptimierung.

## Vollständige Aktualisierung des Datensatzes

Der vollständige Abruf kann bei Bedarf manuell über GitHub Actions gestartet werden:

1. Repository öffnen und den Tab **Actions** auswählen.
2. Den Workflow **Refresh network and climate dataset** öffnen.
3. **Run workflow** auswählen und den gewünschten Branch angeben.
4. Der Workflow lädt die Netzknotendaten neu, fragt die historischen Wetterdaten für alle gültigen Koordinaten paketweise ab, prüft den vollständigen Datensatz und committet die aktualisierte CSV auf den ausgewählten Branch.

Der Workflow verwendet für Windgeschwindigkeit explizit m/s. Bei Fehlern oder unvollständigen Wetterantworten wird der bisherige CSV-Snapshot nicht überschrieben. Der Workflow schreibt die aktualisierte CSV nach erfolgreicher Validierung auf den ausgewählten Branch. Der zuletzt erfolgreich aktualisierte Snapshot liegt auf `main`.
