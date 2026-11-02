"""
M3 — ¿Cómo vamos en campo?
PIE Atlixco · Arturo Solano Escobedo · Operativo de inducción 2026

Sustituye al M3 anterior, que leía de Bubble. La fuente ahora es KoboToolbox
vía el conector del paquete v1.2, consultado como librería.

División de trabajo con M1: M1 responde a dónde mandar brigadas; M3 responde
cómo va el ejercicio. Por eso aquí NO se repite el coroplético de cobertura
acumulada — solo la actividad del día.

Sobre las respuestas del cuestionario: solo entra q01 (reconocimiento) y como
TENDENCIA DE CAMPO, no como medición. Este es un operativo de inducción, no
muestral: quien abre la puerta no es una muestra de nada, los datos no están
ponderados y el propio paquete del conector advierte que no permite inferencia
municipal probabilística. Las demás preguntas no se exponen — decisión tomada
en L3 y sostenida aquí: una captura de pantalla circula como definitiva y la
leyenda "preliminar" no sobrevive al screenshot.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st
import altair as alt

from app_utils import (
    GLOBAL_CSS, COLOR, check_password, fmt_num, fmt_pct,
    load_kobo_tablas, limpiar_cache_kobo, load_m1_secciones, meta_de_seccion,
    ahora_mexico, META_ENTREVISTAS_SECCION, META_POR_BRIGADISTA,
    BRIGADISTAS_ESPERADOS, RESULTADOS_QUE_CUENTAN,
    UMBRAL_DURACION_RAPIDA_MIN, MIN_RACHA_RAPIDA,
)

st.set_page_config(
    page_title="M3 · ¿Cómo vamos en campo? · PIE Atlixco",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)
check_password()

st.sidebar.markdown(
    f"<div style='font-family:\"JetBrains Mono\",monospace; font-size:.7rem; "
    f"color:{COLOR['text_muted']};'>Sesión: <b style='color:{COLOR['text_secondary']};'>"
    f"{st.session_state.get('auth_user','—')}</b></div>",
    unsafe_allow_html=True,
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

st.markdown("""
<div class="header-modulo">
  <div class="hm-dots"><span></span><span></span><span></span></div>
  <div class="hm-eyebrow">Módulo 03 · En operación</div>
  <h1>¿Cómo vamos en campo?</h1>
  <p>Pulso del operativo de inducción: cuánto se ha avanzado, a qué ritmo, quién
  está trabajando hoy y dónde. Los datos vienen en vivo de Kobo y solo incluyen
  los registros ya sincronizados — una visita capturada sin señal no aparece
  hasta que el teléfono se conecta.</p>
</div>
""", unsafe_allow_html=True)

tablas, estado, error = load_kobo_tablas()

col_a, col_b = st.columns([4, 1])
with col_b:
    if st.button("Actualizar", use_container_width=True,
                 help="Vuelve a consultar Kobo sin esperar al refresco."):
        limpiar_cache_kobo()
        st.rerun()

if error:
    st.error(
        f"**No se pudo leer Kobo.** No hay datos que mostrar. Esto no dice nada "
        f"sobre el avance en campo: las brigadas pueden estar trabajando "
        f"normalmente.\n\nDetalle: `{error}`",
        icon="🚫",
    )
    st.stop()

visitas = tablas.get("visitas_operativas", pd.DataFrame())
diario = tablas.get("resumen_diario", pd.DataFrame())
brigadistas = tablas.get("productividad_brigadista", pd.DataFrame())
cobertura = tablas.get("cobertura_seccion", pd.DataFrame())
respuestas = tablas.get("respuestas_agregadas", pd.DataFrame())

if visitas.empty:
    st.info(
        "Kobo respondió pero todavía no hay visitas sincronizadas. "
        "Si el operativo ya arrancó, revisa que los teléfonos hayan enviado y "
        "que el UID del formulario sea el del proyecto en operación."
    )
    st.stop()

for col in ("completas", "parciales", "rechazos", "casas_solas", "visitas"):
    if col in diario.columns:
        diario[col] = pd.to_numeric(diario[col], errors="coerce").fillna(0).astype(int)
    if col in brigadistas.columns:
        brigadistas[col] = pd.to_numeric(brigadistas[col], errors="coerce").fillna(0).astype(int)

diario["entrevistas"] = sum(diario[c] for c in RESULTADOS_QUE_CUENTAN
                            if c in diario.columns)
brigadistas["entrevistas"] = sum(brigadistas[c] for c in RESULTADOS_QUE_CUENTAN
                                 if c in brigadistas.columns)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 1 — PULSO DEL OPERATIVO
# ════════════════════════════════════════════════════════════════════════════

secciones = load_m1_secciones()
_ln_geom = secciones.groupby("seccion_geom")["LN_SECCION"].sum().to_dict()
META_TOTAL = sum(meta_de_seccion(ln) for ln in _ln_geom.values())

ENTREVISTAS = int(diario["entrevistas"].sum())
VISITAS = int(diario["visitas"].sum())
DIAS = int(diario["fecha_visita"].nunique())
HOY = ahora_mexico().date().isoformat()
hoy_fila = diario[diario["fecha_visita"] == HOY]
ENTREVISTAS_HOY = int(hoy_fila["entrevistas"].sum()) if not hoy_fila.empty else 0

ritmo = ENTREVISTAS / DIAS if DIAS else 0
faltan = max(0, META_TOTAL - ENTREVISTAS)
dias_restantes = round(faltan / ritmo) if ritmo else None

k = st.columns(4)
for col, val, lab, ctx in [
    (k[0], fmt_num(ENTREVISTAS), "Entrevistas acumuladas",
     f"{ENTREVISTAS / META_TOTAL * 100:.1f}% de la meta de {fmt_num(META_TOTAL)}"
     if META_TOTAL else ""),
    (k[1], fmt_num(VISITAS), "Visitas realizadas",
     f"{ENTREVISTAS / VISITAS * 100:.0f}% terminó en entrevista" if VISITAS else ""),
    (k[2], f"{ritmo:,.0f}", "Entrevistas por día",
     f"{DIAS} días de campo · hoy van {ENTREVISTAS_HOY}"),
    (k[3], fmt_num(faltan), "Faltan para la meta",
     f"~{dias_restantes} días a este ritmo" if dias_restantes else "meta alcanzada"),
]:
    col.markdown(
        f'<div class="kpi-card"><div class="kpi-val">{val}</div>'
        f'<div class="kpi-label">{lab}</div><div class="kpi-ctx">{ctx}</div></div>',
        unsafe_allow_html=True,
    )

st.caption(
    f"La meta total son {fmt_num(META_TOTAL)} entrevistas: "
    f"{META_ENTREVISTAS_SECCION} por sección operativa "
    f"({BRIGADISTAS_ESPERADOS} brigadistas × {META_POR_BRIGADISTA}), ajustada en "
    f"las secciones cuya lista nominal es menor que la meta. "
    f"Entrevista = visita con contacto real (completa o parcial); un rechazo o "
    f"una casa sola cuentan como visita, no como entrevista."
)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 2 — SERIE DIARIA
# ════════════════════════════════════════════════════════════════════════════

st.markdown("## Producción por día")

# Una sola serie: entrevistas por día contra la meta diaria del equipo. La
# pregunta que este gráfico contesta es "¿vamos al ritmo?", y eso se lee de un
# vistazo con una barra y una línea. El desglose por resultado vive en la tabla
# de abajo, que es donde se consulta cuando hace falta.
META_DIARIA = BRIGADISTAS_ESPERADOS * META_POR_BRIGADISTA

serie = diario.sort_values("fecha_visita").copy()
serie["fecha"] = pd.to_datetime(serie["fecha_visita"], errors="coerce")
serie["pct_meta"] = (serie["entrevistas"] / META_DIARIA * 100).round(0)

_eje = dict(grid=True, gridColor=COLOR["border_subtle"], gridOpacity=0.5,
            domainColor=COLOR["border_subtle"], tickColor=COLOR["border_subtle"],
            labelColor=COLOR["text_secondary"], titleColor=COLOR["text_muted"],
            labelFontSize=11, titleFontSize=11)

barras = (
    alt.Chart(serie)
    .mark_bar(color=COLOR["amber"], cornerRadiusEnd=4, size=22)
    .encode(
        x=alt.X("fecha:T", title=None, axis=alt.Axis(format="%d %b", **_eje)),
        y=alt.Y("entrevistas:Q", title="Entrevistas",
                axis=alt.Axis(**_eje)),
        tooltip=[
            alt.Tooltip("fecha:T", title="Día", format="%d %b %Y"),
            alt.Tooltip("entrevistas:Q", title="Entrevistas"),
            alt.Tooltip("pct_meta:Q", title="% de la meta diaria"),
            alt.Tooltip("visitas:Q", title="Visitas"),
            alt.Tooltip("rechazos:Q", title="Rechazos"),
            alt.Tooltip("casas_solas:Q", title="Casas solas"),
            alt.Tooltip("brigadistas_activos:Q", title="Brigadistas"),
        ],
    )
)

meta_linea = (
    alt.Chart(pd.DataFrame({"y": [META_DIARIA]}))
    .mark_rule(color=COLOR["text_secondary"], strokeDash=[5, 4], size=1.5)
    .encode(y="y:Q")
)
meta_texto = (
    alt.Chart(pd.DataFrame({"y": [META_DIARIA],
                            "t": [f"meta diaria {META_DIARIA}"]}))
    .mark_text(align="left", baseline="bottom", dx=4, dy=-4,
               color=COLOR["text_muted"], fontSize=11)
    .encode(y="y:Q", text="t:N")
)

st.altair_chart(
    (barras + meta_linea + meta_texto)
    .properties(height=320)
    .configure_view(strokeWidth=0, fill="transparent")
    .configure(background="transparent"),
    use_container_width=True,
)
st.caption(
    f"La meta diaria son {META_DIARIA} entrevistas: {BRIGADISTAS_ESPERADOS} "
    f"brigadistas × {META_POR_BRIGADISTA}. Pasa el cursor sobre una barra para "
    f"ver el desglose del día."
)

with st.expander("Ver la tabla por día", expanded=False):
    cols_dia = [c for c in ("fecha_visita", "visitas", "entrevistas", "completas",
                            "parciales", "rechazos", "casas_solas",
                            "brigadistas_activos", "secciones_visitadas",
                            "volantes_entregados", "tasa_entrega_pct")
                if c in serie.columns]
    st.dataframe(serie[cols_dia], use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 3 — PRODUCTIVIDAD POR BRIGADISTA
# ════════════════════════════════════════════════════════════════════════════

st.markdown("## Productividad por brigadista")

por_brig = (
    brigadistas.groupby(["brigadista_codigo", "brigadista"], as_index=False)
    .agg(dias=("fecha_visita", "nunique"), visitas=("visitas", "sum"),
         entrevistas=("entrevistas", "sum"), rechazos=("rechazos", "sum"),
         casas_solas=("casas_solas", "sum"),
         volantes=("volantes_entregados", "sum"))
    .sort_values("entrevistas", ascending=False)
)
por_brig["por_dia"] = (por_brig["entrevistas"] / por_brig["dias"]).round(1)
por_brig["vs_meta"] = (por_brig["por_dia"] / META_POR_BRIGADISTA * 100).round(0)

b1, b2 = st.columns([3, 2])
with b1:
    st.dataframe(
        por_brig.rename(columns={
            "brigadista_codigo": "Código", "brigadista": "Brigadista",
            "dias": "Días", "visitas": "Visitas", "entrevistas": "Entrevistas",
            "rechazos": "Rechazos", "casas_solas": "Casas solas",
            "volantes": "Volantes", "por_dia": "Por día", "vs_meta": "% de meta",
        }),
        use_container_width=True, hide_index=True, height=380,
    )
with b2:
    activos_hoy = brigadistas[brigadistas["fecha_visita"] == HOY]
    st.markdown(f"**Trabajando hoy ({HOY})**")
    if activos_hoy.empty:
        st.caption("Sin registros sincronizados con fecha de hoy.")
    else:
        for _, r in activos_hoy.sort_values("entrevistas", ascending=False).iterrows():
            pct = r["entrevistas"] / META_POR_BRIGADISTA if META_POR_BRIGADISTA else 0
            st.markdown(f"{r['brigadista']} · **{int(r['entrevistas'])}** de "
                        f"{META_POR_BRIGADISTA}")
            st.progress(min(1.0, pct))
    st.caption(
        f"Referencia: {META_POR_BRIGADISTA} entrevistas por brigadista al día. "
        f"Es una referencia de planeación, no un umbral de evaluación: un día "
        f"en sección rural dispersa rinde menos que uno en el centro."
    )

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 4 — DÓNDE ESTÁ EL EQUIPO HOY
# ════════════════════════════════════════════════════════════════════════════

st.markdown("## Dónde está el equipo hoy")

visitas_hoy = visitas[visitas["fecha_visita"] == HOY] if "fecha_visita" in visitas.columns else pd.DataFrame()
if visitas_hoy.empty:
    st.info(
        f"No hay visitas sincronizadas con fecha de hoy ({HOY}). Si el equipo "
        f"está en campo, puede ser que los teléfonos aún no hayan enviado: los "
        f"registros offline no aparecen hasta que hay señal."
    )
else:
    hoy_sec = (
        visitas_hoy.groupby("seccion_operativa", as_index=False)
        .agg(visitas=("registro_id", "count"),
             brigadistas=("brigadista", "nunique"))
        .sort_values("visitas", ascending=False)
    )
    hoy_sec["seccion_operativa"] = hoy_sec["seccion_operativa"].astype(str)
    h1, h2 = st.columns([2, 3])
    with h1:
        st.dataframe(
            hoy_sec.rename(columns={"seccion_operativa": "Sección",
                                    "visitas": "Visitas hoy",
                                    "brigadistas": "Brigadistas"}),
            use_container_width=True, hide_index=True,
        )
    with h2:
        st.markdown(
            f"**{len(hoy_sec)} sección(es) trabajándose hoy** · "
            f"{int(hoy_sec['visitas'].sum())} visitas · "
            f"{visitas_hoy['brigadista'].nunique()} brigadistas en campo"
        )
        st.caption(
            "El avance acumulado por sección y el mapa de prioridad están en el "
            "Módulo 1. Aquí solo se muestra la actividad del día."
        )

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 5 — TENDENCIA DE CAMPO (q01)
# ════════════════════════════════════════════════════════════════════════════

st.markdown("## Señal de campo · reconocimiento")

q01 = respuestas[respuestas["variable"] == "q01_reconocimiento"] if not respuestas.empty else pd.DataFrame()
if q01.empty:
    st.caption("Todavía no hay respuestas de la pregunta de reconocimiento.")
else:
    total = int(q01["n"].sum())
    q1, q2 = st.columns([2, 3])
    with q1:
        for _, r in q01.sort_values("n", ascending=False).iterrows():
            pct = r["n"] / total * 100 if total else 0
            st.markdown(f"**{str(r['codigo']).replace('_', ' ').capitalize()}** · "
                        f"{int(r['n'])} ({pct:.1f}%)")
            st.progress(min(1.0, pct / 100))
    with q2:
        st.warning(
            "**Esto no es una medición de opinión pública.** Es lo que reportan "
            "las personas que abrieron la puerta a una brigada, sin ponderar y "
            "sin diseño muestral. Sirve para ver si el reconocimiento se mueve "
            "conforme avanza el recorrido; no sirve para estimar nada a nivel "
            "municipio, ni para comparar con una encuesta. Las demás preguntas "
            "del cuestionario no se exponen aquí por la misma razón.",
            icon="⚠️",
        )

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 6 — CALIDAD E INTEGRIDAD
# ════════════════════════════════════════════════════════════════════════════

st.markdown("## Calidad e integridad")
st.caption(
    "Bloque interno de supervisión. No se comparte con las brigadas durante el "
    "operativo: señala dónde revisar, no quién lo hizo mal."
)

# Duración por visita, derivada de inicio/fin.
dur = visitas.copy()
for c in ("inicio", "fin"):
    dur[c] = pd.to_datetime(dur.get(c), errors="coerce", utc=True)
dur["minutos"] = (dur["fin"] - dur["inicio"]).dt.total_seconds() / 60
entrevistas_dur = dur[dur["resultado"].isin(("completa", "parcial"))
                      & dur["minutos"].notna()]

# Racha de capturas rápidas: N seguidas del mismo brigadista el mismo día bajo
# el umbral. Solo entrevistas — un rechazo de 30 segundos es lo normal.
rachas = []
for (brig, fecha), grupo in entrevistas_dur.sort_values("inicio").groupby(
        ["brigadista", "fecha_visita"]):
    corrida = 0
    for _, fila in grupo.iterrows():
        corrida = corrida + 1 if fila["minutos"] < UMBRAL_DURACION_RAPIDA_MIN else 0
        if corrida >= MIN_RACHA_RAPIDA:
            rachas.append({"brigadista": brig, "fecha": fecha, "seguidas": corrida})
rachas_df = (pd.DataFrame(rachas).groupby(["brigadista", "fecha"], as_index=False)
             .agg(seguidas=("seguidas", "max")) if rachas else pd.DataFrame())

incid = (visitas["incidencias"].fillna("").str.split(";").explode()
         .replace("", pd.NA).dropna().value_counts()
         if "incidencias" in visitas.columns else pd.Series(dtype=int))

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Integridad del extracto**")
    sin_seccion = int(estado.get("visitas_sin_seccion_valida", 0) or 0)
    filas = [
        ("Registros únicos", fmt_num(estado.get("registros_unicos", 0))),
        ("Duplicados de identificador", fmt_num(estado.get("duplicados_identificador", 0))),
        ("Visitas sin GPS", fmt_num(estado.get("visitas_sin_gps", 0))),
        ("Resultados sin clasificar", fmt_num(estado.get("registros_sin_clasificar", 0))),
        ("Visitas sin sección válida", fmt_num(sin_seccion)),
    ]
    st.dataframe(pd.DataFrame(filas, columns=["Indicador", "n"]),
                 use_container_width=True, hide_index=True)
    if sin_seccion:
        st.warning(
            f"{sin_seccion} visita(s) no suman a ninguna sección: se capturaron "
            f"con una sección fuera del catálogo de 70. Se identifican en Kobo "
            f"por la incidencia `seccion_fuera_catalogo`.",
            icon="⚠️",
        )
with c2:
    st.markdown("**Incidencias por visita**")
    if incid.empty:
        st.caption("Sin incidencias registradas.")
    else:
        st.dataframe(
            pd.DataFrame({"Incidencia": incid.index, "n": incid.values}),
            use_container_width=True, hide_index=True,
        )

st.markdown("**Rachas de capturas rápidas**")
if rachas_df.empty:
    st.caption(
        f"Ninguna. Se marca cuando hay {MIN_RACHA_RAPIDA} entrevistas seguidas "
        f"del mismo brigadista el mismo día por debajo de "
        f"{UMBRAL_DURACION_RAPIDA_MIN} minutos. Solo cuentan completas y "
        f"parciales: un rechazo corto es normal."
    )
else:
    st.dataframe(
        rachas_df.rename(columns={"brigadista": "Brigadista", "fecha": "Fecha",
                                  "seguidas": "Seguidas bajo el umbral"}),
        use_container_width=True, hide_index=True,
    )
    st.caption(
        f"Una entrevista corta aislada es plausible; {MIN_RACHA_RAPIDA} seguidas "
        f"bajo {UMBRAL_DURACION_RAPIDA_MIN} minutos merecen revisión. No es "
        f"prueba de nada por sí sola."
    )

if not entrevistas_dur.empty:
    with st.expander("Distribución de la duración de las entrevistas", expanded=False):
        st.caption(
            f"Mediana {entrevistas_dur['minutos'].median():.1f} min · "
            f"p10 {entrevistas_dur['minutos'].quantile(.10):.1f} · "
            f"p90 {entrevistas_dur['minutos'].quantile(.90):.1f} · "
            f"n = {len(entrevistas_dur):,}"
        )
        hist = (
            alt.Chart(entrevistas_dur[["minutos"]])
            .mark_bar(color=COLOR["steel"], cornerRadiusEnd=3)
            .encode(
                x=alt.X("minutos:Q", bin=alt.Bin(maxbins=40),
                        title="Minutos por entrevista", axis=alt.Axis(**_eje)),
                y=alt.Y("count():Q", title="Entrevistas", axis=alt.Axis(**_eje)),
                tooltip=[alt.Tooltip("count():Q", title="Entrevistas"),
                         alt.Tooltip("minutos:Q", bin=alt.Bin(maxbins=40),
                                     title="Duración")],
            )
        )
        umbral = (
            alt.Chart(pd.DataFrame({"x": [UMBRAL_DURACION_RAPIDA_MIN]}))
            .mark_rule(color=COLOR["red_soft"], strokeDash=[4, 3], size=1.5)
            .encode(x="x:Q")
        )
        st.altair_chart(
            (hist + umbral).properties(height=260)
            .configure_view(strokeWidth=0, fill="transparent")
            .configure(background="transparent"),
            use_container_width=True,
        )
        st.caption(
            f"La línea marca el umbral de {UMBRAL_DURACION_RAPIDA_MIN} minutos "
            f"que alimenta la racha de capturas rápidas."
        )

gen = estado.get("generado_utc", "")
if gen:
    try:
        from zoneinfo import ZoneInfo
        local = datetime.fromisoformat(gen).astimezone(ZoneInfo("America/Mexico_City"))
        st.caption(f"Extracto generado {local:%d/%m/%Y %H:%M} hora local. "
                   f"Solo incluye envíos ya sincronizados desde los teléfonos.")
    except Exception:
        st.caption("Solo incluye envíos ya sincronizados desde los teléfonos.")
