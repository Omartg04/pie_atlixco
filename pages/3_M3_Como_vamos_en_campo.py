"""
M3 — ¿Cómo vamos en campo?
PIE Atlixco · Arturo Solano Escobedo · Proceso interno Morena

Operativo de inducción territorial: encuestadores levantan un formulario corto
(14 páginas) casa por casa, capturado en Bubble. Este módulo mide avance de
cobertura contra la LN elegible (corte 500), desempeño por encuestador, y
tabulación preliminar de 3 preguntas clave sobre Arturo Solano.

⚠️ ESTADO: capa de datos de Bubble en MOCK. La conexión real a la Data API de
Bubble está pendiente de que se confirme el nombre del "thing" en el editor.
En cuanto esté, se reemplaza únicamente `cargar_encuestas_induccion()` por el
conector real — el resto del módulo (KPIs, mapa, cards, tabla, tabulación) no
cambia, porque ya opera sobre el DataFrame con el esquema final esperado.

Inicio real del operativo: 18 de julio de 2026, 9:00 AM (hora ancla para el
cálculo de semana operativa).
"""

import sys
import os
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from app_utils import (
    GLOBAL_CSS, COLOR, load_spt, load_geojson, load_manzanas,
    score_color, fmt_pct, fmt_num, check_password, sidebar_sesion,
)
from bubble_connector import get_encuestas_induccion

st.set_page_config(
    page_title="M3 · ¿Cómo vamos en campo? · PIE Atlixco",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)
check_password()
sidebar_sesion()
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# ANCLA DEL OPERATIVO — real, no mock
# ════════════════════════════════════════════════════════════════════════════

ANCLA_OPERATIVO = datetime(2026, 7, 18, 9, 0, 0)


def semana_operativo(fecha) -> str:
    """Asigna una etiqueta de semana operativa (S1, S2, ...) a una fecha,
    con ancla real el 18 de julio 2026, 9:00 AM. Semana operativa = 7 días
    corridos desde la hora de arranque, sin necesidad de guardar snapshots:
    Bubble conserva el histórico completo y esto se recalcula en cada carga."""
    if isinstance(fecha, pd.Timestamp):
        fecha = fecha.to_pydatetime()
    delta = fecha - ANCLA_OPERATIVO
    semana_num = (delta.days // 7) + 1
    return f"S{max(semana_num, 1)}"


# ════════════════════════════════════════════════════════════════════════════
# CAPA DE DATOS — MOCK (reemplazar por conector real de Bubble)
# ════════════════════════════════════════════════════════════════════════════

NOMBRES_MOCK = [
    "Juana Pérez Luna", "Carlos Ramírez Toledo", "María Hernández Cruz",
    "Luis Ángel Domínguez", "Rosa Isela Martínez", "Fernando Ortiz Vega",
    "Guadalupe Sánchez Ríos", "Jorge Alberto Nava",
]


@st.cache_data
def cargar_encuestas_induccion_mock(n_registros: int = 420) -> pd.DataFrame:
    """
    MOCK — simula el resultado ya transformado de la Data API de Bubble para
    el formulario de inducción (ver Diccionario de variables). Distribución
    de secciones ponderada (algunas secciones con más avance que otras, como
    se espera en campo real), encuestadores con volumen desigual, fechas
    distribuidas desde el ancla del operativo hasta hoy.

    Al conectar Bubble real: esta función se reemplaza por el conector
    (paginación + auth + transform + exclusión de PII), devolviendo un
    DataFrame con exactamente estas columnas.
    """
    rng = random.Random(42)
    np_rng = np.random.default_rng(42)

    secciones = sorted(load_spt()["seccion"].tolist())
    # Pesos: unas secciones con más avance que otras (simula campo real desigual)
    pesos = np_rng.dirichlet(np.ones(len(secciones)) * 0.6)

    hoy = datetime.now()
    dias_operativo = max((hoy - ANCLA_OPERATIVO).days, 1)

    filas = []
    for i in range(n_registros):
        seccion = rng.choices(secciones, weights=pesos, k=1)[0]
        encuestador = rng.choice(NOMBRES_MOCK)
        dia_offset = rng.randint(0, dias_operativo)
        hora_offset = rng.randint(0, 9 * 3600)  # jornada de campo ~9h
        fecha_creacion = ANCLA_OPERATIVO + timedelta(days=dia_offset, seconds=hora_offset)
        duracion_min = max(2, rng.gauss(7, 2.5))
        fecha_modificacion = fecha_creacion + timedelta(minutes=duracion_min)

        conoc = rng.choices(["Sí", "No", "No respondió"], weights=[0.42, 0.35, 0.23])[0]
        buen_cand = rng.choices(["Sí", "No", "No sabe (NO LEER)"], weights=[0.55, 0.18, 0.27])[0]
        votar = rng.choices(
            ["Votaría", "Nunca votaría", "No sabe (NO LEER)"],
            weights=[0.52, 0.24, 0.24],
        )[0]

        # ── Resto de variables del instrumento (mock, para el tabulado completo) ──
        aprobacion_atlixco = rng.choices(
            ["APRUEBA", "APRUEBA MUCHO", "DESAPRUEBA", "DESAPRUEBA MUCHO"], weights=[0.30, 0.10, 0.36, 0.24])[0]
        aprobacion_gobernador = rng.choices(
            ["APRUEBA", "APRUEBA MUCHO", "DESAPRUEBA", "DESAPRUEBA MUCHO"], weights=[0.34, 0.14, 0.32, 0.20])[0]
        aprobacion_presidenta = rng.choices(
            ["APRUEBA", "APRUEBA MUCHO", "DESAPRUEBA", "DESAPRUEBA MUCHO"], weights=[0.40, 0.24, 0.24, 0.12])[0]
        amor_puebla = rng.choices(["Sí", "No"], weights=[0.47, 0.53])[0]
        percepcion_inseguridad = rng.choices(["Mucho", "Algo", "Poco"], weights=[0.50, 0.32, 0.18])[0]
        comite_vigilancia = rng.choices(
            ["Sí", "No", "No sabe (NO LEER)"], weights=[0.61, 0.19, 0.20])[0]
        alarma_vecinal = rng.choices(["Mucho", "Algo", "Nada"], weights=[0.42, 0.38, 0.20])[0]
        seguridad_pct = rng.choices(
            ["Mucho", "Algo", "Poco", "Nada", "No sabe (NO LEER)"], weights=[0.20, 0.32, 0.26, 0.14, 0.08])[0]
        honestidad_arturo = rng.choices(["Mucho", "Algo", "Poco"], weights=[0.46, 0.34, 0.20])[0]
        cumplimiento_arturo = rng.choices(["Mucho", "Algo", "Poco", "Nada"], weights=[0.40, 0.32, 0.18, 0.10])[0]
        principal_problema = rng.choices(
            ["Inseguridad", "Bajos salarios", "Calles en mal estado",
             "Mala calidad de la educación pública",
             "Mantenimiento y reparación del alumbrado público",
             "Migración", "Otra ESPECIFICAR"],
            weights=[0.34, 0.18, 0.16, 0.12, 0.10, 0.06, 0.04])[0]
        principal_problema_otro = (
            rng.choice(["Falta de agua", "Falta de espacios recreativos"])
            if principal_problema == "Otra ESPECIFICAR" else ""
        )
        tipo_inseguridad = (
            rng.choices(["Asaltos en vía pública y transporte", "No sabe"], weights=[0.78, 0.22])[0]
            if principal_problema == "Inseguridad" else ""
        )
        tipo_inseguridad_otro = ""  # sin especificación "otro" observada en datos reales aún
        tiene_celular = rng.random() < 0.78
        tiene_email = rng.random() < 0.31

        filas.append({
            "id_unico": f"mock_{i:05d}",
            "email_encuestador": f"{encuestador.split()[0].lower()}@induccion.atlixco",
            "nombre_encuestador": encuestador,
            "fecha_creacion": fecha_creacion,
            "fecha_modificacion": fecha_modificacion,
            "duracion_min": round(duracion_min, 1),
            "seccion_electoral": int(seccion),
            "conocimiento_arturo": conoc,
            "buena_candidatura_arturo": buen_cand,
            "votar_o_no_arturo": votar,
            "aprobacion_atlixco": aprobacion_atlixco,
            "aprobacion_gobernador": aprobacion_gobernador,
            "aprobacion_presidenta": aprobacion_presidenta,
            "amor_puebla": amor_puebla,
            "percepcion_inseguridad": percepcion_inseguridad,
            "comite_vigilancia": comite_vigilancia,
            "alarma_vecinal": alarma_vecinal,
            "seguridad": seguridad_pct,
            "honestidad_arturo": honestidad_arturo,
            "cumplimiento_arturo": cumplimiento_arturo,
            "principal_problema_estado_opciones": principal_problema,
            "principal_problema_estado_otro": principal_problema_otro,
            "tipo_inseguridad_opciones": tipo_inseguridad,
            "tipo_inseguridad_otro": tipo_inseguridad_otro,
            # Contacto: solo se guarda si se capturó (booleano), nunca el dato en sí —
            # mismo principio de exclusión de PII que en el proyecto de referencia.
            "tiene_celular": tiene_celular,
            "tiene_email": tiene_email,
        })

    df = pd.DataFrame(filas)
    df["semana_operativo"] = df["fecha_creacion"].apply(semana_operativo)
    return df


@st.cache_data
def cargar_ln_corte500_real() -> pd.DataFrame:
    """
    REAL — LN agregada del universo elegible, corte 500, por sección.
    Se deriva sumando `LN_estimada_manzana` de las manzanas con
    `seleccionada_500 == True` en atlixco_unificado_web_capas.geojson
    (el mismo geojson de manzanas que usa M2), agrupado por `seccion`.
    Total verificado: 52,628 LN en las 37 secciones con corte 500.

    Las secciones sin manzanas seleccionadas en corte 500 (5 secciones Modo B
    sin cobertura LN por manzana: 207, 214, 215, 217, 219) quedan en 0 —
    correcto: esas secciones no tienen universo elegible por manzana, se
    trabajan por barrido total (ver SPT Modo B).
    """
    manzanas = load_manzanas()
    rows = [f["properties"] for f in manzanas["features"]]
    df_mz = pd.DataFrame(rows)
    df_mz["seleccionada_500"] = df_mz["seleccionada_500"].astype(str) == "True"

    agg_500 = (
        df_mz[df_mz["seleccionada_500"]]
        .groupby("seccion")["LN_estimada_manzana"]
        .sum()
        .reset_index()
        .rename(columns={"LN_estimada_manzana": "ln_meta_500"})
    )
    agg_total = (
        df_mz.groupby("seccion")["LN_estimada_manzana"]
        .sum()
        .reset_index()
        .rename(columns={"LN_estimada_manzana": "ln_total_seccion"})
    )

    df_spt = load_spt()
    todas_secciones = pd.DataFrame({"seccion": df_spt["seccion"].unique()})
    resultado = todas_secciones.merge(agg_500, on="seccion", how="left").merge(
        agg_total, on="seccion", how="left"
    )
    resultado["ln_meta_500"] = resultado["ln_meta_500"].fillna(0).round(0).astype(int)
    resultado["ln_total_seccion"] = resultado["ln_total_seccion"].fillna(0).round(0).astype(int)
    return resultado


# ── Carga ────────────────────────────────────────────────────────────────
df_ln500 = cargar_ln_corte500_real()

_bubble_secrets = st.secrets.get("bubble", {})
_usar_bubble_real = bool(_bubble_secrets.get("private_key"))

if _usar_bubble_real:
    with st.sidebar:
        forzar_refresh = st.button("🔄 Actualizar datos de Bubble", use_container_width=True)
    df_encuestas_full, ultima_actualizacion, info_carga = get_encuestas_induccion(
        private_key=_bubble_secrets["private_key"], force_refresh=forzar_refresh,
    )
    if forzar_refresh:
        st.toast(f"Actualizado — {len(df_encuestas_full)} registros totales en Bubble.", icon="🔄")
    if df_encuestas_full.empty:
        st.warning(
            "Bubble respondió pero no hay encuestas capturadas todavía, o no se pudo "
            "conectar. Revisa el mensaje de arriba." if info_carga.get("mensaje") else
            "Sin encuestas capturadas en Bubble todavía.",
            icon="⚠️",
        )
        st.stop()
    if info_carga.get("degradado"):
        st.warning(info_carga["mensaje"], icon="⚠️")
    else:
        st.caption(
            f"✅ Conectado a Bubble · última actualización: "
            f"{ultima_actualizacion.strftime('%d/%m/%Y %H:%M UTC') if ultima_actualizacion else '—'}"
        )
else:
    df_encuestas_full = cargar_encuestas_induccion_mock()
    st.info(
        "📡 **Las encuestas de inducción están en modo demostración (mock).** "
        "No se encontraron credenciales de Bubble en `st.secrets['bubble']['private_key']`. "
        "La LN del corte 500 (denominador de cobertura) ya es el dato real, derivado de "
        "`atlixco_unificado_web_capas.geojson` — 52,628 LN en las 37 secciones con "
        "universo elegible por manzana.",
        icon="⚠️",
    )

# ── Corte real del operativo (18 julio 2026, 9:00 AM) ───────────────────────
# Cualquier registro anterior al arranque real (ej. pruebas de configuración
# del formulario en Bubble) queda fuera de todo el módulo, incluyendo el KPI
# de total de encuestas. Bubble conserva ese historial, pero no es operativo.
NOMBRES_EXCLUIDOS = {"omar téllez", "omar tellez"}

_total_bubble_bruto = len(df_encuestas_full)
df_encuestas_full = df_encuestas_full[
    (df_encuestas_full["fecha_creacion"] >= ANCLA_OPERATIVO)
    & (~df_encuestas_full["nombre_encuestador"].str.strip().str.lower().isin(NOMBRES_EXCLUIDOS))
].copy()
_total_bubble_filtrado = len(df_encuestas_full)
_descartados = _total_bubble_bruto - _total_bubble_filtrado

if _descartados > 0:
    st.caption(
        f"🗓️ {_total_bubble_bruto} registros totales en Bubble · {_descartados} descartados "
        f"por ser anteriores al arranque real del operativo (18 jul, 9:00 AM) o pruebas "
        f"de configuración · **{_total_bubble_filtrado} dentro del operativo real**."
    )

if df_encuestas_full.empty:
    st.warning("No hay encuestas capturadas desde el arranque real del operativo (18 jul, 9:00 AM).")
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="header-modulo">
  <div class="hm-dots"><span></span><span></span><span></span></div>
  <div class="hm-eyebrow">Módulo 03 · En producción</div>
  <h1>¿Cómo vamos en campo?</h1>
  <p>Avance del operativo de inducción: cuántas entrevistas llevamos por sección
  contra la lista nominal elegible (corte 500), quién las está levantando, y qué
  nos dicen ya sobre Arturo Solano quienes fueron entrevistados.</p>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR — semana operativa
# ════════════════════════════════════════════════════════════════════════════

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
        help="Acumulado: todo lo capturado desde el inicio del operativo (18 jul, 9:00 AM). "
             "Solo esta semana: filtra a una semana operativa completa (7 días desde el ancla). "
             "Día específico: elige una fecha del calendario.",
    )

    semana_sel = st.selectbox(
        "Semana",
        semanas_disponibles,
        index=len(semanas_disponibles) - 1,
        disabled=(modo_vista != "Solo esta semana"),
        help="Semanas de 7 días desde el ancla del operativo (18 jul, 9:00 AM).",
    )

    dia_sel = st.date_input(
        "Día",
        value=fecha_max,
        min_value=fecha_min,
        max_value=fecha_max,
        disabled=(modo_vista != "Día específico"),
        help="Filtra encuestas capturadas ese día calendario.",
    )

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
# AGREGADOS POR SECCIÓN
# ════════════════════════════════════════════════════════════════════════════

conteo_seccion = (
    df_encuestas.groupby("seccion_electoral")
    .agg(encuestas=("id_unico", "count"))
    .reset_index()
    .rename(columns={"seccion_electoral": "seccion"})
)

resumen = df_ln500.merge(conteo_seccion, on="seccion", how="left")
resumen["encuestas"] = resumen["encuestas"].fillna(0).astype(int)
# 5 secciones Modo B sin universo elegible por manzana (207,214,215,217,219):
# ln_meta_500 == 0 → % no aplica (no se puede dividir entre 0), se deja NaN.
resumen["pct_ln_cubierta"] = np.where(
    resumen["ln_meta_500"] > 0,
    (resumen["encuestas"] / resumen["ln_meta_500"] * 100).clip(upper=100),
    np.nan,
)

# ════════════════════════════════════════════════════════════════════════════
# KPI TICKER
# ════════════════════════════════════════════════════════════════════════════

total_encuestas = len(df_encuestas)
secciones_cubiertas = int((resumen["encuestas"] > 0).sum())
total_secciones = len(resumen)
encuestadores_activos = df_encuestas["nombre_encuestador"].nunique()
tiempo_prom = df_encuestas["duracion_min"].mean()
pct_ln_total = (resumen["encuestas"].sum() / resumen["ln_meta_500"].sum() * 100)

kpis = [
    ("% LN cubierta (corte 500)", fmt_pct(pct_ln_total), "Encuestas / LN elegible, universo 500"),
    ("Encuestas capturadas", fmt_num(total_encuestas), "Periodo seleccionado"),
    ("Secciones cubiertas", f"{secciones_cubiertas} de {total_secciones}", "Con al menos 1 encuesta"),
    ("Encuestadores activos", fmt_num(encuestadores_activos), "En el periodo seleccionado"),
    ("Tiempo promedio", f"{tiempo_prom:.1f} min", "Duración de la entrevista"),
]

cols = st.columns(5)
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
# TABS
# ════════════════════════════════════════════════════════════════════════════

tab_mapa, tab_encuestadores, tab_resultados = st.tabs(
    ["🗺️ Mapa y cobertura", "👥 Encuestadores", "📋 Resultados preliminares"]
)

# ── TAB 1 — Mapa ────────────────────────────────────────────────────────────
with tab_mapa:
    st.markdown("### Selecciona una sección")
    secciones_lista = sorted(resumen["seccion"].tolist())
    if "m3_sel_seccion" not in st.session_state:
        st.session_state["m3_sel_seccion"] = secciones_lista[0]

    sel = st.selectbox(
        "Sección",
        secciones_lista,
        index=secciones_lista.index(st.session_state["m3_sel_seccion"]),
        format_func=lambda s: f"Sección {s}",
        label_visibility="collapsed",
    )
    st.session_state["m3_sel_seccion"] = sel

    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:10px; margin:12px 0 10px; font-size:.76rem; color:{COLOR['text_muted']};">
      <span>Sin cobertura</span>
      <div style="flex:1; height:8px; border-radius:4px;
                  background:linear-gradient(90deg,#5b7a9e 0%,#8a8564 50%,#e8a33d 100%);"></div>
      <span>Cobertura completa</span>
    </div>
    <div style="font-size:.72rem; color:{COLOR['text_muted']}; margin-bottom:14px;">
      Relleno por % de LN corte 500 cubierta con encuestas de inducción capturadas.
    </div>
    """, unsafe_allow_html=True)

    col_map, col_card = st.columns([1.4, 1], gap="medium")

    geo = load_geojson()
    lookup_resumen = resumen.set_index("seccion")

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
        feat_sel = next((f for f in geo["features"] if f["properties"].get("seccion") == sel), None)
        center = (_centroid([feat_sel]) if feat_sel else None) or [18.9, -98.43]
        zoom = 16 if feat_sel else 13

        m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB dark_matter")

        def style_fn(feature):
            sec = feature["properties"].get("seccion")
            if sec not in lookup_resumen.index:
                return {"fillColor": "#2a3140", "color": "#3a4255", "weight": .5, "fillOpacity": .15}
            val = lookup_resumen.loc[sec, "pct_ln_cubierta"]
            color = score_color(val, 0, 100)
            style = {"fillColor": color, "color": "#0f1218", "weight": 1, "fillOpacity": .75}
            if sec == sel:
                style["color"] = "#eef1f0"
                style["weight"] = 3
            return style

        def highlight_fn(feature):
            return {"weight": 2.5, "color": "#eef1f0", "fillOpacity": .9}

        geo_rich = {"type": "FeatureCollection", "features": []}
        for feat in geo["features"]:
            f2 = dict(feat)
            f2["properties"] = dict(feat["properties"])
            sec = f2["properties"].get("seccion")
            if sec in lookup_resumen.index:
                r = lookup_resumen.loc[sec]
                f2["properties"].update({
                    "Encuestas": int(r["encuestas"]),
                    "LN corte 500": int(r["ln_meta_500"]),
                    "% Cubierta": fmt_pct(r["pct_ln_cubierta"]),
                })
            else:
                f2["properties"].update({"Encuestas": "—", "LN corte 500": "—", "% Cubierta": "—"})
            geo_rich["features"].append(f2)

        folium.GeoJson(
            geo_rich,
            style_function=style_fn,
            highlight_function=highlight_fn,
            tooltip=folium.GeoJsonTooltip(
                fields=["seccion", "Encuestas", "LN corte 500", "% Cubierta"],
                aliases=["Sección", "Encuestas", "LN corte 500", "% Cubierta"],
                sticky=True, labels=True,
                style="font-family:'DM Sans',sans-serif; font-size:12.5px; background:#1b212b; "
                      "color:#eef1f0; border:1px solid #3a4255; border-radius:6px;",
                max_width=240,
            ),
            name="secciones",
        ).add_to(m)

        map_out = st_folium(m, height=520, use_container_width=True, key=f"m3_map_{sel}")

        if map_out and map_out.get("last_active_drawing"):
            props = map_out["last_active_drawing"].get("properties", {})
            sec_click = props.get("seccion")
            if sec_click in lookup_resumen.index and sec_click != st.session_state["m3_sel_seccion"]:
                st.session_state["m3_sel_seccion"] = sec_click
                st.rerun()

    with col_card:
        r = lookup_resumen.loc[sel]
        color_pct = score_color(r["pct_ln_cubierta"], 0, 100)
        encuestadores_seccion = sorted(
            df_encuestas[df_encuestas["seccion_electoral"] == sel]["nombre_encuestador"].unique().tolist()
        )

        if r["ln_meta_500"] > 0:
            valor_principal = f"{int(r['encuestas'])} de {int(r['ln_meta_500'])}"
            etiqueta_principal = f"{fmt_pct(r['pct_ln_cubierta'])} de la LN corte 500 cubierta"
            ctx_ln = f"LN total de la sección: {int(r['ln_total_seccion']):,} (corte 500 = {int(r['ln_meta_500']):,})"
        else:
            valor_principal = f"{int(r['encuestas'])} encuestas"
            etiqueta_principal = "Sección sin universo LN por manzana (Modo B, barrido total)"
            ctx_ln = f"LN total de la sección: {int(r['ln_total_seccion']):,}"

        st.markdown(f"""
        <div class="card-wrap">
          <div style="background:linear-gradient(135deg,{COLOR['bg_raised_2']} 0%,{COLOR['bg_base']} 100%);
                      border:1px solid {COLOR['border_subtle']}; border-bottom:3px solid {color_pct};
                      border-radius:10px; padding:20px 24px;">
            <div style="font-family:'JetBrains Mono',monospace; font-size:.7rem; font-weight:700;
                        letter-spacing:.1em; text-transform:uppercase; color:{COLOR['text_secondary']}; margin-bottom:10px;">
              SECCIÓN {sel}
            </div>
            <div class="kpi-val" style="font-size:2rem;">{valor_principal}</div>
            <div class="kpi-label">{etiqueta_principal}</div>
            <div class="kpi-ctx" style="margin-top:6px;">{ctx_ln}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Encuestadores en esta sección**")
        if encuestadores_seccion:
            for enc in encuestadores_seccion:
                st.markdown(f"- {enc}")
        else:
            st.caption("Sin encuestas capturadas todavía en esta sección.")

        st.markdown("**Avance por semana operativa**")
        df_sec_sem = (
            df_encuestas_full[df_encuestas_full["seccion_electoral"] == sel]
            .groupby("semana_operativo").size().reset_index(name="Encuestas")
            .rename(columns={"semana_operativo": "Semana"})
        )
        if not df_sec_sem.empty:
            st.dataframe(df_sec_sem, hide_index=True, use_container_width=True)
        else:
            st.caption("Sin historial todavía.")

    st.markdown("---")
    st.markdown("### Todas las secciones")
    st.caption("Encuestas capturadas y % de LN corte 500 cubierta, todas las secciones del plan.")

    tabla_secciones = resumen.copy().sort_values("pct_ln_cubierta", ascending=False, na_position="last")
    tabla_secciones_fmt = tabla_secciones[["seccion", "encuestas", "ln_meta_500", "pct_ln_cubierta"]].rename(
        columns={
            "seccion": "Sección", "encuestas": "Encuestas",
            "ln_meta_500": "LN corte 500", "pct_ln_cubierta": "% LN cubierta",
        }
    )
    st.dataframe(
        tabla_secciones_fmt,
        use_container_width=True,
        hide_index=True,
        column_config={
            "% LN cubierta": st.column_config.ProgressColumn(
                "% LN cubierta", min_value=0, max_value=100, format="%.1f%%",
            ),
        },
    )

# ── TAB 2 — Encuestadores ───────────────────────────────────────────────────
with tab_encuestadores:
    st.markdown("### Ranking de encuestadores")
    if modo_vista == "Acumulado a la fecha":
        periodo_txt = "acumulado a la fecha"
    elif modo_vista == "Solo esta semana":
        periodo_txt = semana_sel
    else:
        periodo_txt = f"{dia_sel}"
    st.caption(f"Periodo: {periodo_txt}")

    ranking_enc = (
        df_encuestas.groupby("nombre_encuestador")
        .agg(
            total_encuestas=("id_unico", "count"),
            secciones_cubiertas=("seccion_electoral", "nunique"),
            duracion_prom=("duracion_min", "mean"),
            ultima_captura=("fecha_creacion", "max"),
        )
        .reset_index()
        .sort_values("total_encuestas", ascending=False)
    )
    ranking_enc["ultima_semana_activa"] = ranking_enc["ultima_captura"].apply(semana_operativo)
    ranking_enc["duracion_prom"] = ranking_enc["duracion_prom"].round(1)

    tabla_enc = ranking_enc[[
        "nombre_encuestador", "total_encuestas", "secciones_cubiertas",
        "duracion_prom", "ultima_semana_activa",
    ]].rename(columns={
        "nombre_encuestador": "Encuestador", "total_encuestas": "Total encuestas",
        "secciones_cubiertas": "Secciones cubiertas", "duracion_prom": "Duración prom. (min)",
        "ultima_semana_activa": "Última semana activa",
    })

    st.dataframe(
        tabla_enc,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total encuestas": st.column_config.ProgressColumn(
                "Total encuestas", min_value=0,
                max_value=int(tabla_enc["Total encuestas"].max()), format="%d",
            ),
        },
    )

# ── TAB 3 — Resultados preliminares ─────────────────────────────────────────
with tab_resultados:
    st.markdown("### Tabulación preliminar — Arturo Solano Escobedo")
    if modo_vista == "Acumulado a la fecha":
        _periodo_txt = "acumulado"
    elif modo_vista == "Solo esta semana":
        _periodo_txt = semana_sel
    else:
        _periodo_txt = f"{dia_sel}"
    st.caption(
        f"Base: {len(df_encuestas)} entrevistas de inducción ({_periodo_txt}). "
        "Resultado preliminar de campo, no ponderado — no comparable directamente "
        "con la encuesta de referencia (base_maestra), que sí usa PESO_CAL."
    )

    def card_pregunta(titulo: str, columna: str, orden: list[str]):
        respuestas_col = df_encuestas[columna]
        n_base = respuestas_col.notna().sum()
        n_total = len(df_encuestas)
        conteo = respuestas_col.value_counts(normalize=True).reindex(orden).fillna(0) * 100
        st.markdown(f"**{titulo}**")
        st.caption(f"Base: {n_base} de {n_total} encuestas respondieron esta pregunta.")
        if n_base == 0:
            st.caption("Sin respuestas todavía para esta pregunta en el periodo seleccionado.")
            return
        for opcion in orden:
            pct = conteo.get(opcion, 0)
            st.markdown(f"""
            <div style="margin-bottom:8px;">
              <div style="display:flex; justify-content:space-between; font-size:.82rem; color:{COLOR['text_secondary']};">
                <span>{opcion}</span><span style="font-family:'JetBrains Mono',monospace;">{pct:.1f}%</span>
              </div>
              <div style="background:{COLOR['bg_raised_2']}; border-radius:4px; height:8px; overflow:hidden;">
                <div style="width:{pct:.1f}%; background:{COLOR['amber']}; height:100%;"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    def lista_otros(titulo: str, columna: str):
        """Para especificaciones de texto libre ('Otro'): no tiene sentido una
        barra por opción — se muestra conteo + muestra de respuestas."""
        respuestas = df_encuestas[columna].replace("", np.nan).dropna()
        st.markdown(f"**{titulo}**")
        st.markdown(f"""
        <div class="kpi-val" style="font-size:1.3rem;">{len(respuestas)}</div>
        <div class="kpi-ctx" style="margin-bottom:8px;">especificaciones de texto libre recibidas</div>
        """, unsafe_allow_html=True)
        if len(respuestas):
            with st.expander("Ver respuestas"):
                for txt in respuestas.unique()[:20]:
                    st.markdown(f"- {txt}")
        else:
            st.caption("Sin especificaciones registradas en el periodo.")

    # ── KPIs principales ────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        card_pregunta(
            "Reconocimiento", "conocimiento_arturo",
            ["Sí", "No", "No respondió"],
        )
    with c2:
        card_pregunta(
            "Buena candidatura", "buena_candidatura_arturo",
            ["Sí", "No", "No sabe (NO LEER)"],
        )
    with c3:
        card_pregunta(
            "Disposición a votar", "votar_o_no_arturo",
            ["Votaría", "Nunca votaría", "No sabe (NO LEER)"],
        )

    # ── Programas ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Programas")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        card_pregunta("Conocimiento del Programa Amor Puebla", "amor_puebla",
                      ["Sí", "No"])
    with p2:
        card_pregunta("Nivel de percepción de inseguridad", "percepcion_inseguridad",
                      ["Mucho", "Algo", "Poco"])
    with p3:
        card_pregunta("Aceptación de comités de vigilancia", "comite_vigilancia",
                      ["Sí", "No", "No sabe (NO LEER)"])
    with p4:
        card_pregunta("Valoración de las alarmas vecinales", "alarma_vecinal",
                      ["Mucho", "Algo", "Nada"])

    # ── Atributos ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Atributos")
    a1, a2, a3 = st.columns(3)
    with a1:
        card_pregunta("Percepción de cumplimiento de Arturo Solano Escobedo",
                      "cumplimiento_arturo", ["Mucho", "Algo", "Poco", "Nada"])
    with a2:
        card_pregunta("Percepción de honestidad de Arturo Solano Escobedo",
                      "honestidad_arturo", ["Mucho", "Algo", "Poco"])
    with a3:
        card_pregunta(
            "Percepción de votar o nunca votar de Arturo Solano Escobedo",
            "votar_o_no_arturo",
            ["Votaría", "Nunca votaría", "No sabe (NO LEER)"],
        )

    # ── Problemáticas ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Problemáticas")
    q1, q2 = st.columns(2)
    with q1:
        card_pregunta("Principal problema del estado", "principal_problema_estado_opciones",
                      ["Inseguridad", "Bajos salarios", "Calles en mal estado",
                       "Mala calidad de la educación pública",
                       "Mantenimiento y reparación del alumbrado público",
                       "Migración", "Otra ESPECIFICAR"])
        lista_otros("Especificación de otro problema del estado", "principal_problema_estado_otro")
    with q2:
        df_solo_inseguridad = df_encuestas[df_encuestas["principal_problema_estado_opciones"] == "Inseguridad"]
        st.markdown("**Principal tipo de inseguridad**")
        st.caption(f"Solo entre quienes respondieron \"Inseguridad\" arriba (n={len(df_solo_inseguridad)}).")
        if len(df_solo_inseguridad):
            n_base_tipo = df_solo_inseguridad["tipo_inseguridad_opciones"].notna().sum()
            st.caption(f"Base: {n_base_tipo} de {len(df_solo_inseguridad)} respondieron esta pregunta.")
            orden_tipo = ["Asaltos en vía pública y transporte", "No sabe"]
            conteo_tipo = (
                df_solo_inseguridad["tipo_inseguridad_opciones"]
                .value_counts(normalize=True).reindex(orden_tipo).fillna(0) * 100
            )
            for opcion in orden_tipo:
                pct = conteo_tipo.get(opcion, 0)
                st.markdown(f"""
                <div style="margin-bottom:8px;">
                  <div style="display:flex; justify-content:space-between; font-size:.82rem; color:{COLOR['text_secondary']};">
                    <span>{opcion}</span><span style="font-family:'JetBrains Mono',monospace;">{pct:.1f}%</span>
                  </div>
                  <div style="background:{COLOR['bg_raised_2']}; border-radius:4px; height:8px; overflow:hidden;">
                    <div style="width:{pct:.1f}%; background:{COLOR['amber']}; height:100%;"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("Sin registros en el periodo seleccionado.")
        lista_otros("Especificación de otro problema de inseguridad", "tipo_inseguridad_otro")

    # ── Datos de contacto recopilados ───────────────────────────────────────
    st.markdown("---")
    st.markdown("### Datos de contacto recopilados")
    st.caption(
        "Solo se muestran totales — el nombre, celular y correo del encuestado "
        "nunca se exponen aquí ni en ninguna otra vista del módulo."
    )
    cc1, cc2 = st.columns(2)
    total_base = len(df_encuestas)
    with cc1:
        n_cel = int(df_encuestas["tiene_celular"].sum())
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-val">{n_cel} de {total_base}</div>
          <div class="kpi-label">Celulares capturados</div>
          <div class="kpi-ctx">{fmt_pct(n_cel / total_base * 100 if total_base else 0)} de la base</div>
        </div>
        """, unsafe_allow_html=True)
    with cc2:
        n_mail = int(df_encuestas["tiene_email"].sum())
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-val">{n_mail} de {total_base}</div>
          <div class="kpi-label">Correos capturados</div>
          <div class="kpi-ctx">{fmt_pct(n_mail / total_base * 100 if total_base else 0)} de la base</div>
        </div>
        """, unsafe_allow_html=True)