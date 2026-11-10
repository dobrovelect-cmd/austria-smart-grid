import html
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

from screening_logic import calculate_heuristic_mix, count_candidate_strategies

st.set_page_config(page_title="Pre-Screening österreichischer Umspannwerke", layout="wide")


APP_DIR = Path(__file__).resolve().parent
BASE_CSV_FILE = APP_DIR / "substations_climate_base.csv"
DATASET_METADATA_FILE = APP_DIR / "dataset_metadata.json"
st.title("Räumliches Pre-Screening österreichischer Umspannwerke mit veröffentlichter Einspeisekapazität für Wind, PV und BESS")

# Close the floating map card through a lightweight query parameter.
# The map key is refreshed so the same station can be selected again.
if st.query_params.get("close_station") == "1":
    st.session_state["pinned_station_uid"] = None
    st.session_state["substation_map_epoch"] = int(st.session_state.get("substation_map_epoch", 0)) + 1
    del st.query_params["close_station"]


if not BASE_CSV_FILE.exists():
    st.error("❌ Datenbank nicht gefunden! Bitte sicherstellen, dass substations_climate_base.csv im Projektverzeichnis liegt.")
    st.stop()


def normalize_uid(value):
    """Normalize numeric UIDs read from CSV and API without changing the ID."""
    if pd.isna(value):
        return None
    value = str(value).strip()
    if value.endswith(".0"):
        value = value[:-2]
    return value or None


def load_data():
    """Load the committed, validated network and climate snapshot."""
    df = pd.read_csv(BASE_CSV_FILE)
    df["Kontakt"] = df["Kontakt"].fillna("Nicht verfügbar")
    df["Webseite"] = df["Webseite"].fillna("Nicht verfügbar")

    # Traffic-light colours reflect the available capacity in the snapshot.
    def get_base_grid_color(avail):
        if avail <= 5:
            return [220, 20, 60, 180]
        elif avail <= 20:
            return [255, 165, 0, 180]
        return [34, 139, 34, 180]

    df["Farbe_Netz"] = df["Frei_MVA"].apply(get_base_grid_color)
    return df


def format_snapshot_timestamp(metadata):
    value = metadata.get("updated_at", "unbekannt")
    if metadata.get("precision") == "date":
        try:
            return datetime.fromisoformat(value).strftime("%d.%m.%Y")
        except ValueError:
            return value
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%d.%m.%Y, %H:%M")
    except (TypeError, ValueError):
        return value


df = load_data()

# The demo uses the validated, version-controlled snapshot; no live API calls
# are made during startup or while using the dashboard.
try:
    with DATASET_METADATA_FILE.open("r", encoding="utf-8") as metadata_file:
        dataset_metadata = json.load(metadata_file)
except (FileNotFoundError, json.JSONDecodeError, OSError):
    dataset_metadata = {"updated_at": "unbekannt", "source": "Repository-Snapshot"}

st.caption(
    f"Datenstand des Datensatzes: {format_snapshot_timestamp(dataset_metadata)}"
    f" · Quelle: {dataset_metadata.get('source', 'Repository-Snapshot')}"
)

# =====================================================================
# 🎛️ BLOCK 1: BASIS-NETZFILTER
# =====================================================================
all_states = sorted(df["Bundesland"].dropna().unique())
all_operators = sorted(df["Betreiber"].dropna().unique())
min_v, max_v = float(df["Frei_MVA"].min()), float(df["Frei_MVA"].max())

# Region and operator selectors remain in a compact collapsed panel.
with st.sidebar.expander("🎛️ Basis-Netzfilter", expanded=False):
    st.caption("Bundesländer und Netzbetreiber können mehrfach ausgewählt werden.")
    selected_states = st.multiselect(
        "Bundesländer",
        options=all_states,
        default=all_states,
        help="Dropdown öffnen und einzelne Bundesländer an- oder abwählen."
    )
    selected_operators = st.multiselect(
        "Netzbetreiber",
        options=all_operators,
        default=all_operators,
        help="Dropdown öffnen und einzelne Netzbetreiber an- oder abwählen."
    )

# Capacity filter stays visible even when Basis-Netzfilter is collapsed.
st.sidebar.markdown("---")
st.sidebar.markdown("**Verfügbare Netzkapazität (MVA)**")
range_mva = st.sidebar.slider(
    "Bereich der freien Kapazität",
    min_value=min_v,
    max_value=max_v,
    value=(min_v, max_v),
    key="available_capacity_range",
    label_visibility="collapsed",
    help="Filtert nach der aktuell angezeigten freien Netzanschlusskapazität."
)

# =====================================================================
# 🌤️ BLOCK 2: HEURISTISCHE RESSOURCENINDIKATOREN
# =====================================================================
st.sidebar.markdown("---")
with st.sidebar.expander("🌤️ Heuristische Ressourcenanalyse", expanded=True):
    use_climate_analysis = st.checkbox("Heuristische Aufteilung aktivieren", value=True)
    
    st.markdown("**Screening-Schwellenwerte:**")
    target_wind = st.slider(
        "Min. Windgeschwindigkeit auf 100 m (m/s)",
        3.5, 8.5, 4.0, 0.1,
        help=(
            "Wind-Screening: Vergleich des modellierten Jahresmittels der Windgeschwindigkeit "
            "in 100 m mit dem gewählten Schwellenwert. Dies ist keine Berechnung von "
            "Wind-Volllaststunden oder Windstromertrag."
        ),
    )
    target_solar = st.slider(
        "Min. Sonneneinstrahlung (kWh/m²)",
        950, 1350, 950, 25,
        help=(
            "PV-Äquivalentstunden-Proxy: Globalstrahlung / 1 kW/m² × PR 0,85. "
            "Der Faktor 0,85 ist ein vereinfachter Performance-Ratio-Ansatz; "
            "dies ist keine standortspezifische Ertragssimulation."
        ),
    )

# =====================================================================
# 📐 BLOCK 3: 3D-SKALIERUNG
# =====================================================================
st.sidebar.markdown("---")
st.sidebar.header("📐 3D-Visualisierung")
col_radius = st.sidebar.slider("Säulenbreite (m)", 100, 2500, 400, 100)
col_elevation = st.sidebar.slider("Höhenskalierung", 50, 800, 300, 50)


# =====================================================================
# 🧮 HEURISTISCHE EE-AUFTEILUNG & BESS-LEISTUNGSANSATZ
# =====================================================================
f_df = df[
    (df["Bundesland"].isin(selected_states)) &
    (df["Betreiber"].isin(selected_operators)) &
    (df["Frei_MVA"].between(range_mva[0], range_mva[1]))
].copy()


if not f_df.empty:
    res = f_df.apply(
        lambda row: calculate_heuristic_mix(
            row,
            target_wind=target_wind,
            target_solar=target_solar,
            use_climate_analysis=use_climate_analysis,
        ),
        axis=1,
    )
    f_df["Finale_Farbe"] = [item[0] for item in res]
    f_df["Strategie"] = [item[1] for item in res]
    f_df["WEA_Leistung_MVA"] = [item[2] for item in res]
    f_df["PV_Leistung_MVA"] = [item[3] for item in res]
    f_df["Speicher_MVA"] = [item[4] for item in res]
    f_df["VBS_Solar_h"] = [item[5] for item in res]
else:
    # Preserve the schema even when filters remove every row. This keeps the
    # metrics, empty map layer, and table renderable without a KeyError.
    f_df["Finale_Farbe"] = pd.Series(index=f_df.index, dtype="object")
    f_df["Strategie"] = pd.Series(index=f_df.index, dtype="object")
    f_df["WEA_Leistung_MVA"] = pd.Series(index=f_df.index, dtype="float64")
    f_df["PV_Leistung_MVA"] = pd.Series(index=f_df.index, dtype="float64")
    f_df["Speicher_MVA"] = pd.Series(index=f_df.index, dtype="float64")
    f_df["VBS_Solar_h"] = pd.Series(index=f_df.index, dtype="float64")

if use_climate_analysis:
    def get_wind_screening_status(speed):
        if pd.isna(speed):
            return "Keine Klimadaten"
        return "Schwelle erfüllt" if speed >= target_wind else "Unterhalb der Schwelle"

    f_df["Wind_Screening_Status"] = f_df["Wind_ms"].apply(get_wind_screening_status)
    f_df["Wind_Schwelle_ms"] = target_wind


# =====================================================================
# 📊 METRIKEN (DYNAMISCH)
# =====================================================================
col1, col2, col3 = st.columns(3)

if not use_climate_analysis:
    col1.metric("Umspannwerke gesamt", len(f_df))
    col2.metric("Max. freie Kapazität", f"{f_df['Frei_MVA'].max()} MVA" if not f_df.empty else "0 MVA")
    col3.metric("Durchschn. freie Kapazität", f"{round(f_df['Frei_MVA'].mean(), 1)} MVA" if not f_df.empty else "0 MVA")
else:
    counts = count_candidate_strategies(
        f_df["Strategie"] if "Strategie" in f_df.columns else []
    )

    # Colored square markers match the corresponding ColumnLayer colors.
    candidate_metrics = [
        (col1, "🟦 Wind+BESS-Kandidaten", counts.get("Windpark + BESS (heuristisch)", 0)),
        (col2, "🟨 PV+BESS-Kandidaten", counts.get("PV-Anlage + BESS (heuristisch)", 0)),
        (col3, "🟪 Hybride Kandidaten", counts.get("Hybrides Wind-PV-System + BESS (heuristisch)", 0)),
    ]
    for metric_col, label, count in candidate_metrics:
        metric_col.metric(label=label, value=count)
    no_capacity_count = int((f_df["Frei_MVA"] <= 0).sum())
    st.caption(
        f"{no_capacity_count} gefilterte Netzknoten ohne ausgewiesene freie Anschlusskapazität "
        "werden nicht als Anschlusskandidaten gezählt."
    )

# =====================================================================
# 🎯 TOOLTIP FÜR SCREENING-INDIKATOREN
# =====================================================================
if not use_climate_analysis:
    tooltip_html = """
        <div style='font-family:Arial,sans-serif; box-sizing:border-box; width:340px; max-width:100%;
                    padding:10px; font-size:13.5px; line-height:1.4; overflow-wrap:anywhere;'>
            <b style='font-size:16px; color:#2c3e50;'>{Name}</b>
            <hr style='margin:6px 0; border:0; border-top:1px solid #ccc;'/>
            <b>Freie Netzkapazität:</b> <span style='color:#27ae60; font-weight:bold;'>{Frei_MVA} MVA</span><br/>
            <b>Gebuchte Kapazität:</b> {Belegt_MVA} MVA<br/>
            <b>Netzbetreiber:</b> {Betreiber}<br/>
            <b>Bundesland:</b> {Bundesland}<br/>
            <b>Kontakt:</b> {Kontakt}<br/>
            <b>Webseite:</b> <a href='{Webseite}' target='_blank' style='overflow-wrap:anywhere;'>{Webseite}</a>
        </div>
    """
else:
    tooltip_html = """
        <div style='font-family:Arial,sans-serif; box-sizing:border-box; width:360px; max-width:100%;
                    padding:10px; font-size:13.5px; line-height:1.4; overflow-wrap:anywhere;'>
            <b style='font-size:16px; color:#2c3e50;'>{Name}</b>
            <div style='margin:6px 0 8px; padding:8px; background:#f3f5f7; border-left:4px solid #8e44ad; border-radius:4px;'>
                <div style='font-size:11px; color:#6b7280; text-transform:uppercase; letter-spacing:.3px;'>Empfohlenes Einspeisekonzept</div>
                <b style='font-size:15px; color:#2c3e50;'>{Strategie}</b>
                <div style='margin-top:6px;'>🌬️ <b>Wind:</b> <span style='font-size:16px; font-weight:700;'>{WEA_Leistung_MVA} MVA</span></div>
                <div>☀️ <b>PV:</b> <span style='font-size:16px; font-weight:700;'>{PV_Leistung_MVA} MVA</span></div>
                <div>🔋 <b>BESS:</b> <span style='font-size:16px; font-weight:700;'>{Speicher_MVA} MVA</span></div>
            </div>
            <b>Freie Netzkapazität:</b> <span style='color:#27ae60; font-weight:bold;'>{Frei_MVA} MVA</span><br/>
            <b>Gebuchte Kapazität:</b> {Belegt_MVA} MVA<br/>
            <b>Netzbetreiber:</b> {Betreiber} · {Bundesland}<br/>
            <hr style='margin:6px 0; border:0; border-top:1px solid #eee;'/>
            🌬️ <b>Wind-Jahresmittel (2024, 100 m):</b> {Wind_ms} m/s<br/>
            <b>Wind-Schwelle:</b> {Wind_Schwelle_ms} m/s · {Wind_Screening_Status}<br/>
            ☀️ <b>Globalstrahlung:</b> {Solar_kWh} kWh/m²<br/>
            <hr style='margin:6px 0; border:0; border-top:1px solid #eee;'/>
            <b>Kontakt:</b> {Kontakt}<br/>
            <b>Webseite:</b> <a href='{Webseite}' target='_blank' style='overflow-wrap:anywhere;'>{Webseite}</a><br/>
            <span style='font-size:11px; color:#59636e;'>Wind-, PV- und BESS-Leistungsansätze sind heuristische Screening-Werte, keine Ertrags- oder Lastflussberechnung.</span>
        </div>
    """

# --- PYDECK MAP ---
view = pdk.ViewState(latitude=47.6, longitude=13.8, zoom=7, pitch=45)

layer = pdk.Layer(
    "ColumnLayer",
    data=f_df,
    id="substation-columns",
    get_position="[Länge, Breite]",
    get_elevation="Frei_MVA",
    elevation_scale=col_elevation,
    radius=col_radius,
    get_fill_color="Finale_Farbe" if not f_df.empty else [0, 0, 0, 0],
    pickable=True,
    auto_highlight=True,
)

map_epoch = st.session_state.get("substation_map_epoch", 0)
map_event = st.pydeck_chart(
    pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={
            "html": tooltip_html,
            "style": {
                "backgroundColor": "white",
                "color": "black",
                "borderRadius": "6px",
                "boxShadow": "0px 2px 10px rgba(0,0,0,0.15)",
                "maxWidth": "380px",
                "maxHeight": "65vh",
                "overflowY": "auto",
                "overflowX": "hidden",
                "fontSize": "13.5px",
                "lineHeight": "1.4",
                "padding": "10px",
                "boxSizing": "border-box",
            },
        },
    ),
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-object",
    key=f"substation-map-{map_epoch}",
)

# A click pins the same station information as a floating card over the map.
# Unlike the hover tooltip, this card remains visible after the pointer leaves the column.
selected_objects = (
    map_event.selection.get("objects", {}).get("substation-columns", [])
    if map_event is not None
    else []
)
if selected_objects:
    clicked_uid = normalize_uid(selected_objects[0].get("UID"))
    if clicked_uid:
        st.session_state["pinned_station_uid"] = clicked_uid

pinned_uid = st.session_state.get("pinned_station_uid")
if pinned_uid:
    pinned_matches = f_df[f_df["UID"].map(normalize_uid) == pinned_uid]
    if not pinned_matches.empty:
        station = pinned_matches.iloc[0]

        def display_number(value, decimals=1):
            try:
                return f"{float(value):.{decimals}f}" if pd.notna(value) else "—"
            except (TypeError, ValueError):
                return "—"

        strategy_labels = {
            "Hybrides Wind-PV-System + BESS (heuristisch)": "Wind + PV + BESS",
            "PV-Anlage + BESS (heuristisch)": "PV + BESS",
            "Windpark + BESS (heuristisch)": "Wind + BESS",
            "Geringes Potenzial": "Geringes Potenzial",
        }
        strategy_colors = {
            "Hybrides Wind-PV-System + BESS (heuristisch)": "#9B59B6",
            "PV-Anlage + BESS (heuristisch)": "#F1C40F",
            "Windpark + BESS (heuristisch)": "#2980B9",
            "Geringes Potenzial": "#BDC3C7",
        }

        station_name = html.escape(str(station.get("Name", "Netzknoten")))
        station_operator = html.escape(str(station.get("Betreiber", "—")))
        station_state = html.escape(str(station.get("Bundesland", "—")))
        strategy = str(station.get("Strategie", "Basis-Netzmodus"))
        strategy_label = html.escape(strategy_labels.get(strategy, strategy))
        strategy_color = strategy_colors.get(strategy, "#6B7280")
        free_capacity = display_number(station.get("Frei_MVA"))
        booked_capacity = display_number(station.get("Belegt_MVA"))
        contact = html.escape(str(station.get("Kontakt", "Nicht verfügbar")))
        website = str(station.get("Webseite", "Nicht verfügbar")).strip()
        if website and website != "Nicht verfügbar":
            website_html = (
                f'<a href="{html.escape(website, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer" style="overflow-wrap:anywhere;">'
                f'{html.escape(website)}</a>'
            )
        else:
            website_html = "Nicht verfügbar"

        recommendation_html = ""
        climate_html = ""
        if use_climate_analysis:
            recommendation_html = f"""
                <div style="margin:8px 0 9px;padding:9px;background:#f3f5f7;
                            border-left:4px solid {strategy_color};border-radius:5px;">
                    <div style="font-size:10px;color:#6b7280;text-transform:uppercase;
                                letter-spacing:.35px;margin-bottom:3px;">
                        Empfohlenes Einspeisekonzept
                    </div>
                    <div style="font-size:16px;font-weight:700;color:#263445;margin-bottom:7px;">
                        {strategy_label}
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;">
                        <div style="min-width:0;">🌬️ <b>Wind</b><br/>
                            <span style="font-size:16px;font-weight:700;">{display_number(station.get("WEA_Leistung_MVA"))} MVA</span></div>
                        <div style="min-width:0;">☀️ <b>PV</b><br/>
                            <span style="font-size:16px;font-weight:700;">{display_number(station.get("PV_Leistung_MVA"))} MVA</span></div>
                        <div style="min-width:0;">🔋 <b>BESS</b><br/>
                            <span style="font-size:16px;font-weight:700;">{display_number(station.get("Speicher_MVA"))} MVA</span></div>
                    </div>
                </div>
            """
            climate_html = f"""
                <hr style="margin:7px 0;border:0;border-top:1px solid #e5e7eb;"/>
                🌬️ <b>Wind-Jahresmittel (2024, 100 m):</b> {display_number(station.get("Wind_ms"), 2)} m/s<br/>
                <b>Wind-Schwelle:</b> {display_number(station.get("Wind_Schwelle_ms"))} m/s ·
                {html.escape(str(station.get("Wind_Screening_Status", "—")))}<br/>
                ☀️ <b>Globalstrahlung:</b> {display_number(station.get("Solar_kWh"))} kWh/m²<br/>
            """

        pinned_panel_html = f"""
            <div style="position:fixed;top:clamp(210px,29vh,290px);right:24px;
                        z-index:999999;width:360px;max-width:calc(100vw - 32px);
                        max-height:62vh;overflow-y:auto;overflow-x:hidden;
                        box-sizing:border-box;padding:12px 13px 11px;
                        background:#ffffff;color:#202733;border:1px solid #d5dbe3;
                        border-left:4px solid {strategy_color};border-radius:9px;
                        box-shadow:0 8px 28px rgba(15,23,42,.24);
                        font-family:Arial,sans-serif;font-size:13px;line-height:1.42;
                        overflow-wrap:anywhere;">
                <a href="?close_station=1" title="Fenster schließen"
                   style="position:absolute;right:10px;top:7px;text-decoration:none;
                          color:#59636e;font-size:21px;font-weight:500;line-height:1;">
                    ×
                </a>
                <div style="padding-right:24px;font-size:17px;font-weight:700;color:#263445;">
                    📍 {station_name}
                </div>
                <div style="font-size:11px;color:#6b7280;margin-top:2px;">
                    {station_operator} · {station_state} · UID {html.escape(str(pinned_uid))}
                </div>
                {recommendation_html}
                <b>Freie Netzkapazität:</b>
                <span style="color:#218c50;font-weight:700;">{free_capacity} MVA</span><br/>
                <b>Gebuchte Kapazität:</b> {booked_capacity} MVA
                {climate_html}
                <hr style="margin:7px 0;border:0;border-top:1px solid #e5e7eb;"/>
                <b>Kontakt:</b> {contact}<br/>
                <b>Webseite:</b> {website_html}
                <div style="font-size:10px;color:#697586;margin-top:7px;line-height:1.3;">
                    Wind-, PV- und BESS-Leistungsansätze sind heuristische Screening-Werte,
                    keine Ertrags- oder Lastflussberechnung.
                </div>
            </div>
        """
        # Render as raw HTML in the app DOM. st.markdown would parse nested
        # indented HTML fragments as Markdown code blocks in this panel.
        st.html(pinned_panel_html)
    else:
        # The selected point may have been removed by a filter change.
        st.session_state["pinned_station_uid"] = None


# --- TECHNISCHES ANLAGENREGISTER ---
st.markdown("### 📋 Technisches Anlagenregister")

if not f_df.empty:
    main_columns = [
        "UID",
        "Name",
        "Bundesland",
        "Betreiber",
        "Frei_MVA",
        "Belegt_MVA",
        "Solar_kWh",
    ]
    if use_climate_analysis:
        main_columns += [
            "Wind_ms",
            "Wind_Screening_Status",
            "Strategie",
        ]

    main_df = f_df[main_columns].copy()
    if use_climate_analysis:
        main_df["Strategie"] = main_df["Strategie"].replace({
            "Hybrides Wind-PV-System + BESS (heuristisch)": "Wind + PV + BESS",
            "PV-Anlage + BESS (heuristisch)": "PV + BESS",
            "Windpark + BESS (heuristisch)": "Wind + BESS",
            "Geringes Potenzial": "Geringes Potenzial",
        })

    main_df = main_df.rename(columns={
        "Name": "Netzknoten",
        "Betreiber": "Netzbetreiber",
        "Frei_MVA": "Frei (MVA)",
        "Belegt_MVA": "Belegt (MVA)",
        "Wind_ms": "Wind @100 m (m/s)",
        "Wind_Screening_Status": "Wind-Screening",
        "Solar_kWh": "Globalstrahlung (kWh/m²)",
    })

    st.dataframe(
        main_df,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Keine Umspannwerke entsprechen den gewählten Filterkriterien.")
