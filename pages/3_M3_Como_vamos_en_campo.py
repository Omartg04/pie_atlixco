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
_dias_validos = diario["fecha_visita"].astype(str).str.strip()
DIAS = int(_dias_validos[_dias_validos != ""].nunique())
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
# Puntos por defecto, mapa de calor como opción (decisión del 11/11/2026). Con
# los filtros de día, brigadista y sección se revisa el recorrido de una
# jornada o de una persona. Son ubicaciones de domicilios visitados: el tablero
# está tras contraseña y no se exportan.

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
    gps["categoria"] = [categoria_resultado(r, v) for r, v in
                        zip(gps["resultado"], gps["entrega_volante"])]
    gps["seccion_operativa"] = gps["seccion_operativa"].astype(str)

    def _orden_sec(x):
        return int(x) if str(x).isdigit() else 10**9

    TODO_OP, TODO_EQ, TODAS = "Todo el operativo", "Todo el equipo", "Todas"
    f1, f2, f3 = st.columns(3)
    with f1:
        fechas = sorted((f for f in gps["fecha_visita"].dropna().astype(str).unique()
                         if f.strip()), reverse=True)
        f_sel = st.selectbox("Día", [TODO_OP] + list(fechas), key="m3_mapa_dia")
    base = gps if f_sel == TODO_OP else gps[gps["fecha_visita"] == f_sel]
    with f2:
        nombres = sorted(base["brigadista"].dropna().astype(str).unique())
        b_sel = st.selectbox("Brigadista", [TODO_EQ] + nombres, key="m3_mapa_brig")
    if b_sel != TODO_EQ:
        base = base[base["brigadista"].astype(str) == b_sel]
    with f3:
        secs = sorted(base["seccion_operativa"].unique(), key=_orden_sec)
        s_sel = st.selectbox("Sección", [TODAS] + secs, key="m3_mapa_sec")
    if s_sel != TODAS:
        base = base[base["seccion_operativa"] == s_sel]

    o1, o2 = st.columns([2, 3])
    with o1:
        vista = st.radio("Vista", ["Puntos", "Mapa de calor"], horizontal=True,
                         key="m3_mapa_vista",
                         help="Puntos: cada visita con su resultado. Mapa de "
                              "calor: densidad, sin identificar domicilios.")
    with o2:
        n_cs = int((base["categoria"] == "casa_sola").sum())
        ver_cs = st.checkbox(
            f"Mostrar casas solas ({n_cs:,} en esta selección)",
            value=False, key="m3_mapa_cs",
            help="Se capturaron hasta el 10 de noviembre. Sirven para ver dónde "
                 "quedaron puertas sin abrir si se decide regresar.",
        )
    gps_v = base if ver_cs else base[base["categoria"] != "casa_sola"]

    # Cuántas visitas de la misma selección no tienen GPS: sin esto, un mapa
    # vacío o ralo se lee como poco trabajo cuando es falta de ubicación.
    sel_vis = visitas.copy()
    if f_sel != TODO_OP:
        sel_vis = sel_vis[sel_vis["fecha_visita"] == f_sel]
    if b_sel != TODO_EQ:
        sel_vis = sel_vis[sel_vis["brigadista"].astype(str) == b_sel]
    if s_sel != TODAS:
        sel_vis = sel_vis[sel_vis["seccion_operativa"].astype(str) == s_sel]
    if not ver_cs:
        sel_vis = sel_vis[sel_vis["resultado"] != "casa_sola"]
    sin_gps_sel = max(0, len(sel_vis) - len(gps_v))
    st.markdown(
        f"<div style='font-size:.84rem;color:{COLOR['text_secondary']};"
        f"margin:-4px 0 8px'>{len(gps_v):,} visitas con ubicación"
        f"<span style='color:{COLOR['text_muted']}'> &nbsp;·&nbsp; "
        f"{sin_gps_sel:,} de la misma selección sin GPS, que no aparecen en el "
        f"mapa</span></div>",
        unsafe_allow_html=True,
    )

    if gps_v.empty:
        st.caption("Sin visitas georreferenciadas con esos filtros.")
    else:
        centro = [gps_v["latitud"].mean(), gps_v["longitud"].mean()]
        mapa = folium.Map(location=centro, zoom_start=13,
                          tiles=carto_tiles(), attr=CARTO_ATTR)
        Fullscreen(position="topleft", title="Pantalla completa",
                   title_cancel="Salir").add_to(mapa)

        # Contorno de las secciones como referencia, debajo de los datos, sin
        # relleno y en línea delgada para no competir.
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

        if vista == "Mapa de calor":
            HeatMap(gps_v[["latitud", "longitud"]].values.tolist(),
                    radius=18, blur=22, min_opacity=0.35).add_to(mapa)
        else:
            # Orden de dibujo: lo que menos importa abajo. Casas solas, luego
            # rechazos, y las entrevistas encima.
            capas = ["casa_sola", "rechazo_sin_volante", "rechazo_volante", "entrevista"]
            for cat in capas:
                cfg = RESULTADO_MAPA[cat]
                for _, r in gps_v[gps_v["categoria"] == cat].iterrows():
                    hora = str(r.get("inicio") or "")[11:16]
                    folium.CircleMarker(
                        location=[r["latitud"], r["longitud"]],
                        radius=cfg["radio"] if cfg["relleno"] else cfg["radio"] + 1,
                        color=cfg["color"],
                        weight=2 if cfg["relleno"] else 2.5,
                        fill=cfg["relleno"], fill_color=cfg["color"],
                        fill_opacity=0.75 if cfg["relleno"] else 0,
                        tooltip=folium.Tooltip(
                            f"<b>{cfg['etiqueta']}</b><br>"
                            f"Resultado: {r.get('resultado', '—')}<br>"
                            f"Brigadista: {r.get('brigadista', '—')}<br>"
                            f"Sección: {r.get('seccion_operativa', '—')}<br>"
                            f"{r.get('fecha_visita', '')} {hora}<br>"
                            f"Precisión: {r.get('gps_precision_m', '—')} m"
                        ),
                    ).add_to(mapa)
        # Siempre al área con puntos: con un zoom fijo de municipio, cientos de
        # visitas en una sección se amontonan en una mancha.
        mapa.fit_bounds([[gps_v["latitud"].min(), gps_v["longitud"].min()],
                         [gps_v["latitud"].max(), gps_v["longitud"].max()]],
                        padding=(20, 20))

        m1c, m2c = st.columns([4, 1])
        with m1c:
            st_folium(mapa, height=620, use_container_width=True,
                      returned_objects=[],
                      key=f"m3_gps_{f_sel}_{b_sel}_{s_sel}_{vista}_{ver_cs}_{len(gps_v)}")
        with m2c:
            if vista == "Mapa de calor":
                st.markdown("**Mapa de calor**")
                st.caption(
                    "Densidad de visitas sobre el contorno de las secciones. "
                    "No identifica domicilios. Cambia a «Puntos» para ver el "
                    "resultado de cada visita."
                )
            else:
                st.markdown("**Resultado de la visita**")
                conteo = gps_v["categoria"].value_counts().to_dict()
                for clave, cfg in RESULTADO_MAPA.items():
                    if clave == "casa_sola" and not ver_cs:
                        continue
                    marca = "●" if cfg["relleno"] else "○"
                    st.markdown(
                        f"<div style='font-size:.82rem;margin-bottom:6px'>"
                        f"<span style='color:{cfg['color']};font-size:1.1rem'>"
                        f"{marca}</span> {cfg['etiqueta']} · "
                        f"<b>{conteo.get(clave, 0):,}</b></div>",
                        unsafe_allow_html=True)
                rv = conteo.get("rechazo_volante", 0)
                rs = conteo.get("rechazo_sin_volante", 0)
                if rv + rs:
                    st.caption(
                        f"El protocolo pide volante también a quien rechaza: "
                        f"aquí lo recibió {rv / (rv + rs) * 100:.0f}% de los "
                        f"rechazos con ubicación."
                    )
                st.caption("Relleno y tamaño distinguen las categorías además "
                           "del color. Pasa el cursor sobre un punto para el "
                           "detalle; esquina superior izquierda para pantalla "
                           "completa.")

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

# Una fila de productividad_brigadista es un brigadista en un día. La vista de
# equipo colapsa la fecha; la vista individual la conserva. Solo cuentan
# fechas reales: una fecha vacía no es una jornada (ver nota de DIAS arriba).
for col in ("volantes_entregados",):
    if col in brigadistas.columns:
        brigadistas[col] = pd.to_numeric(brigadistas[col], errors="coerce").fillna(0).astype(int)
brigadistas["fecha_visita"] = brigadistas["fecha_visita"].astype(str).str.strip()
brig_fechadas = brigadistas[brigadistas["fecha_visita"] != ""].copy()

# Jornadas del equipo: los días en que alguien capturó. Es la misma secuencia
# que numera la gráfica de producción por día, así que "jornada 3" significa
# lo mismo en los dos bloques.
_f_equipo = pd.to_datetime(
    diario["fecha_visita"].astype(str).str.strip(), errors="coerce").dropna()
JORNADAS = sorted(_f_equipo.dt.date.unique())

_claves = (brig_fechadas[["brigadista_codigo", "brigadista"]]
           .drop_duplicates().astype(str)
           .sort_values(["brigadista_codigo", "brigadista"]))


def _etiqueta_brig(codigo: str, nombre: str) -> str:
    codigo, nombre = codigo.strip(), nombre.strip()
    if codigo and nombre and nombre != codigo:
        return f"{codigo} · {nombre}"
    return codigo or nombre or "(sin código)"


_opciones = {_etiqueta_brig(c, n): (c, n)
             for c, n in _claves.itertuples(index=False)}
TODO_EQUIPO = "Todo el equipo"
b_sel = st.selectbox(
    "Brigadista", [TODO_EQUIPO] + list(_opciones),
    key="m3_brigadista",
    help="Todo el equipo muestra el acumulado por brigadista. Elige a uno "
         "para ver su producción jornada por jornada.",
)

if b_sel == TODO_EQUIPO:
    por_brig = (
        brig_fechadas.groupby(["brigadista_codigo", "brigadista"], as_index=False)
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
            "dias": "Días con captura", "visitas": "Visitas",
            "entrevistas": "Entrevistas", "rechazos": "Rechazos",
            "casas_solas": "Casas solas", "volantes": "Volantes",
            "por_dia": "Por día", "vs_meta": "% de meta",
        }),
        use_container_width=True, hide_index=True, height=420,
    )
    st.caption(
        f"Referencia: {META_POR_BRIGADISTA} entrevistas por brigadista al día. Es "
        f"una referencia de planeación, no un umbral de evaluación: un día en "
        f"sección rural dispersa rinde menos que uno en el centro. «Por día» "
        f"divide entre los días en que ese brigadista capturó, no entre las "
        f"{len(JORNADAS)} jornadas del equipo: un día sin captura no le baja "
        f"el promedio. Elige un brigadista arriba para ver sus jornadas."
    )
else:
    cod, nom = _opciones[b_sel]
    suyo = brig_fechadas[(brig_fechadas["brigadista_codigo"].astype(str) == cod)
                         & (brig_fechadas["brigadista"].astype(str) == nom)].copy()
    suyo["fecha"] = pd.to_datetime(suyo["fecha_visita"], errors="coerce").dt.date
    cols_num = [c for c in ("visitas", "entrevistas", "completas", "parciales",
                            "rechazos", "casas_solas", "volantes_entregados")
                if c in suyo.columns]
    suyo = suyo.groupby("fecha", as_index=False)[cols_num].sum()

    # Todas las jornadas del equipo, aunque este brigadista no haya capturado:
    # faltar un día no es lo mismo que trabajarlo sin lograr entrevistas, así
    # que la jornada vacía se marca "sin captura" y no se rellena con cero.
    jd = pd.DataFrame({"fecha": JORNADAS})
    jd["jornada"] = range(1, len(jd) + 1)
    jd = jd.merge(suyo, on="fecha", how="left")
    jd["con_captura"] = jd["visitas"].notna()
    jd["dia"] = pd.to_datetime(jd["fecha"]).dt.strftime("%d/%m")
    jd["fecha_txt"] = pd.to_datetime(jd["fecha"]).dt.strftime("%d/%m/%Y")
    jd["pct_meta"] = (jd["entrevistas"] / META_POR_BRIGADISTA * 100).round(0)
    orden_dias_b = jd["dia"].tolist()

    trabajadas = jd[jd["con_captura"]]
    n_trab = len(trabajadas)
    tot_ent = int(trabajadas["entrevistas"].sum()) if n_trab else 0
    prom = tot_ent / n_trab if n_trab else 0
    st.markdown(
        f"**{fmt_num(tot_ent)} entrevistas** en {n_trab} de {len(jd)} jornadas "
        f"· promedio {prom:.1f} por jornada con captura "
        f"({prom / META_POR_BRIGADISTA * 100:.0f}% de la referencia de "
        f"{META_POR_BRIGADISTA})"
    )

    _eje_b = dict(grid=True, gridColor=COLOR["border_subtle"], gridOpacity=0.5,
                  domainColor=COLOR["border_subtle"], tickColor=COLOR["border_subtle"],
                  labelColor=COLOR["text_secondary"], titleColor=COLOR["text_muted"],
                  labelFontSize=11, titleFontSize=11)
    _x_b = alt.X("dia:O", title=None, sort=orden_dias_b,
                 scale=alt.Scale(domain=orden_dias_b, paddingInner=0.25,
                                 paddingOuter=0.15),
                 axis=alt.Axis(labelAngle=0 if len(jd) <= 14 else -45, **_eje_b))
    _ymax = max(META_POR_BRIGADISTA * 1.25,
                float(trabajadas["entrevistas"].max() or 0) * 1.1 if n_trab else 0)
    _y_b = alt.Y("entrevistas:Q", title="Entrevistas",
                 scale=alt.Scale(domain=[0, _ymax]), axis=alt.Axis(**_eje_b))

    barras_b = (
        alt.Chart(trabajadas)
        .mark_bar(color=COLOR["amber"], cornerRadiusEnd=4)
        .encode(
            x=_x_b, y=_y_b,
            tooltip=[
                alt.Tooltip("jornada:Q", title="Jornada"),
                alt.Tooltip("fecha_txt:N", title="Día"),
                alt.Tooltip("entrevistas:Q", title="Entrevistas"),
                alt.Tooltip("pct_meta:Q", title=f"% de la referencia ({META_POR_BRIGADISTA})"),
                alt.Tooltip("visitas:Q", title="Visitas"),
                alt.Tooltip("completas:Q", title="Completas"),
                alt.Tooltip("parciales:Q", title="Parciales"),
                alt.Tooltip("rechazos:Q", title="Rechazos"),
                alt.Tooltip("casas_solas:Q", title="Casas solas"),
                alt.Tooltip("volantes_entregados:Q", title="Volantes"),
            ],
        )
    )
    # La jornada sin captura conserva su lugar en el eje y lo dice en texto:
    # un hueco mudo se confunde con un día de cero entrevistas.
    sin_cap = jd[~jd["con_captura"]].assign(entrevistas=0, t="sin captura")
    texto_sin = (
        alt.Chart(sin_cap)
        .mark_text(angle=270, align="left", baseline="middle", dx=6,
                   color=COLOR["text_muted"], fontSize=11)
        .encode(x=_x_b, y=alt.Y("entrevistas:Q", scale=alt.Scale(domain=[0, _ymax])),
                text="t:N",
                tooltip=[alt.Tooltip("jornada:Q", title="Jornada"),
                         alt.Tooltip("fecha_txt:N", title="Día"),
                         alt.Tooltip("t:N", title="Estado")])
    )
    meta_b = (
        alt.Chart(pd.DataFrame({"y": [META_POR_BRIGADISTA]}))
        .mark_rule(color=COLOR["text_secondary"], strokeDash=[5, 4], size=1.5)
        .encode(y="y:Q")
    )
    meta_b_txt = (
        alt.Chart(pd.DataFrame({"y": [META_POR_BRIGADISTA],
                                "t": [f"referencia {META_POR_BRIGADISTA}"]}))
        .mark_text(align="left", baseline="bottom", dx=4, dy=-4,
                   color=COLOR["text_muted"], fontSize=11)
        .encode(y="y:Q", text="t:N")
    )
    capas = [barras_b, meta_b, meta_b_txt]
    if not sin_cap.empty:
        capas.insert(1, texto_sin)
    st.altair_chart(
        alt.layer(*capas).properties(height=300)
        .configure_view(strokeWidth=0, fill="transparent")
        .configure(background="transparent"),
        use_container_width=True,
    )

    tabla_b = jd[["jornada", "fecha_txt"]].copy()
    tabla_b.columns = ["Jornada", "Día"]
    for col, lab in (("entrevistas", "Entrevistas"), ("pct_meta", "% de referencia"),
                     ("visitas", "Visitas"), ("completas", "Completas"),
                     ("parciales", "Parciales"), ("rechazos", "Rechazos"),
                     ("casas_solas", "Casas solas"),
                     ("volantes_entregados", "Volantes")):
        if col in jd.columns:
            tabla_b[lab] = [f"{int(v):,}" if c else "—"
                            for v, c in zip(jd[col].fillna(0), jd["con_captura"])]
    tabla_b.insert(2, "Captura", jd["con_captura"].map({True: "sí", False: "sin captura"}))
    st.dataframe(tabla_b, use_container_width=True, hide_index=True)
    st.caption(
        f"Referencia: {META_POR_BRIGADISTA} entrevistas al día, de planeación y "
        f"no de evaluación. «Sin captura» quiere decir que no hay envíos suyos "
        f"sincronizados con esa fecha; puede ser un día no trabajado o un "
        f"teléfono que todavía no envía."
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

# Un renglón sin fecha significa que el envío llegó sin el campo `inicio`: el
# conector deriva fecha_visita de ahí. No se grafica (no tiene lugar en el eje)
# pero tampoco se esconde, porque son visitas reales que no se pueden fechar.
sin_fecha = serie[serie["fecha"].isna()]
serie = serie[serie["fecha"].notna()].copy()
if not sin_fecha.empty:
    st.warning(
        f"{int(sin_fecha['visitas'].sum())} visitas llegaron sin fecha de "
        f"inicio y no aparecen en la gráfica ni en el filtro por día. "
        f"Suelen venir de envíos donde el formulario no registró el campo "
        f"`inicio`; sí están contadas en los totales de arriba."
    )

# Eje ordinal: un lugar por día con operativo. Con escala temporal los días sin
# trabajo (fines de semana) abren huecos y Altair adelgaza las etiquetas, que es
# justo lo que hace ilegible la secuencia de jornadas.
serie["dia"] = serie["fecha"].dt.strftime("%d/%m")
orden_dias = serie["dia"].tolist()
serie["jornada"] = range(1, len(serie) + 1)
_angulo = 0 if len(serie) <= 14 else -45

_eje = dict(grid=True, gridColor=COLOR["border_subtle"], gridOpacity=0.5,
            domainColor=COLOR["border_subtle"], tickColor=COLOR["border_subtle"],
            labelColor=COLOR["text_secondary"], titleColor=COLOR["text_muted"],
            labelFontSize=11, titleFontSize=11)

barras = (
    alt.Chart(serie)
    .mark_bar(color=COLOR["amber"], cornerRadiusEnd=4)
    .encode(
        x=alt.X("dia:O", title=None, sort=orden_dias,
                scale=alt.Scale(paddingInner=0.25, paddingOuter=0.15),
                axis=alt.Axis(labelAngle=_angulo, **_eje)),
        y=alt.Y("entrevistas:Q", title="Entrevistas",
                axis=alt.Axis(**_eje)),
        tooltip=[
            alt.Tooltip("jornada:Q", title="Jornada"),
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
    fecha_rec = int(estado.get("fecha_recuperada_de_start", 0) or 0)
    fin_rec = int(estado.get("fin_recuperado_de_end", 0) or 0)
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
        ("Fecha recuperada de `start`", fmt_num(fecha_rec)),
        ("Duración recuperada de `end`", fmt_num(fin_rec)),
    ]
    st.dataframe(pd.DataFrame(filas, columns=["Indicador", "n"]),
                 use_container_width=True, hide_index=True)
    if fecha_rec:
        st.info(
            f"{fecha_rec} visitas llegaron con la hora bajo `start` en lugar de "
            f"`inicio`: el formulario se volvió a publicar con los nombres por "
            f"defecto de ODK. El tablero las recupera, así que el dato está "
            f"completo, pero conviene devolverle su nombre al campo en el "
            f"XLSForm para no depender de la traducción."
        )
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