import streamlit as st
import pandas as pd
import pydeck as pdk
import os

st.set_page_config(page_title="SMART Grid Austria & Speicher AI", layout="wide")

st.title("⚡ Monitoring des österreichischen Stromnetzes & Intelligente EE-Speicher-Planung")

# Überprüfung der Datenbank
if not os.path.exists("substations_climate_base.csv"):
    st.error("❌ Datenbank nicht gefunden! Bitte zuerst ausführen: python fetch_climate_data.py")
    st.stop()

@st.cache_data
def load_data():
    df = pd.read_csv("substations_climate_base.csv")
    
    # Ausfallsicherung für Kontakte/Webseiten
    df["Kontakt"] = df["Kontakt"].fillna("Nicht verfügbar")
    df["Webseite"] = df["Webseite"].fillna("Nicht verfügbar")
    
    # Ampelfarben für das Basisnetz
    def get_base_grid_color(avail):
        if avail <= 5: return [220, 20, 60, 180]     # Rot
        elif avail <= 20: return [255, 165, 0, 180]  # Orange
        return [34, 139, 34, 180]                    # Grün
        
    df['Farbe_Netz'] = df['Frei_MVA'].apply(get_base_grid_color)
    return df

df = load_data()

# =====================================================================
# 🎛️ BLOCK 1: BASIS-NETZFILTER
# =====================================================================
st.sidebar.header("🎛️ Basis-Netzfilter")

all_states = sorted(df["Bundesland"].dropna().unique())
selected_states = st.sidebar.multiselect("Bundesland auswählen", all_states, default=all_states)

all_operators = sorted(df["Betreiber"].dropna().unique())
selected_operators = st.sidebar.multiselect("Netzbetreiber auswählen", all_operators, default=all_operators)

min_v, max_v = float(df["Frei_MVA"].min()), float(df["Frei_MVA"].max())
range_mva = st.sidebar.slider("Verfügbare Netzkapazität (MVA)", min_v, max_v, (0.0, max_v))

# =====================================================================
# 🌤️ BLOCK 2: INTELLIGENTE ZUSATZFUNKTION (Vollbenutzungsstunden)
# =====================================================================
st.sidebar.markdown("---")
with st.sidebar.expander("🌤️ KI-Analyse: Dynamische EE-Aufteilung", expanded=True):
    use_climate_analysis = st.checkbox("Wirtschaftliche Aufteilung aktivieren", value=True)
    
    st.markdown("**Mindestanforderungen für Rentabilität:**")
    # Оптимизированы дефолтные значения (4.0 вместо 4.8 и 950 вместо 1050), чтобы проекты сразу отображались
    target_wind = st.slider("Min. Windgeschwindigkeit (m/s)", 3.5, 8.5, 4.0, 0.1)
    target_solar = st.slider("Min. Sonneneinstrahlung (kWh/m²)", 950, 1350, 950, 25)

# =====================================================================
# 📐 BLOCK 3: 3D-SKALIERUNG
# =====================================================================
st.sidebar.markdown("---")
st.sidebar.header("📐 3D-Visualisierung")
col_radius = st.sidebar.slider("Säulenbreite (m)", 100, 2500, 400, 100)
col_elevation = st.sidebar.slider("Höhenskalierung", 50, 800, 300, 50)


# =====================================================================
# 🧮 MATHEMATISCHER KERN: PEAK-SHAVING & SPEICHER-OPTIMIERUNG
# =====================================================================
f_df = df[
    (df["Bundesland"].isin(selected_states)) &
    (df["Betreiber"].isin(selected_operators)) &
    (df["Frei_MVA"].between(range_mva[0], range_mva[1]))
].copy()

def calculate_intelligent_mix(row):
    S = row['Frei_MVA']
    
    if not use_climate_analysis:
        return row['Farbe_Netz'], "Basis-Netzmodus", 0.0, 0.0, 0.0, 0, 0
    
    # 1. Stundenberechnung (VBS)
    if row['Wind_ms'] < 4.0:
        vbs_wind = 0.0
    else:
        vbs_wind = min(3200.0, 1000.0 + (row['Wind_ms'] - 4.0) * 500.0)
        
    vbs_solar = row['Solar_kWh'] * 0.85
    
    wind_ok = row['Wind_ms'] >= target_wind and vbs_wind > 0
    solar_ok = row['Solar_kWh'] >= target_solar
    
    if not wind_ok and not solar_ok:
        return [189, 195, 199, 100], "Geringes Potenzial", 0.0, 0.0, 0.0, int(vbs_wind), int(vbs_solar)
        
    # 2. Gewichte bestimmen
    total_vbs = (vbs_wind if wind_ok else 0) + (vbs_solar if solar_ok else 0)
    w_wind = (vbs_wind / total_vbs) if wind_ok else 0.0
    w_solar = (vbs_solar / total_vbs) if solar_ok else 0.0
    
    # Bestimmung des Speicher-Faktors für Peak-Shaving
    if wind_ok and solar_ok:
        speicher_anteil = 0.20 
        strategie_name = "Optimiertes Hybridkraftwerk + BESS"
        farbe = [155, 89, 182, 210] # Lila
    elif wind_ok:
        speicher_anteil = 0.25 
        strategie_name = "Windpark + BESS (Lastverschiebung)"
        farbe = [41, 128, 185, 210] # Blau
    else:
        speicher_anteil = 0.35 # Höherer Speicherbedarf für die Mittagssonne
        strategie_name = "PV-Anlage + BESS (Peak-Shaving)"
        farbe = [241, 196, 15, 210] # Gelb
        
    # --- NEUE PEAK-SHAVING LOGIK (Anforderung Professor) ---
    # Die Netzkapazität S wird als Basis-Einspeisung voll ausgenutzt.
    # Der Speicher (BESS) erlaubt eine Überdimensionierung der Anlagen, 
    # da er Erzeugungsspitzen (z.B. PV-Mittagsspitze) abfedert und verzögert einspeist.
    leistung_speicher = round(S * speicher_anteil, 1)
    
    # Überbelegung des Netzanschlusses dank intelligenter Batterie-Pufferung
    leistung_wea = round(S * w_wind * (1 + speicher_anteil), 1)
    leistung_pv = round(S * w_solar * (1 + speicher_anteil), 1)
    
    return farbe, strategie_name, leistung_wea, leistung_pv, leistung_speicher, int(vbs_wind), int(vbs_solar)

if not f_df.empty:
    res = f_df.apply(calculate_intelligent_mix, axis=1)
    f_df['Finale_Farbe'] = [r[0] for r in res]
    f_df['Strategie'] = [r[1] for r in res]
    f_df['WEA_Leistung_MVA'] = [r[2] for r in res]
    f_df['PV_Leistung_MVA'] = [r[3] for r in res]
    f_df['Speicher_MVA'] = [r[4] for r in res]
    f_df['VBS_Wind_h'] = [r[5] for r in res]
    f_df['VBS_Solar_h'] = [r[6] for r in res]


# =====================================================================
# 📊 METRIKEN (DYNAMISCH)
# =====================================================================
col1, col2, col3 = st.columns(3)

if not use_climate_analysis:
    col1.metric("Umspannwerke gesamt", len(f_df))
    col2.metric("Max. freie Kapazität", f"{f_df['Frei_MVA'].max()} MVA" if not f_df.empty else "0 MVA")
    col3.metric("Durchschn. freie Kapazität", f"{round(f_df['Frei_MVA'].mean(), 1)} MVA" if not f_df.empty else "0 MVA")
else:
    counts = f_df['Strategie'].value_counts()
    col1.metric("Wind+BESS Cluster", counts.get("Windpark + BESS (Lastverschiebung)", 0))
    col2.metric("PV+BESS Peak-Shaving", counts.get("PV-Anlage + BESS (Peak-Shaving)", 0))
    col3.metric("Optimierte Hybrid-Systeme", counts.get("Optimiertes Hybridkraftwerk + BESS", 0))

# =====================================================================
# 🎯 DYNAMISCHE STRUKTURIERUNG DES TOOLTIPS (Wording angepasst)
# =====================================================================
if not use_climate_analysis:
    tooltip_html = """
        <div style='font-family: sans-serif; padding: 12px; line-height: 1.6; min-width: 250px;'>
            <b style='font-size:16px; color: #2c3e50;'>{Name}</b><br/>
            <hr style='margin:6px 0; border: 0; border-top: 1px solid #ccc;'/>
            <b>Verfügbare Netzkapazität:</b> <span style='font-size: 15px; color: #27ae60; font-weight: bold;'>{Frei_MVA} MVA</span><br/>
            <b>Belegte / Reservierte Leistung:</b> {Belegt_MVA} MVA<br/>
            <hr style='margin:6px 0; border: 0; border-top: 1px solid #eee;'/>
            <b>Netzbetreiber:</b> {Betreiber}<br/>
            <b>Region:</b> {Bundesland}<br/>
            <b>Kontakt:</b> <span style='color:#e67e22;'>{Kontakt}</span><br/>
            <b>Webseite:</b> <a href='{Webseite}' target='_blank' style='color:#2980b9; text-decoration:none;'>{Webseite}</a>
        </div>
    """
else:
    tooltip_html = """
        <div style='font-family: sans-serif; padding: 12px; line-height: 1.6; min-width: 340px;'>
            <b style='font-size:16px; color: #2c3e50;'>{Name}</b><br/>
            <hr style='margin:6px 0; border: 0; border-top: 1px solid #ccc;'/>
            <b>Netzanschlussleistung (Limit):</b> <span style='color:#27ae60; font-weight:bold;'>{Frei_MVA} MVA</span><br/>
            <b>Belegte / Reservierte Leistung:</b> {Belegt_MVA} MVA<br/>
            
            <div style='background-color: #f8f9fa; padding: 8px; border-radius: 4px; margin-top: 5px; border-left: 4px solid #8e44ad;'>
                <b style='color:#8e44ad; font-size:13px;'>📈 KI-Einspeisekonzept (Peak-Shaving):</b><br/>
                <b>Konzept:</b> <span style='color:#2c3e50; font-weight:bold;'>{Strategie}</span><br/>
                💨 Max. Windkraft-Leistung: <b>{WEA_Leistung_MVA} MVA</b> ({VBS_Wind_h} h/Jahr)<br/>
                ☀️ Max. Photovoltaik-Leistung: <b>{PV_Leistung_MVA} MVA</b> ({VBS_Solar_h} h/Jahr)<br/>
                🔋 <b>BESS-Batteriepuffer: {Speicher_MVA} MVA</b> (federt Erzeugungsspitzen ab)
            </div>
            
            <hr style='margin:6px 0; border: 0; border-top: 1px solid #eee;'/>
            <b>Netzbetreiber:</b> {Betreiber} | {Bundesland}<br/>
            <b>Kontakt:</b> <span style='color:#e67e22;'>{Kontakt}</span><br/>
            <b>Webseite:</b> <a href='{Webseite}' target='_blank' style='color:#2980b9; text-decoration:none;'>{Webseite}</a>
        </div>
    """

# --- PYDECK MAP ---
view = pdk.ViewState(latitude=47.6, longitude=13.8, zoom=7, pitch=45)

layer = pdk.Layer(
    "ColumnLayer",
    data=f_df,
    get_position="[Länge, Breite]",
    get_elevation="Frei_MVA",
    elevation_scale=col_elevation,
    radius=col_radius,
    get_fill_color="Finale_Farbe" if not f_df.empty else [0, 0, 0, 0],
    pickable=True,
    auto_highlight=True,
)

st.pydeck_chart(pdk.Deck(
    layers=[layer],
    initial_view_state=view,
    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    tooltip={
        "html": tooltip_html,
        "style": {"backgroundColor": "white", "color": "black", "borderRadius": "5px", "boxShadow": "0px 2px 10px rgba(0,0,0,0.15)"}
    }
))

# --- ANLAGENREGISTER (TABELLE) ---
st.markdown("### 📋 Technisches Anlagenregister (Exportbereit)")
if not f_df.empty:
    columns_to_drop = ["Farbe_Netz", "Finale_Farbe", "Breite", "Länge"]
    if not use_climate_analysis:
        columns_to_drop += ["Strategie", "WEA_Leistung_MVA", "PV_Leistung_MVA", "Speicher_MVA", "VBS_Wind_h", "VBS_Solar_h"]
    st.dataframe(f_df.drop(columns=columns_to_drop), use_container_width=True)
else:
    st.info("Keine Umspannwerke entsprechen den gewählten Filterkriterien.")