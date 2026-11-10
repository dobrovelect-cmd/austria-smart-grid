# SMART Grid Austria & Speicher AI

Räumliches Pre-Screening österreichischer Umspannwerke mit veröffentlichter Einspeisekapazität für Windenergie, Photovoltaik und Batteriespeicher (BESS).

**Hinweis zur Spannungsebene:** Die EbUtilities-Datenquelle veröffentlicht verfügbare und gebuchte Einspeisekapazitäten je Umspannwerk, stellt in dem von diesem Projekt verwendeten Datensatz jedoch kein eigenes Feld zur Spannungsebene bereit. Einige Stationsnamen enthalten explizite Angaben wie 6, 10, 20, 25 oder 30 kV. Daher wird die Gesamtheit der Datensätze nicht pauschal als ausschließlich hochspannungsseitig klassifiziert. Eine belastbare Filterung nach Spannungsebene erfordert ein zusätzliches, stationsbezogenes Spannungsattribut.

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
docker run --rm --name austria-smart-grid -p 8501:8501 austria-smart-grid:latest
```

Der Build prüft beim Erstellen zusätzlich, ob NumPy, pandas, PyArrow und Streamlit gemeinsam importiert werden können. Die Versionen von NumPy und PyArrow sind festgelegt, damit die Streamlit-Tabelle nicht durch eine inkompatible Arrow-Version ausfällt.

Der Container nutzt den versionierten CSV-Snapshot direkt aus dem Image. Für die Demonstration ist kein zusätzliches Docker-Volume erforderlich.

Anschließend die Anwendung im Browser öffnen:

**http://localhost:8501**

Zum Beenden im Terminal, in dem der Container läuft, **Ctrl+C** drücken.

Der Container verwendet den im Repository gespeicherten CSV-Datensatz `substations_climate_base.csv`. Beim normalen Start werden keine Klima- oder Netzdaten aus externen APIs abgerufen.

### Datenstand der Demonstration

Das Dashboard verwendet einen versionierten CSV-Snapshot mit Netzkapazitäten von EbUtilities und Klimakennwerten von Open-Meteo für das Jahr 2024. Beim Öffnen der App werden keine externen APIs aufgerufen. Die Kapazitätswerte bleiben während der Demonstration unverändert; dadurch ist das Verhalten reproduzierbar und unabhängig von der aktuellen Verfügbarkeit der API.

Der Snapshot kann durch den Maintainer separat über den GitHub-Actions-Workflow „Refresh network and climate dataset“ neu erzeugt werden. Der Workflow ist derzeit ausschließlich manuell startbar; ein täglicher, wöchentlicher oder monatlicher Zeitplan ist nicht eingerichtet. Nach erfolgreichem Lauf werden CSV und Metadaten auf den ausgewählten Branch committet. Bei einer Bereitstellung aus `main` übernimmt Streamlit Community Cloud den neuen Repository-Stand anschließend beim nächsten App-Deployment.

### Technisches Anlagenregister

Die Tabelle zeigt in einer einzigen Ansicht UID, Netzknoten, Bundesland, Netzbetreiber, freie und gebuchte Kapazität sowie Globalstrahlung und – bei aktivierter heuristischer Ressourcenanalyse – Wind-Screening und Strategie. Es gibt keinen separaten aufklappbaren Detailbereich.

### Interaktion mit der Karte

Beim Überfahren eines Netzknotens erscheint weiterhin die Hover-Information. Ein Klick fixiert dieselbe Stationsinformation als schwebendes HTML-Fenster direkt über dem Kartenfeld; es bleibt beim Bewegen des Mauszeigers sichtbar und wird über **×** geschlossen. Die Karte rendert das Fenster direkt im App-Dokument, nicht als Markdown-Code. Es wird kein zusätzliches Detailfeld unterhalb der Karte erzeugt. Im Fenster steht zuerst das heuristische Einspeisekonzept mit den Leistungsansätzen für 🌬️ Wind, ☀️ PV und 🔋 BESS. Die drei Kandidaten-Kennzahlen oberhalb der Karte zeigen farbige Quadrate passend zu den Säulen: 🟦 Blau für Wind+BESS, 🟨 Gelb für PV+BESS und 🟪 Violett für Wind+PV+BESS.

Für die Klickauswahl der PyDeck-Karte wird Streamlit 1.40.0 oder neuer benötigt; im Projekt ist Streamlit 1.40.0 festgesetzt.

### Aktualisierung des lokalen Datenstands

Die vollständige Aktualisierung des Datensatzes erfolgt separat über GitHub Actions (siehe Abschnitt „Vollständige Aktualisierung des Datensatzes“ weiter unten).

Wenn ein neuer CSV-Snapshot auf GitHub veröffentlicht wurde, kann der lokale Stand aktualisiert und das Docker-Image neu erstellt werden:

```bash
git pull
docker build --no-cache -t austria-smart-grid:latest .
docker run --rm --name austria-smart-grid -p 8501:8501 austria-smart-grid:latest
```

`--no-cache` stellt sicher, dass geänderte Python-Abhängigkeiten neu installiert werden. Der neue Container liest den aktualisierten CSV-Snapshot aus dem Image.

## Klimadaten und Einheiten

Die Klimakennwerte beziehen sich auf das Kalenderjahr 2024 und werden über die Open-Meteo Historical Weather API abgefragt.

- `Wind_ms`: arithmetischer Mittelwert der stündlichen Variable `wind_speed_100m` in **m/s**. Der API-Aufruf setzt `wind_speed_unit=ms` ausdrücklich und prüft die zurückgemeldete Einheit.
- **Wind-Screening in der App:** Das modellierte Jahresmittel `Wind_ms` in 100 m Höhe wird mit dem vom Nutzer gewählten Schwellenwert verglichen. Die App zeigt den Modellwert, den Schwellenwert und den Status (`Schwelle erfüllt` bzw. `Unterhalb der Schwelle`) getrennt an. Ein unterschrittener Schwellenwert bedeutet lediglich, dass die heuristische Screening-Aufteilung diesem Netzknoten keinen Wind-Leistungsanteil zuweist. Er bedeutet **nicht**, dass kein Wind vorhanden ist oder dass die tatsächliche Windstromerzeugung null wäre.
- Es werden **keine Wind-Volllaststunden und kein Windenergieertrag** berechnet: Es wird weder eine stündliche Turbinen-Leistungskennlinie noch ein konkretes Anlagenmodell verwendet. Der interne dimensionslose Wind-Gewichtungswert dient ausschließlich der heuristischen Aufteilung der verfügbaren Anschlusskapazität zwischen Wind und PV.
- `Solar_kWh`: jährliche Summe der stündlichen Mittelwerte von `shortwave_radiation`, geteilt durch 1000. Die resultierende Einheit ist **kWh/m²** (globale kurzwellige Einstrahlung auf eine horizontale Fläche), nicht die elektrische PV-Erzeugung.
- Der PV-Vollbenutzungsstunden-Proxy in der App wird als `Solar_kWh / 1 kW/m² × 0,85` berechnet. Der Faktor 0,85 ist ein vereinfachter Performance-Ratio-Ansatz; die Rechnung ist kein PV-Ertragsmodell für eine konkrete Modulfläche, Neigung oder Anlagenkonfiguration.
- Die Kategorien und BESS-Leistungswerte sind heuristische Screening-Ausgaben. Die App führt weder Lastfluss- noch Dispatch- oder Kostenoptimierung durch.
- Netzknoten ohne ausgewiesene freie Einspeisekapazität (`Frei_MVA ≤ 0`) werden nicht als Anschlusskandidaten gezählt. Die Kandidatenzahlen beziehen sich nur auf die aktuell gefilterten Netzknoten mit positiver freier Kapazität.
- Die Wind-Gewichtung ist ein frei definierter Screening-Score und keine physikalische Energiekennzahl. Sie wird zusammen mit dem PV-Äquivalentstunden-Proxy ausschließlich zur heuristischen Aufteilung der verfügbaren Anschlusskapazität verwendet.
- Die Wetterwerte stammen aus räumlichen Reanalyse-/Modellgitterzellen und sind keine standortspezifischen Messungen oder Ertragsprognosen.
- Bei unvollständigen oder fehlerhaft formatierten Open-Meteo-JSON-Antworten wird der betreffende Standort-Batch erneut abgefragt und bei Bedarf rekursiv in kleinere Teil-Batches zerlegt. Der CSV-Snapshot wird erst nach erfolgreicher Verarbeitung aller gültigen Netzknoten ersetzt.

Der im Repository enthaltene CSV-Snapshot wurde am 3. November 2026 vollständig neu erzeugt. Dabei wurden die Netzknotendaten erneut von EbUtilities und die stündlichen Klimadaten für 2024 von Open-Meteo abgerufen. Die Windgeschwindigkeit wurde von der API explizit in m/s angefordert; der Collector prüft die zurückgemeldete Einheit. Der Snapshot umfasst 443 Netzknoten mit eindeutigen UIDs. Kennwerte dieses Snapshots: mittlere Windgeschwindigkeit 3,84 m/s (1,36–6,81 m/s), mittlere jährliche Globalstrahlung 1.309,5 kWh/m², 252 Netzknoten mit positiver freier Einspeisekapazität und 191 Netzknoten ohne ausgewiesene freie Kapazität.

## Dateien

- `fetch_climate_data.py`: Abruf und Aktualisierung der Netzknoten- und Klimadaten.
- `substations_climate_base.csv`: am 3. November 2026 aktualisierter Datensatz für 443 Netzknoten.
- `dataset_metadata.json`: Zeitstempel und Quelle des im Repository enthaltenen Netzkapazitäts-/Klimadaten-Snapshots.
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
