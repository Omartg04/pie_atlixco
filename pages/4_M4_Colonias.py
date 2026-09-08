"""
M4 — ¿Cómo vamos en campo, por colonia?
PIE Atlixco · Arturo Solano Escobedo · Proceso interno Morena

Vista complementaria a M3, orientada a que las brigadas ubiquen el avance del
operativo de inducción en el nombre de colonia que conocen, en vez de solo el
número de sección.

⚠️ IMPORTANTE — naturaleza del dato:
El formulario de inducción en Bubble captura `seccion_electoral`, no colonia
ni manzana. Por lo tanto, el número de encuestas por colonia que se muestra
aquí es una ESTIMACIÓN por reparto proporcional (no un conteo real por
colonia): las encuestas de cada sección se reparten entre las colonias que la
componen, en proporción a la LN corte 500 de cada colonia dentro de esa
sección. El denominador (LN corte 500 elegible por colonia) sí es exacto —
sale del mismo crosswalk manzana→colonia que ya construimos, sin estimación.

Por la misma razón, este módulo NO incluye ranking de encuestadores ni
tabulación preliminar de opinión por colonia: no hay forma honesta de saber
en qué colonia específica trabajó cada encuestador, ni de desagregar una
respuesta de opinión por colonia sin fabricar precisión que no existe. Esas
vistas se quedan en M3, por sección. Ver memoria_calculo_modulo_colonias_atlixco.md
para el detalle metodológico completo del crosswalk.

Inicio real del operativo: 18 de julio de 2026, 9:00 AM (mismo ancla que M3).
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from app_utils import (
    GLOBAL_CSS, COLOR, load_manzanas, load_colonias_geojson,
    score_color, fmt_pct, fmt_num, check_password, sidebar_sesion,
    carto_tiles, CARTO_ATTR,
)
from bubble_connector import get_encuestas_induccion, HABITANTES_PROMEDIO_VIVIENDA

st.set_page_config(
    page_title="M4 · ¿Cómo vamos en campo, por colonia? · PIE Atlixco",
    page_icon="🏘️",
    layout="wide",
    initial_sidebar_state="expanded",
)
check_password()
sidebar_sesion()
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# Mismo ancla real del operativo que M3 y bubble_connector.py (18 jul 2026, 9:00 AM).
# Se redefine localmente aquí en vez de importarla, siguiendo el mismo patrón que
# ya usa 3_M3_Como_vamos_en_campo.py.
ANCLA_OPERATIVO = datetime(2026, 7, 18, 9, 0, 0)

NOMBRES_EXCLUIDOS = {"omar téllez", "omar tellez"}


# ════════════════════════════════════════════════════════════════════════════
# CAPA DE DATOS — LN corte 500 exacta por colonia + matriz de reparto sección→colonia
# ════════════════════════════════════════════════════════════════════════════

@st.cache_data
def cargar_ln_corte500_por_colonia():
    """
    REAL (exacto, sin estimación) — LN agregada del universo elegible corte
    500, por colonia. Se deriva de las mismas manzanas de
    atlixco_unificado_web_capas.geojson que usa M2/M3, agrupadas por
    colonia_id (campo ya presente en el geojson gracias al crosswalk
    manzana→colonia).

    IMPORTANTE: la llave es colonia_id (cvegeo de INEGI o "INE-<control>"),
    NUNCA colonia_nombre. 13 nombres de colonia en Atlixco corresponden a
    lugares distintos en el catálogo fuente (ej. "SANTA CRUZ" son 4 polígonos
    con cvegeo diferente, uno incluso FRACCIONAMIENTO y los demás COLONIA) —
    agrupar solo por nombre los fusionaría incorrectamente. Se agrega una
    `colonia_label` que desambigua el nombre en pantalla cuando se repite.

    Devuelve:
      - resumen_colonia: LN corte 500 y total por colonia, tipo, secciones que
        toca, n_manzanas, colonia_label (para mostrar en UI).
      - matriz_seccion_colonia: para cada (seccion, colonia_id), el peso =
        participación de esa colonia en el ln_meta_500 de esa sección — es la
        base del reparto proporcional de encuestas.
    """
    manzanas = load_manzanas()
    rows = [f["properties"] for f in manzanas["features"]]
    df_mz = pd.DataFrame(rows)
    df_mz["seleccionada_500"] = df_mz["seleccionada_500"].astype(str) == "True"
    df_mz = df_mz[df_mz["colonia_id"].notna()].copy()  # solo universo con crosswalk (37 secciones en_alcance)

    df_500 = df_mz[df_mz["seleccionada_500"]].copy()

    # Base: TODAS las colonias del universo, tengan o no manzanas en corte 500
    # (igual que M3 conserva las 5 secciones Modo B con ln_meta_500==0, en vez
    # de excluirlas — si se agrupara solo sobre df_500, las colonias sin
    # ninguna manzana seleccionada desaparecerían del selector y del mapa).
    base_colonia = (
        df_mz.groupby(["colonia_id", "colonia_nombre", "colonia_tipo", "origen_colonia"])
        .agg(
            ln_total_colonia=("LN_estimada_manzana", "sum"),
            secciones=("seccion", lambda s: ";".join(str(x) for x in sorted(set(s)))),
        )
        .reset_index()
    )
    meta_500 = (
        df_500.groupby("colonia_id")
        .agg(ln_meta_500=("LN_estimada_manzana", "sum"), n_manzanas_500=("id_unidad", "count"))
        .reset_index()
    )
    resumen_colonia = base_colonia.merge(meta_500, on="colonia_id", how="left")
    resumen_colonia["ln_meta_500"] = resumen_colonia["ln_meta_500"].fillna(0).round(0).astype(int)
    resumen_colonia["n_manzanas_500"] = resumen_colonia["n_manzanas_500"].fillna(0).astype(int)
    resumen_colonia["ln_total_colonia"] = resumen_colonia["ln_total_colonia"].round(0).astype(int)

    # Etiqueta que desambigua nombres repetidos: se agrega "(tipo · secciones)"
    # solo a las colonias cuyo nombre no es único en el universo.
    conteo_nombre = resumen_colonia["colonia_nombre"].value_counts()
    def _label(row):
        if conteo_nombre[row["colonia_nombre"]] > 1:
            return f"{row['colonia_nombre']} ({row['colonia_tipo']} · sec. {row['secciones']})"
        return row["colonia_nombre"]
    resumen_colonia["colonia_label"] = resumen_colonia.apply(_label, axis=1)

    # Desambiguación de segundo nivel: algunas colonias homónimas comparten
    # además tipo y las mismas secciones (ej. 3 polígonos "SANTA CRUZ
    # TEHUIXPANGO" distintos, los 3 tipo COLONIA, los 3 solo en sección 208)
    # — el label de arriba seguiría repitiéndose. Se añade un sufijo con los
    # últimos 4 dígitos del colonia_id (único por construcción) solo a las
    # filas cuyo label aún colisiona.
    dup_label = resumen_colonia["colonia_label"].duplicated(keep=False)
    if dup_label.any():
        resumen_colonia.loc[dup_label, "colonia_label"] = (
            resumen_colonia.loc[dup_label, "colonia_label"]
            + " #" + resumen_colonia.loc[dup_label, "colonia_id"].astype(str).str[-4:]
        )

    # Matriz de reparto: peso de cada colonia dentro del ln_meta_500 de su sección.
    # OJO: una colonia puede tocar mas de una seccion -> aparece una fila por
    # (seccion, colonia_id) que SI toca, con el peso relativo a esa seccion.
    ln_seccion_colonia = (
        df_500.groupby(["seccion", "colonia_id"])["LN_estimada_manzana"].sum()
        .reset_index().rename(columns={"LN_estimada_manzana": "ln_seccion_colonia"})
    )
    ln_seccion_total = (
        df_500.groupby("seccion")["LN_estimada_manzana"].sum()
        .reset_index().rename(columns={"LN_estimada_manzana": "ln_seccion_total"})
    )
    matriz = ln_seccion_colonia.merge(ln_seccion_total, on="seccion", how="left")
    matriz["peso"] = np.where(
        matriz["ln_seccion_total"] > 0,
        matriz["ln_seccion_colonia"] / matriz["ln_seccion_total"],
        0.0,
    )

    return resumen_colonia, matriz[["seccion", "colonia_id", "peso"]]


resumen_colonia, matriz_reparto = cargar_ln_corte500_por_colonia()

# ── Encuestas de Bubble — misma logica exacta que M3 ────────────────────────
_bubble_secrets = st.secrets.get("bubble", {})
_usar_bubble_real = bool(_bubble_secrets.get("private_key"))

if _usar_bubble_real:
    df_encuestas_full, ultima_actualizacion, info_carga = get_encuestas_induccion(
        private_key=_bubble_secrets["private_key"],
    )
    if df_encuestas_full.empty:
        st.warning("Sin encuestas capturadas en Bubble todavía.", icon="⚠️")
        st.stop()
    if info_carga.get("degradado"):
        st.warning(info_carga["mensaje"], icon="⚠️")
else:
    st.error(
        "Este módulo requiere la conexión real a Bubble (comparte caché con M3, "
        "no trae su propio mock) — revisa `st.secrets['bubble']['private_key']`."
    )
    st.stop()

df_encuestas_full = df_encuestas_full[
    (df_encuestas_full["fecha_creacion"] >= ANCLA_OPERATIVO)
    & (~df_encuestas_full["nombre_encuestador"].str.strip().str.lower().isin(NOMBRES_EXCLUIDOS))
].copy()

if df_encuestas_full.empty:
    st.warning("No hay encuestas capturadas desde el arranque real del operativo.")
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="header-modulo">
  <div class="hm-dots"><span></span><span></span><span></span></div>
  <div class="hm-eyebrow">Módulo 04 · Vista complementaria a M3</div>
  <h1>¿Cómo vamos en campo, por colonia?</h1>
  <p>Mismo avance del operativo de inducción que M3, orientado por colonia —
  el nombre que las brigadas reconocen en la calle — en vez de número de
  sección. El universo elegible (LN corte 500) es exacto; las encuestas por
  colonia son una estimación por reparto proporcional, marcada como tal en
  cada vista.</p>
</div>
""", unsafe_allow_html=True)

st.warning(
    "⚠️ **Las encuestas por colonia son una estimación**, no un conteo real. Bubble solo "
    "registra la sección de cada encuesta, no la colonia ni la manzana. El total de "
    "encuestas de cada sección se reparte entre sus colonias en proporción a la LN corte "
    "500 de cada una — asume que la cobertura fue pareja dentro de la sección, lo cual "
    "puede no ser cierto en la práctica. El dato exacto y no estimado, sección por sección, "
    "está en **M3 · ¿Cómo vamos en campo?**",
    icon="⚠️",
)

# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR — mismo periodo que M3
# ════════════════════════════════════════════════════════════════════════════

TIPOS_COLONIA_DISPONIBLES = sorted(resumen_colonia["colonia_tipo"].dropna().unique().tolist())

with st.sidebar:
    st.markdown("### Periodo")
    semanas_disponibles = sorted(
        df_encuestas_full["semana_operativo"].unique(),
        key=lambda s: int(s[1:]),
    )
    fecha_min = df_encuestas_full["fecha_creacion"].dt.date.min()
    fecha_max = df_encuestas_full["fecha_creacion"].dt.date.max()

    modo_vista = st.radio(
        "Vista",
        ["Acumulado a la fecha", "Solo esta semana", "Día específico"],
    )
    semana_sel = st.selectbox(
        "Semana", semanas_disponibles, index=len(semanas_disponibles) - 1,
        disabled=(modo_vista != "Solo esta semana"),
    )
    dia_sel = st.date_input(
        "Día", value=fecha_max, min_value=fecha_min, max_value=fecha_max,
        disabled=(modo_vista != "Día específico"),
    )

    st.markdown("### Filtro por tipo de colonia")
    tipos_sel = st.multiselect(
        "Tipo de colonia (opcional)",
        TIPOS_COLONIA_DISPONIBLES,
        default=TIPOS_COLONIA_DISPONIBLES,
        help="Muestra solo las colonias de estos tipos (clasificación de INEGI: "
             "COLONIA, FRACCIONAMIENTO, RANCHO, etc. — SIN_TIPO (fuente INE) para "
             "las rescatadas del INE). A diferencia de M3, aquí no hace falta "
             "reestimar nada: cada colonia ya tiene un solo tipo propio, así que "
             "filtrar solo oculta las que no aplican — no cambia el cálculo de "
             "ninguna colonia visible.",
    )
    if not tipos_sel:
        st.warning("Selecciona al menos un tipo de colonia — se muestra sin filtro mientras tanto.", icon="⚠️")
        tipos_sel = TIPOS_COLONIA_DISPONIBLES

filtro_tipo_activo = set(tipos_sel) != set(TIPOS_COLONIA_DISPONIBLES)

if modo_vista == "Solo esta semana":
    df_encuestas = df_encuestas_full[df_encuestas_full["semana_operativo"] == semana_sel].copy()
elif modo_vista == "Día específico":
    df_encuestas = df_encuestas_full[df_encuestas_full["fecha_creacion"].dt.date == dia_sel].copy()
else:
    df_encuestas = df_encuestas_full.copy()

if df_encuestas.empty:
    st.warning("No hay encuestas capturadas en el periodo seleccionado.")
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# REPARTO PROPORCIONAL: encuestas por sección → encuestas estimadas por colonia
# ════════════════════════════════════════════════════════════════════════════

conteo_seccion = (
    df_encuestas.groupby("seccion_electoral").size()
    .reset_index(name="encuestas_seccion").rename(columns={"seccion_electoral": "seccion"})
)

reparto = matriz_reparto.merge(conteo_seccion, on="seccion", how="inner")
reparto["encuestas_estimadas"] = reparto["encuestas_seccion"] * reparto["peso"]

encuestas_colonia = (
    reparto.groupby("colonia_id")["encuestas_estimadas"].sum().reset_index()
)

resumen = resumen_colonia.merge(encuestas_colonia, on="colonia_id", how="left")
resumen["encuestas_estimadas"] = resumen["encuestas_estimadas"].fillna(0.0)
resumen["ln_proyectada_cubierta"] = (resumen["encuestas_estimadas"] * HABITANTES_PROMEDIO_VIVIENDA).round(0).astype(int)
resumen["pct_ln_cubierta"] = np.where(
    resumen["ln_meta_500"] > 0,
    (resumen["ln_proyectada_cubierta"] / resumen["ln_meta_500"] * 100),
    np.nan,
)

# Filtro por tipo de colonia: cada colonia ya tiene un solo colonia_tipo propio
# (no es una mezcla como en M3), así que filtrar es solo quedarse con esas
# filas — no hace falta recalcular ni reestimar nada del resto.
total_colonias_sin_filtro = len(resumen)
if filtro_tipo_activo:
    resumen = resumen[resumen["colonia_tipo"].isin(tipos_sel)].copy()
    st.info(
        f"🔎 Filtro de tipo de colonia activo: mostrando {len(resumen)} de "
        f"{total_colonias_sin_filtro} colonias ({', '.join(tipos_sel)}). El método de "
        "estimación de encuestas no cambia — el filtro solo oculta colonias, no "
        "recalcula las visibles.",
        icon="🔎",
    )
    if resumen.empty:
        st.warning("Ninguna colonia de este tipo en el universo priorizado.")
        st.stop()

# ════════════════════════════════════════════════════════════════════════════
# KPI TICKER
# ════════════════════════════════════════════════════════════════════════════

total_encuestas = len(df_encuestas)
ln_proyectada_total = int(resumen["ln_proyectada_cubierta"].sum())
colonias_cubiertas = int((resumen["encuestas_estimadas"] >= 0.5).sum())
total_colonias = len(resumen)
pct_ln_total = (resumen["ln_proyectada_cubierta"].sum() / resumen["ln_meta_500"].sum() * 100) if resumen["ln_meta_500"].sum() > 0 else float("nan")

kpis = [
    ("Encuestas capturadas", fmt_num(total_encuestas), "Periodo seleccionado — dato real, sin reparto"),
    ("LN proyectada cubierta", fmt_num(ln_proyectada_total), "Suma de la estimación por colonia (= total de M3)"),
    ("% LN cubierta (proyectada)", fmt_pct(pct_ln_total), "Debe coincidir con el % global de M3"),
    ("Colonias con avance estimado", f"{colonias_cubiertas} de {total_colonias}", "≥1 encuesta estimada (redondeo ≥0.5)"),
]

cols = st.columns(4)
for col, (label, val, ctx) in zip(cols, kpis):
    with col:
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-val">{val}</div>
          <div class="kpi-label">{label}</div>
          <div class="kpi-ctx">{ctx}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# MAPA Y COBERTURA POR COLONIA
# ════════════════════════════════════════════════════════════════════════════

st.markdown("### Selecciona una colonia")
id_to_label = dict(zip(resumen["colonia_id"], resumen["colonia_label"]))
colonias_lista = sorted(resumen["colonia_id"].tolist(), key=lambda cid: id_to_label[cid])
if "m4_sel_colonia" not in st.session_state or st.session_state["m4_sel_colonia"] not in colonias_lista:
    st.session_state["m4_sel_colonia"] = colonias_lista[0]

sel = st.selectbox(
    "Colonia", colonias_lista,
    index=colonias_lista.index(st.session_state["m4_sel_colonia"]),
    format_func=lambda cid: id_to_label.get(cid, cid),
    label_visibility="collapsed",
)
st.session_state["m4_sel_colonia"] = sel

st.markdown(f"""
<div style="display:flex; align-items:center; gap:10px; margin:12px 0 10px; font-size:.76rem; color:{COLOR['text_muted']};">
  <span>Sin cobertura</span>
  <div style="flex:1; height:8px; border-radius:4px;
              background:linear-gradient(90deg,#5b7a9e 0%,#8a8564 50%,#e8a33d 100%);"></div>
  <span>Cobertura completa</span>
</div>
<div style="font-size:.72rem; color:{COLOR['text_muted']}; margin-bottom:14px;">
  Relleno por % de LN corte 500 cubierta (estimado por reparto proporcional).
</div>
""", unsafe_allow_html=True)

col_map, col_card = st.columns([1.4, 1], gap="medium")

geo = load_colonias_geojson()
lookup_resumen = resumen.set_index("colonia_id")


def _centroid(features):
    lats, lons = [], []
    for feat in features:
        try:
            coords = feat["geometry"]["coordinates"]
            def _flatten(c):
                if isinstance(c[0], (float, int)):
                    lats.append(c[1]); lons.append(c[0])
                else:
                    for cc in c:
                        _flatten(cc)
            _flatten(coords)
        except Exception:
            continue
    return [sum(lats) / len(lats), sum(lons) / len(lons)] if lats else None


with col_map:
    feat_sel = next((f for f in geo["features"] if f["properties"].get("colonia_id") == sel), None)
    center = (_centroid([feat_sel]) if feat_sel else None) or [18.9, -98.43]
    zoom = 16 if feat_sel else 13

    m = folium.Map(location=center, zoom_start=zoom, tiles=carto_tiles(), attr=CARTO_ATTR)

    def style_fn(feature):
        cid = feature["properties"].get("colonia_id")
        if cid not in lookup_resumen.index:
            return {"fillColor": "#2a3140", "color": "#3a4255", "weight": .5, "fillOpacity": .15}
        val = lookup_resumen.loc[cid, "pct_ln_cubierta"]
        color = score_color(val, 0, 100)
        style = {"fillColor": color, "color": "#0f1218", "weight": 1, "fillOpacity": .75}
        if cid == sel:
            style["color"] = "#eef1f0"
            style["weight"] = 3
        return style

    def highlight_fn(feature):
        return {"weight": 2.5, "color": "#eef1f0", "fillOpacity": .9}

    geo_rich = {"type": "FeatureCollection", "features": []}
    for feat in geo["features"]:
        f2 = dict(feat)
        f2["properties"] = dict(feat["properties"])
        cid = f2["properties"].get("colonia_id")
        if cid in lookup_resumen.index:
            r = lookup_resumen.loc[cid]
            f2["properties"].update({
                "colonia_label": r["colonia_label"],
                "Encuestas (est.)": round(r["encuestas_estimadas"], 1),
                "LN proyectada": int(r["ln_proyectada_cubierta"]),
                "LN corte 500": int(r["ln_meta_500"]),
                "% Cubierta (est.)": fmt_pct(r["pct_ln_cubierta"]),
            })
        else:
            f2["properties"].update({
                "colonia_label": f2["properties"].get("colonia_nombre", "—"),
                "Encuestas (est.)": "—", "LN proyectada": "—", "LN corte 500": "—", "% Cubierta (est.)": "—",
            })
        geo_rich["features"].append(f2)

    folium.GeoJson(
        geo_rich,
        style_function=style_fn,
        highlight_function=highlight_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["colonia_label", "colonia_tipo", "Encuestas (est.)", "LN proyectada", "LN corte 500", "% Cubierta (est.)"],
            aliases=["Colonia", "Tipo", "Encuestas (estimadas)", "LN proyectada (×3.86)", "LN corte 500", "% Cubierta (estimado)"],
            sticky=True, labels=True,
            style="font-family:'DM Sans',sans-serif; font-size:12.5px; background:#1b212b; "
                  "color:#eef1f0; border:1px solid #3a4255; border-radius:6px;",
            max_width=260,
        ),
        name="colonias",
    ).add_to(m)

    map_out = st_folium(m, height=520, use_container_width=True, key=f"m4_map_{sel}")

    if map_out and map_out.get("last_active_drawing"):
        props = map_out["last_active_drawing"].get("properties", {})
        col_click = props.get("colonia_id")
        if col_click in lookup_resumen.index and col_click != st.session_state["m4_sel_colonia"]:
            st.session_state["m4_sel_colonia"] = col_click
            st.rerun()

with col_card:
    r = lookup_resumen.loc[sel]
    color_pct = score_color(r["pct_ln_cubierta"], 0, 100)

    if r["ln_meta_500"] > 0:
        etiqueta_principal = f"{fmt_pct(r['pct_ln_cubierta'])} de la LN corte 500 cubierta (estimado)"
        ctx_ln = f"LN total de la colonia: {int(r['ln_total_colonia']):,} (corte 500 = {int(r['ln_meta_500']):,})"
    else:
        etiqueta_principal = "Colonia sin manzanas en el corte 500"
        ctx_ln = f"LN total de la colonia: {int(r['ln_total_colonia']):,}"

    origen_tag = (
        '<span class="tag zona">SIN TIPO — FUENTE INE</span>' if r["origen_colonia"] == "INE" else ""
    )

    st.markdown(f"""
    <div class="card-wrap">
      <div style="background:linear-gradient(135deg,{COLOR['bg_raised_2']} 0%,{COLOR['bg_base']} 100%);
                  border:1px solid {COLOR['border_subtle']}; border-bottom:3px solid {color_pct};
                  border-radius:10px; padding:20px 24px;">
        <div style="font-family:'JetBrains Mono',monospace; font-size:.7rem; font-weight:700;
                    letter-spacing:.1em; text-transform:uppercase; color:{COLOR['text_secondary']}; margin-bottom:6px;">
          {r['colonia_label'].upper()}
        </div>
        <div style="margin-bottom:10px;">
          <span class="tag seccion">{r['colonia_tipo']}</span>{origen_tag}
        </div>
        <div style="display:flex; gap:22px; flex-wrap:wrap; margin-bottom:6px;">
          <div>
            <div class="kpi-val" style="font-size:1.6rem;">{round(r['encuestas_estimadas'], 1)}</div>
            <div class="kpi-label" style="font-size:.72rem;">Encuestas (estimadas)</div>
          </div>
          <div>
            <div class="kpi-val" style="font-size:1.6rem;">{int(r['ln_proyectada_cubierta']):,}</div>
            <div class="kpi-label" style="font-size:.72rem;">LN proyectada cubierta</div>
          </div>
          <div>
            <div class="kpi-val" style="font-size:1.6rem; color:{color_pct};">{fmt_pct(r['pct_ln_cubierta']) if r['ln_meta_500'] > 0 else '—'}</div>
            <div class="kpi-label" style="font-size:.72rem;">% LN cubierta (est.)</div>
          </div>
        </div>
        <div class="kpi-label">{etiqueta_principal}</div>
        <div class="kpi-ctx" style="margin-top:6px;">{ctx_ln}</div>
        <div class="kpi-ctx" style="margin-top:6px;">Secciones que toca: {r['secciones']}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if r["origen_colonia"] == "INE":
        st.caption(
            "ℹ️ Esta colonia no tiene delimitación en el marco de INEGI 2025 — se usó el "
            "polígono y nombre del INE como rescate, por lo que no tiene tipo de "
            "asentamiento clasificado."
        )

st.markdown("---")
st.markdown("### Todas las colonias")
st.caption(
    "Encuestas estimadas (reparto proporcional) y % de LN corte 500 cubierta, "
    + (f"colonias de tipo {', '.join(tipos_sel)}" if filtro_tipo_activo
       else "todas las colonias")
    + " del universo priorizado (37 secciones en_alcance)."
)

tabla_colonias = resumen.copy().sort_values("pct_ln_cubierta", ascending=False, na_position="last")
tabla_colonias_fmt = tabla_colonias[
    ["colonia_label", "colonia_tipo", "encuestas_estimadas", "ln_proyectada_cubierta", "ln_meta_500", "pct_ln_cubierta", "secciones"]
].rename(columns={
    "colonia_label": "Colonia", "colonia_tipo": "Tipo",
    "encuestas_estimadas": "Encuestas (est.)",
    "ln_proyectada_cubierta": "LN proyectada cubierta",
    "ln_meta_500": "LN corte 500", "pct_ln_cubierta": "% LN cubierta (est.)",
    "secciones": "Secciones",
})
tabla_colonias_fmt["Encuestas (est.)"] = tabla_colonias_fmt["Encuestas (est.)"].round(1)

st.dataframe(
    tabla_colonias_fmt,
    use_container_width=True,
    hide_index=True,
    column_config={
        "% LN cubierta (est.)": st.column_config.ProgressColumn(
            "% LN cubierta (est.)", min_value=0, max_value=100, format="%.1f%%",
        ),
    },
)