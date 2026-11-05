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
import folium
from folium.plugins import Fullscreen, HeatMap
from streamlit_folium import st_folium

# El despliegue es de varios archivos y app_utils.py es el que más fácil se
# queda atrás: un ImportError aquí llega al usuario como un stack trace
# redactado que no dice qué falta. Se atrapa para decirlo en claro.
try:
    from app_utils import (  # noqa: E402
    GLOBAL_CSS, COLOR, check_password, fmt_num, fmt_pct,
    load_kobo_tablas, limpiar_cache_kobo, load_m1_secciones, meta_de_seccion,
    ahora_mexico, META_POR_BRIGADISTA, META_DIARIA_EQUIPO,
    BRIGADISTAS_ESPERADOS, RESULTADOS_QUE_CUENTAN, personas_impactadas,
    HABITANTES_PROMEDIO_VIVIENDA, PCT_IMPACTO_META, load_m1_contornos,
    UMBRAL_DURACION_RAPIDA_MIN, MIN_RACHA_RAPIDA,
    RESULTADO_MAPA, categoria_resultado, carto_tiles, CARTO_ATTR,
    )
except ImportError as _exc:  # pragma: no cover
    import streamlit as _st
    _st.set_page_config(page_title="M3 · error de versión", page_icon="⚠️", layout="wide")
    _st.error(
        f"**`app_utils.py` está desactualizado.** Esta página necesita algo que "
        f"la versión desplegada no tiene:\n\n`{_exc}`\n\n"
        "Copia `app_utils.py` de la misma entrega que esta página, commitéalo y "
        "haz push. Suele pasar cuando se actualiza una página y no el módulo "
        "compartido.",
        icon="🧩",
    )
    _st.stop()

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
gps = tablas.get("supervision_gps_privado", pd.DataFrame())

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
    (k[1], fmt_num(personas_impactadas(ENTREVISTAS)), "Personas impactadas",
     f"{fmt_num(VISITAS)} visitas · "
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
    f"La meta de cada sección sale de su propia lista nominal: una visita es a "
    f"una vivienda e impacta a {HABITANTES_PROMEDIO_VIVIENDA} personas en "
    f"promedio, así que la meta son las entrevistas necesarias para alcanzar al "
    f"{int(PCT_IMPACTO_META*100)}% de sus electores. Suma "
    f"{fmt_num(META_TOTAL)} entrevistas en las 70 secciones operativas. "
    f"Entrevista = visita con contacto real (completa o parcial); un rechazo o "
    f"una casa sola cuentan como visita, no como entrevista."
)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 2 — GEORREFERENCIA
# ════════════════════════════════════════════════════════════════════════════
# Dos niveles, como en Zacatlán: primero densidad del municipio, que no
# identifica domicilios; luego, al elegir una sección, los puntos individuales
# para verificar el recorrido. El detalle exige un acto deliberado.

st.markdown("## Dónde se trabajó")

if gps.empty:
    st.info(
        "**No hay visitas con GPS registrado.** El campo de ubicación es "
        "opcional en el instrumento: si los brigadistas lo omiten o el teléfono "
        "no fija posición, la visita se captura igual pero sin coordenadas.\n\n"
        "Para confirmar si es eso o si las coordenadas se están perdiendo en el "
        "camino, corre `python3 diagnostico_gps.py` desde la raíz del repo: "
        "dice en qué forma manda Kobo la ubicación y cuántas visitas la traen."
    )
else:
    gps = gps.copy()
    for c in ("latitud", "longitud"):
        gps[c] = pd.to_numeric(gps[c], errors="coerce")
    gps = gps[gps["latitud"].notna() & gps["longitud"].notna()]

    # El resultado y el volante viven en visitas_operativas: se unen por
    # registro_id, que es la llave estable del conector.
    gps = gps.merge(
        visitas[["registro_id", "resultado", "entrega_volante",
                 "inicio", "gps_precision_m"]],
        on="registro_id", how="left",
    )
    gps["categoria"] = gps["resultado"].map(categoria_resultado)

    fechas = sorted(gps["fecha_visita"].dropna().unique(), reverse=True)
    g1, g2 = st.columns([2, 3])
    with g1:
        f_sel = st.selectbox(
            "Día", ["Todo el operativo"] + list(fechas),
            help="Todo el operativo para ver zonas de trabajo y de rechazo; "
                 "un día concreto para verificar el recorrido de esa jornada.",
        )
    gps_v = gps if f_sel == "Todo el operativo" else gps[gps["fecha_visita"] == f_sel]
    with g2:
        st.markdown(
            f"<div style='padding-top:30px;font-size:.84rem;color:"
            f"{COLOR['text_secondary']}'>{len(gps_v):,} visitas con ubicación "
            f"de {len(visitas):,} capturadas"
            f"<span style='color:{COLOR['text_muted']}'> &nbsp;·&nbsp; "
            f"{len(visitas) - len(gps):,} sin GPS</span></div>",
            unsafe_allow_html=True,
        )

    if gps_v.empty:
        st.caption("Sin visitas georreferenciadas en ese día.")
    else:
        centro = [gps_v["latitud"].mean(), gps_v["longitud"].mean()]
        secciones_gps = sorted(gps_v["seccion_operativa"].astype(str).unique(),
                               key=lambda x: int(x) if str(x).isdigit() else 0)
        sec_sel = st.selectbox(
            "Ver los puntos de una sección",
            ["(solo el mapa de calor)"] + secciones_gps,
            help="El mapa de calor muestra densidad sin identificar domicilios. "
                 "Al elegir una sección se dibujan los puntos individuales.",
        )

        mapa = folium.Map(location=centro, zoom_start=13,
                          tiles=carto_tiles(), attr=CARTO_ATTR)
        Fullscreen(position="topleft", title="Pantalla completa",
                   title_cancel="Salir").add_to(mapa)

        # Contorno de las secciones como referencia: sin él, el mapa de calor
        # es una mancha sin saber a qué territorio corresponde. Va debajo de
        # los datos, sin relleno y en línea delgada, para no competir.
        folium.GeoJson(
            load_m1_contornos(),
            name="Secciones",
            style_function=lambda f: {
                "fillOpacity": 0, "color": COLOR["border_strong"], "weight": 1,
            },
            highlight_function=lambda f: {
                "color": "#ffffff", "weight": 2, "fillOpacity": 0.05,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["secciones_vigentes", "capa_ln", "ranking_ire"],
                aliases=["Sección(es):", "Capa de LN:", "Prioridad #:"],
            ),
        ).add_to(mapa)

        if sec_sel == "(solo el mapa de calor)":
            HeatMap(
                gps_v[["latitud", "longitud"]].values.tolist(),
                radius=18, blur=22, min_opacity=0.35,
            ).add_to(mapa)
            leyenda = None
        else:
            pts = gps_v[gps_v["seccion_operativa"].astype(str) == sec_sel].copy()
            pts = pts.sort_values("inicio")
            # Forma además de color: el color nunca carga la identidad solo.
            for _, r in pts.iterrows():
                cfg = RESULTADO_MAPA[r["categoria"]]
                hora = str(r.get("inicio") or "")[11:16]
                folium.CircleMarker(
                    location=[r["latitud"], r["longitud"]],
                    radius=6 if cfg["relleno"] else 7,
                    color=cfg["color"],
                    weight=2 if cfg["relleno"] else 2.5,
                    fill=cfg["relleno"],
                    fill_color=cfg["color"],
                    fill_opacity=0.75 if cfg["relleno"] else 0,
                    tooltip=folium.Tooltip(
                        f"<b>{cfg['etiqueta']}</b><br>"
                        f"Resultado: {r.get('resultado', '—')}<br>"
                        f"Volante: {r.get('entrega_volante', '—')}<br>"
                        f"Brigadista: {r.get('brigadista', '—')}<br>"
                        f"{r.get('fecha_visita', '')} {hora}<br>"
                        f"Precisión: {r.get('gps_precision_m', '—')} m"
                    ),
                ).add_to(mapa)
            leyenda = pts["categoria"].value_counts().to_dict()

        m1c, m2c = st.columns([4, 1])
        with m1c:
            st_folium(mapa, height=620, use_container_width=True,
                      returned_objects=[],
                      key=f"m3_gps_{f_sel}_{sec_sel}_{len(gps_v)}")
        with m2c:
            if leyenda is None:
                st.markdown("**Mapa de calor**")
                st.caption(
                    "Densidad de visitas sobre el contorno de las secciones. "
                    "No identifica domicilios: sirve para ver dónde se "
                    "concentró el trabajo. Elige una sección arriba para ver "
                    "los puntos, y el botón de la esquina superior izquierda "
                    "para pantalla completa."
                )
            else:
                st.markdown("**Resultado de la visita**")
                for clave, cfg in RESULTADO_MAPA.items():
                    n = leyenda.get(clave, 0)
                    marca = ("●" if cfg["relleno"] else "○")
                    st.markdown(
                        f"<div style='font-size:.82rem;margin-bottom:6px'>"
                        f"<span style='color:{cfg['color']};font-size:1.1rem'>"
                        f"{marca}</span> {cfg['etiqueta']} · "
                        f"<b>{n}</b></div>", unsafe_allow_html=True)
                st.caption(
                    f"Sección {sec_sel}, {len(pts)} puntos. El relleno distingue "
                    f"las categorías además del color. Pasa el cursor sobre un "
                    f"punto para ver resultado, volante, brigadista y hora."
                )

    st.caption(
        "Estas son ubicaciones de domicilios visitados. No se exportan a "
        "archivo ni salen del tablero, que está restringido al equipo de "
        "coordinación."
    )


# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 3 — SEÑAL DE CAMPO (q01)
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
# BLOQUE 4 — PRODUCTIVIDAD POR BRIGADISTA
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

st.dataframe(
        por_brig.rename(columns={
        "brigadista_codigo": "Código", "brigadista": "Brigadista",
        "dias": "Días", "visitas": "Visitas", "entrevistas": "Entrevistas",
        "rechazos": "Rechazos", "casas_solas": "Casas solas",
        "volantes": "Volantes", "por_dia": "Por día", "vs_meta": "% de meta",
    }),
    use_container_width=True, hide_index=True, height=420,
)
st.caption(
    f"Referencia: {META_POR_BRIGADISTA} entrevistas por brigadista al día. Es "
    f"una referencia de planeación, no un umbral de evaluación: un día en "
    f"sección rural dispersa rinde menos que uno en el centro."
)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 5 — PRODUCCIÓN POR DÍA
# ════════════════════════════════════════════════════════════════════════════

st.markdown("## Producción por día")

# Una sola serie: entrevistas por día contra la meta diaria del equipo. La
# pregunta que este gráfico contesta es "¿vamos al ritmo?", y eso se lee de un
# vistazo con una barra y una línea. El desglose por resultado vive en la tabla
# de abajo, que es donde se consulta cuando hace falta.
META_DIARIA = META_DIARIA_EQUIPO

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
# BLOQUE 6 — DÓNDE SE TRABAJA HOY
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
# BLOQUE 7 — CALIDAD E INTEGRIDAD
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
    corregidas = int(estado.get("visitas_con_seccion_corregida", 0) or 0)
    rescatado = int(estado.get("gps_rescatado_de_geolocation", 0) or 0)
    por_gps = int(estado.get("seccion_corregida_por_gps", 0) or 0)
    sin_coord = int(estado.get("gps_sin_coordenada_para_corregir", 0) or 0)
    fuera_poli = int(estado.get("gps_fuera_de_todo_poligono", 0) or 0)
    no_permitido = int(estado.get("gps_destino_no_permitido", 0) or 0)
    sin_seccion = int(estado.get("visitas_sin_seccion_valida", 0) or 0)
    filas = [
        ("Registros únicos", fmt_num(estado.get("registros_unicos", 0))),
        ("Duplicados de identificador", fmt_num(estado.get("duplicados_identificador", 0))),
        ("Visitas sin GPS", fmt_num(estado.get("visitas_sin_gps", 0))),
        ("Resultados sin clasificar", fmt_num(estado.get("registros_sin_clasificar", 0))),
        ("Visitas sin sección válida", fmt_num(sin_seccion)),
        ("Visitas con sección reasignada", fmt_num(corregidas)),
        ("  de ellas, por ubicación real", fmt_num(por_gps)),
        ("Sin GPS para verificar sección", fmt_num(sin_coord)),
        ("GPS fuera de todo polígono", fmt_num(fuera_poli)),
        ("Destino descartado por la regla", fmt_num(no_permitido)),
        ("GPS recuperado de _geolocation", fmt_num(rescatado)),
    ]
    st.dataframe(pd.DataFrame(filas, columns=["Indicador", "n"]),
                 use_container_width=True, hide_index=True)
    if sin_coord:
        st.warning(
            f"{sin_coord} visita(s) bajo una regla de corrección por GPS no "
            f"traen coordenada, así que se quedaron con la sección que declaró "
            f"el brigadista. No se adivinan.",
            icon="⚠️",
        )
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
