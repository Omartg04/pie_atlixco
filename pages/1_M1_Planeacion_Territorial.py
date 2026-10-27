"""
M1 — Planeación Territorial
PIE Atlixco · Arturo Solano Escobedo · Operativo de inducción 2026

Reemplaza al M1 anterior (índice SPT). El ranking lo manda el IRE; el
coropléctico colorea por capa de LN. La encuesta no entra en esta versión.

Caso de uso: el coordinador ve el mapa, lee el ranking, arma el recorrido del
día, revisa el detalle de cada sección y copia el mensaje que manda por
WhatsApp al brigadista con el enlace del mapa de campo.

El módulo NO carga el geojson de manzanas (3.5 MB). Lee cuatro insumos
ligeros; la geometría de manzana vive en los KML de My Maps, que es donde el
brigadista la necesita.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from app_utils import (
    GLOBAL_CSS, COLOR, check_password, carto_tiles, CARTO_ATTR,
    fmt_num, fmt_pct,
    load_m1_secciones, load_m1_manzanas, load_m1_contornos, load_mapas_catalogo,
)

st.set_page_config(
    page_title="M1 · Planeación Territorial · PIE Atlixco",
    page_icon="🗺️",
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

df = load_m1_secciones()
mz = load_m1_manzanas()
geo = load_m1_contornos()
mapas = load_mapas_catalogo()

URL_POR_SECCION = dict(zip(mapas["seccion"], mapas["url_my_maps_viewer"].fillna("")))

# Los enlaces de My Maps en forma de edición (/edit?mid=...) anclan el mapa a la
# primera cuenta de Google con sesión en el dispositivo, lo abren en modo
# edición y permiten mover geometrías a quien los reciba. Se detectan aquí para
# que no lleguen a campo por descuido al llenar el catálogo.
URLS_EDICION = sorted(
    int(sec) for sec, url in URL_POR_SECCION.items()
    if "/edit" in str(url) or "usp=sharing" in str(url)
)

# ── Color por capa de LN ──────────────────────────────────────────────────────
# Tres categorías legibles de un golpe, sobre la rampa de marca del proyecto:
# ámbar = S1 (mayor prioridad) → oliva = S2 → acero = S3. El IRE manda el
# ORDEN en la tabla; el mapa comunica la capa, que es lo que se lee en mapa.
COLOR_CAPA = {"S1": COLOR["amber"], "S2": "#8a8564", "S3": COLOR["steel"]}
ETIQUETA_CAPA = {
    "S1": "S1 · Núcleo de LN",
    "S2": "S2 · Intermedia",
    "S3": "S3 · Dispersa",
}
COLOR_NIVEL = {
    "P1_CERTEZA": COLOR["amber"],
    "P2_ALTA": COLOR["amber"],
    "P3_MEDIA": "#8a8564",
    "P4_BAJA": COLOR["steel"],
}

# ════════════════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="header-modulo">
  <div class="hm-dots"><span></span><span></span><span></span></div>
  <div class="hm-eyebrow">Módulo 01 · En operación</div>
  <h1>Planeación Territorial</h1>
  <p>¿A dónde manda el equipo las brigadas y en qué orden? El mapa muestra las
  74 secciones agrupadas por su peso de lista nominal, y la tabla las ordena de
  mayor a menor prioridad. Al armar el recorrido del día sale el mensaje listo
  para mandarle al brigadista por WhatsApp, con el enlace del mapa de su
  sección.</p>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR — filtros y recorrido
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### Recorrido del día")
    opciones = df["SECCION"].tolist()  # ya viene ordenado por RANKING_IRE

    # M2 manda aquí con st.session_state["m1_sel_seccion"] para abrir la ficha
    # de una sección. Se consume una sola vez: se siembra el recorrido y se
    # borra, para que el coordinador pueda quitarla después sin que vuelva.
    _pendiente = st.session_state.pop("m1_sel_seccion", None)
    if _pendiente is not None:
        try:
            _pendiente = int(_pendiente)
        except (TypeError, ValueError):
            _pendiente = None
        if _pendiente in set(df["SECCION"]):
            st.session_state["m1_recorrido"] = [_pendiente]

    secciones_foco = st.multiselect(
        "Secciones asignadas",
        opciones,
        key="m1_recorrido",
        format_func=lambda s: (
            f"#{int(df.loc[df['SECCION'] == s, 'RANKING_IRE'].iloc[0])} · "
            f"Sección {s} · {df.loc[df['SECCION'] == s, 'CAPA_LN'].iloc[0]}"
        ),
        help="En orden de prioridad. Puedes elegir una sección (mensaje para "
             "un brigadista) o varias (planeación del día).",
    )

    st.markdown("---")
    st.markdown("### Filtros de la tabla")
    f_capa = st.selectbox("Capa de LN", ["(todas)"] + sorted(df["CAPA_LN"].unique()))
    f_nivel = st.selectbox("Nivel de IRE", ["(todos)"] + sorted(df["NIVEL_IRE"].unique()))
    f_tipo = st.selectbox("Tipo INE", ["(todos)"] + sorted(df["TIPO_INE"].dropna().unique()))
    solo_con_mapa = st.checkbox(
        "Solo secciones con mapa publicado", value=False,
        help="Las secciones cuyo mapa de My Maps ya tiene URL en "
             "mapas_catalogo.csv.",
    )

df_tabla = df.copy()
if f_capa != "(todas)":
    df_tabla = df_tabla[df_tabla["CAPA_LN"] == f_capa]
if f_nivel != "(todos)":
    df_tabla = df_tabla[df_tabla["NIVEL_IRE"] == f_nivel]
if f_tipo != "(todos)":
    df_tabla = df_tabla[df_tabla["TIPO_INE"] == f_tipo]
if solo_con_mapa:
    con_mapa = {s for s, u in URL_POR_SECCION.items() if str(u).strip()}
    df_tabla = df_tabla[df_tabla["SECCION"].isin(con_mapa)]

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 1 — UNIVERSO DEL OPERATIVO
# ════════════════════════════════════════════════════════════════════════════

ln_total = int(df["LN_SECCION"].sum())
mz_prior = mz[mz["capa_prioridad_v2"] == "prioritaria_50"]
ln_prior = int(mz_prior["LN_manzana"].sum())

k1, k2, k3, k4 = st.columns(4)
for col, val, lab, ctx in [
    (k1, fmt_num(len(df)), "Secciones en el marco",
     f"{int((df['CAPA_LN'] == 'S1').sum())} en S1 · "
     f"{int((df['CAPA_LN'] == 'S2').sum())} en S2 · "
     f"{int((df['CAPA_LN'] == 'S3').sum())} en S3"),
    (k2, fmt_num(len(mz_prior)), "Manzanas prioritarias",
     f"corte al 50% · guía de recorrido"),
    (k3, fmt_num(ln_total), "Lista nominal total", "corte septiembre 2026"),
    (k4, fmt_num(ln_prior), "LN en manzanas prioritarias",
     f"{ln_prior / ln_total * 100:.1f}% del municipio"),
]:
    col.markdown(
        f'<div class="kpi-card"><div class="kpi-val">{val}</div>'
        f'<div class="kpi-label">{lab}</div>'
        f'<div class="kpi-ctx">{ctx}</div></div>',
        unsafe_allow_html=True,
    )

st.caption(
    "La sección es la unidad de asignación operativa. La manzana es referencia "
    "de recorrido: el corte al 50% orienta por dónde empezar dentro de la "
    "sección, no define una meta."
)

if URLS_EDICION:
    st.error(
        "**Enlaces de edición en el catálogo de mapas.** Las secciones "
        + ", ".join(str(s) for s in URLS_EDICION)
        + " tienen una URL en forma `/edit?mid=...`. Ese enlace abre el mapa "
          "en modo edición y cualquiera que lo reciba puede mover geometrías. "
          "Cámbialas por la forma `/viewer?mid=...` en "
          "`data/mapas_catalogo.csv` y verifica en My Maps que el mapa esté "
          "compartido como \"cualquier persona con el enlace puede VER\".",
        icon="🔒",
    )

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 2 — MAPA DE PRIORIDAD
# ════════════════════════════════════════════════════════════════════════════

st.markdown("## Mapa de prioridad")

# Las 5 secciones vigentes del bloque 160R comparten el polígono de la 160 como
# proxy (decisión D2 del log V2): si el coordinador selecciona cualquiera de
# ellas, se resalta ese polígono.
GEOM_POR_SECCION = dict(zip(df["SECCION"], df["seccion_geom"]))
geoms_foco = {GEOM_POR_SECCION[s] for s in secciones_foco}


def estilo_seccion(feature):
    p = feature["properties"]
    capa = p.get("capa_ln") or ""
    base = COLOR_CAPA.get(capa, COLOR["text_muted"])
    en_foco = p.get("seccion_geom") in geoms_foco
    return {
        "fillColor": base,
        "color": "#ffffff" if en_foco else COLOR["border_strong"],
        "weight": 3 if en_foco else 1,
        "fillOpacity": 0.78 if en_foco else (0.42 if geoms_foco else 0.58),
    }


def resaltar_seccion(feature):
    return {"weight": 3, "color": "#ffffff", "fillOpacity": 0.85}


mapa = folium.Map(
    location=[18.9010, -98.4506], zoom_start=12,
    tiles=carto_tiles(), attr=CARTO_ATTR,
)
folium.GeoJson(
    geo,
    name="Secciones",
    style_function=estilo_seccion,
    highlight_function=resaltar_seccion,
    tooltip=folium.GeoJsonTooltip(
        fields=["secciones_vigentes", "capa_ln", "ranking_ire", "nivel_ire",
                "tipo_ine", "ln_seccion", "n_mz_prioritarias", "ln_prioritaria"],
        aliases=["Sección(es):", "Capa de LN:", "Prioridad #:", "Nivel IRE:",
                 "Tipo:", "LN:", "Manzanas prioritarias:", "LN prioritaria:"],
        localize=True, sticky=False,
    ),
).add_to(mapa)

col_mapa, col_leyenda = st.columns([4, 1])
with col_mapa:
    st_folium(
        mapa, height=560, use_container_width=True,
        returned_objects=[],
        key=f"m1_mapa_{'-'.join(str(s) for s in sorted(secciones_foco))}",
    )
with col_leyenda:
    st.markdown("**Capa de lista nominal**")
    for capa in ("S1", "S2", "S3"):
        sub = df[df["CAPA_LN"] == capa]
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
            f'<span style="width:16px;height:16px;border-radius:3px;'
            f'background:{COLOR_CAPA[capa]};display:inline-block;flex:0 0 auto"></span>'
            f'<span style="font-size:.78rem;line-height:1.25">'
            f'<b>{ETIQUETA_CAPA[capa]}</b><br>'
            f'<span style="color:{COLOR["text_secondary"]}">{len(sub)} secciones · '
            f'{sub["LN_SECCION"].sum() / ln_total * 100:.1f}% de la LN</span></span></div>',
            unsafe_allow_html=True,
        )
    st.caption(
        "El color comunica el peso de lista nominal. El orden de prioridad lo "
        "manda el IRE, en la tabla de abajo."
    )
    if any(df.loc[df["SECCION"].isin(secciones_foco), "es_bloque_160r"] == 1):
        st.warning(
            "El bloque 160R comparte el polígono de la sección 160 como proxy: "
            "sus 5 secciones vigentes se resaltan juntas.", icon="⚠️",
        )

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 3 — RANKING DE SECCIONES PRIORITARIAS
# ════════════════════════════════════════════════════════════════════════════

st.markdown("## Ranking de secciones prioritarias")

COLS_VISTA = {
    "RANKING_IRE": "#", "SECCION": "Sección", "TIPO_INE": "Tipo",
    "CAPA_LN": "Capa LN", "NIVEL_IRE": "Nivel IRE", "IRE": "IRE",
    "LN_SECCION": "LN", "PCT_LN_ACUM": "% LN acum.",
    "n_mz_prioritarias": "Mz prior.", "ln_prioritaria": "LN prior.",
    "n_navs": "Colonias/loc.",
}
vista = df_tabla[list(COLS_VISTA)].rename(columns=COLS_VISTA)


def pinta_nivel(val):
    return f"color:{COLOR_NIVEL.get(val, COLOR['text_secondary'])};font-weight:600"


def pinta_capa(val):
    return f"color:{COLOR_CAPA.get(val, COLOR['text_secondary'])};font-weight:600"


st.dataframe(
    vista.style
    .map(pinta_nivel, subset=["Nivel IRE"])
    .map(pinta_capa, subset=["Capa LN"])
    .format({"IRE": "{:.4f}", "% LN acum.": "{:.1f}%",
             "LN": "{:,.0f}", "LN prior.": "{:,.0f}"}),
    use_container_width=True, hide_index=True, height=420,
)
st.caption(
    f"{len(df_tabla)} de {len(df)} secciones con los filtros actuales. "
    "Ninguna sección alcanzó P1_CERTEZA: el piso de la rejilla del Monte Carlo "
    "(n=20) queda por debajo del N* de la sección mayor, que es 24."
)

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 4 — RESUMEN DEL RECORRIDO
# ════════════════════════════════════════════════════════════════════════════

st.markdown("## Recorrido seleccionado")

if not secciones_foco:
    st.info(
        "Elige las secciones del recorrido en la barra lateral. Con una sección "
        "sale el mensaje para el brigadista; con varias, la planeación del día."
    )
else:
    sel = df[df["SECCION"].isin(secciones_foco)].sort_values("RANKING_IRE")
    geoms_sel = sel["seccion_geom"].unique()
    mz_sel = mz_prior[mz_prior["seccion"].isin(geoms_sel)]
    r1, r2, r3, r4 = st.columns(4)
    for col, val, lab, ctx in [
        (r1, fmt_num(len(sel)), "Secciones",
         f"prioridad #{int(sel['RANKING_IRE'].min())} a "
         f"#{int(sel['RANKING_IRE'].max())}"),
        (r2, fmt_num(len(mz_sel)), "Manzanas prioritarias",
         f"{mz_sel['nav_nombre'].nunique()} colonias/localidades"),
        (r3, fmt_num(sel["LN_SECCION"].sum()), "LN de las secciones",
         f"{sel['LN_SECCION'].sum() / ln_total * 100:.1f}% del municipio"),
        (r4, fmt_num(mz_sel["LN_manzana"].sum()), "LN prioritaria",
         "en las manzanas del corte 50%"),
    ]:
        col.markdown(
            f'<div class="kpi-card"><div class="kpi-val">{val}</div>'
            f'<div class="kpi-label">{lab}</div>'
            f'<div class="kpi-ctx">{ctx}</div></div>',
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════════════════════════════════════════
    # BLOQUE 5 — DETALLE POR SECCIÓN
    # ════════════════════════════════════════════════════════════════════════

    st.markdown("## Detalle de las secciones")

    for _, row in sel.iterrows():
        secc = int(row["SECCION"])
        geom = int(row["seccion_geom"])
        bloque = row["es_bloque_160r"] == 1
        mz_s = mz_prior[mz_prior["seccion"] == geom]
        url = str(URL_POR_SECCION.get(secc, "") or "").strip()

        titulo = (f"Prioridad #{int(row['RANKING_IRE'])} · Sección {secc} · "
                  f"{row['TIPO_INE']} · {row['CAPA_LN']} · "
                  f"{fmt_num(row['LN_SECCION'])} electores")
        with st.expander(titulo, expanded=len(sel) <= 3):
            if bloque:
                st.warning(
                    "Sección del bloque 160R. No tiene cartografía de manzana "
                    "propia: comparte el polígono de la sección 160 y sus "
                    "manzanas no tienen LN asignada. El mapa de campo muestra "
                    "la traza del bloque completo, sin priorización.",
                    icon="⚠️",
                )
            if not url:
                st.info(
                    f"El mapa de la sección {secc} todavía no tiene URL en "
                    "`mapas_catalogo.csv`. El KML está generado; falta "
                    "publicarlo en My Maps y pegar aquí el enlace `/viewer`."
                )

            c1, c2 = st.columns([3, 2])
            with c1:
                st.markdown("**Manzanas prioritarias por colonia o localidad**")
                if mz_s.empty:
                    st.caption("Sin manzanas prioritarias en esta sección.")
                else:
                    agr = (
                        mz_s.groupby(["nav_tipo", "nav_nombre"])
                        .agg(manzanas=("manzana", lambda s: ", ".join(
                            str(int(x)) for x in sorted(s))),
                             n=("manzana", "size"),
                             ln=("LN_manzana", "sum"))
                        .reset_index()
                        .sort_values("ln", ascending=False)
                    )
                    agr["ln"] = agr["ln"].round().astype(int)
                    st.dataframe(
                        agr.rename(columns={
                            "nav_tipo": "Tipo", "nav_nombre": "Colonia / localidad",
                            "manzanas": "Manzanas", "n": "N", "ln": "LN est.",
                        }),
                        use_container_width=True, hide_index=True,
                    )
            with c2:
                st.markdown("**Indicadores de la sección**")
                st.markdown(
                    f"- IRE **{row['IRE']:.4f}** · nivel **{row['NIVEL_IRE']}**\n"
                    f"- Ranking por LN: **#{int(row['RANKING_LN'])}** de 74\n"
                    f"- LN acumulada hasta aquí: **{row['PCT_LN_ACUM']:.1f}%**\n"
                    f"- Manzanas prioritarias: **{int(row['n_mz_prioritarias'])}** "
                    f"({fmt_num(row['ln_prioritaria'])} electores)\n"
                    f"- Unidades de navegación: **{int(row['n_navs'])}**\n"
                    f"- N* del diseño muestral: **{int(row['N_STAR'])}**"
                )

            with st.expander("Caracterización electoral y demográfica", expanded=False):
                e1, e2 = st.columns(2)
                with e1:
                    st.markdown("**Elección de ayuntamiento 2024**")
                    st.markdown(
                        f"- Ganador: **{row['GANADOR_2024']}**\n"
                        f"- Margen: **{row['MARGEN_PP_2024']:.2f} pp**\n"
                        f"- Bloque Morena: **{fmt_pct(row['PCT_MORENA_2024'])}**\n"
                        f"- Oposición: **{fmt_pct(row['PCT_OPOSI_2024'])}**\n"
                        f"- MC: **{fmt_pct(row['PCT_MC_2024'])}**\n"
                        f"- Nulos: **{fmt_pct(row['PCT_NULOS_2024'])}**"
                    )
                    if str(row["ORIGEN_ELECTORAL"]) != "computo_propio":
                        st.caption(
                            "Votos heredados de la sección 160 repartidos en "
                            "proporción a la LN: las 5 secciones del bloque "
                            "comparten el mismo porcentaje y difieren solo en "
                            "volumen."
                        )
                    if str(row["FLAG_CASILLA_ESPECIAL_EXCLUIDA"]) == "1":
                        st.caption(
                            "Se excluyeron casillas especiales del agregado: "
                            "son electores en tránsito, no residentes."
                        )
                    if str(row["FLAG_CALIDAD_COMPUTO"]).strip() not in ("", "nan"):
                        st.caption(f"Calidad del cómputo: {row['FLAG_CALIDAD_COMPUTO']}")
                with e2:
                    st.markdown("**Composición de la lista nominal**")
                    st.markdown(
                        f"- Mujeres: **{fmt_pct(row['PCT_MUJERES'])}**\n"
                        f"- 18–29: **{fmt_pct(row['PCT_18_29'])}**\n"
                        f"- 30–44: **{fmt_pct(row['PCT_30_44'])}**\n"
                        f"- 45–59: **{fmt_pct(row['PCT_45_59'])}**\n"
                        f"- 60 y más: **{fmt_pct(row['PCT_60_MAS'])}**\n"
                        f"- 45 y más: **{fmt_pct(row['PCT_45_MAS'])}**"
                    )
                st.caption(
                    "Capas descriptivas: no entran en el índice ni en el "
                    "ranking. La correlación entre IRE y fuerza del bloque es "
                    "de +0.13, así que no se construyó índice de rentabilidad."
                )

    # ════════════════════════════════════════════════════════════════════════
    # BLOQUE 6 — MENSAJE PARA COMPARTIR
    # ════════════════════════════════════════════════════════════════════════

    st.markdown("## Mensaje para compartir")

    # El mensaje lista las colonias y localidades donde hay manzanas
    # prioritarias, sin los números: el mapa de la sección ya los trae marcados
    # y el brigadista los explora ahí con el contexto completo. El detalle
    # queda disponible a un clic para cuando alguien lo pida.
    incluir_detalle = st.checkbox(
        "Incluir los números de manzana y su LN", value=False,
        help="Normalmente no hace falta: el mapa de la sección ya trae las "
             "manzanas marcadas. Actívalo si algún brigadista necesita la "
             "lista escrita.",
    )

    lineas = []
    if len(sel) > 1:
        tot_mz = int(sel["n_mz_prioritarias"].sum())
        lineas += [
            "📋 ATLIXCO · RECORRIDO DEL DÍA",
            f"{len(sel)} secciones · {tot_mz} manzanas prioritarias · "
            f"{fmt_num(sel['LN_SECCION'].sum())} electores en lista nominal",
            "",
        ]

    for _, row in sel.iterrows():
        secc = int(row["SECCION"])
        geom = int(row["seccion_geom"])
        mz_s = mz_prior[mz_prior["seccion"] == geom]
        url = str(URL_POR_SECCION.get(secc, "") or "").strip()

        lineas += [
            f"📍 SECCIÓN {secc} · {row['TIPO_INE']} · prioridad #{int(row['RANKING_IRE'])}",
            f"{int(row['n_mz_prioritarias'])} manzanas prioritarias · "
            f"{fmt_num(row['LN_SECCION'])} electores en la sección",
        ]

        if not mz_s.empty:
            for (nav_tipo, nav_nombre), grupo in mz_s.groupby(["nav_tipo", "nav_nombre"]):
                etiqueta = "Loc" if nav_tipo != "colonia" else "Col"
                linea = f"Manzanas: {etiqueta}. {nav_nombre}"
                if incluir_detalle:
                    piezas = ", ".join(
                        f"{int(r.manzana)} (~{round(r.LN_manzana)})"
                        for r in grupo.sort_values("manzana").itertuples()
                    )
                    linea += f" — {piezas}"
                lineas.append(linea)

        if url:
            lineas.append(f"🗺️ {url}")
        else:
            lineas.append("🗺️ (mapa pendiente de publicar)")

        if row["es_bloque_160r"] == 1:
            lineas.append(
                "⚠️ Sección reseccionada: el mapa muestra la traza del bloque "
                "160R completo, sin manzanas priorizadas."
            )
        lineas.append("")

    mensaje = "\n".join(lineas).rstrip()
    st.code(mensaje, language=None)

    aviso = ("" if len(mensaje) < 4096 else
             " ⚠️ Supera los 4,096 caracteres de un mensaje de WhatsApp: se "
             "partirá en varios. Selecciona menos secciones si quieres "
             "mandarlo en uno solo.")
    st.caption(
        f"Usa el botón de copiar en la esquina del bloque y pégalo en WhatsApp. "
        f"El enlace abre el mapa de la sección, donde el brigadista verifica el "
        f"contorno y sus manzanas. {len(mensaje):,} caracteres.{aviso}"
    )
    faltantes = [int(r["SECCION"]) for _, r in sel.iterrows()
                 if not str(URL_POR_SECCION.get(int(r["SECCION"]), "") or "").strip()]
    if faltantes:
        st.warning(
            "Sin URL de mapa: secciones "
            + ", ".join(str(s) for s in faltantes)
            + ". Publica su KML en My Maps y pega el enlace `/viewer` en "
              "`data/mapas_catalogo.csv`.",
            icon="⚠️",
        )

# ════════════════════════════════════════════════════════════════════════════
# BLOQUE 7 — TABLA DE REFERENCIA
# ════════════════════════════════════════════════════════════════════════════

with st.expander("Tabla completa de planeación (74 secciones)", expanded=False):
    completa = df.copy()
    completa["url_mapa"] = completa["SECCION"].map(
        lambda s: str(URL_POR_SECCION.get(s, "") or "")
    )
    st.dataframe(completa, use_container_width=True, hide_index=True, height=420)
    st.download_button(
        "Descargar CSV",
        completa.to_csv(index=False).encode("utf-8"),
        file_name="pie_atlixco_planeacion_secciones.csv",
        mime="text/csv",
    )
