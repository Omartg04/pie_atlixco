"""
M2 — Manzanas Prioritarias
PIE Atlixco · Arturo Solano Escobedo
Vista general: mapa con todas las manzanas de las 37 secciones Modo A a la vez,
con corte acumulativo de priorización (500 / 700 / 865). El selector de sección
permite hacer zoom/detalle opcional a una sección específica.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from utils import (
    GLOBAL_CSS, COLOR, load_spt, load_geojson, load_manzanas, load_priorizacion_secciones,
    fmt_num, ARQUETIPOS, DEFAULT_ARQUETIPO, check_password, corte_color, score_color,
)

st.set_page_config(
    page_title="M2 · Manzanas · PIE Atlixco",
    page_icon="🧱",
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
  <div class="hm-eyebrow">Módulo 02 · En operación</div>
  <h1>🧱 Manzanas Prioritarias</h1>
  <p>Dentro de cada sección Modo A, cuáles manzanas concentran la lista nominal
  elegible y en qué orden conviene cubrirlas — corte acumulativo de 500, 700 y
  865 manzanas (cada corte incluye al anterior; optimización validada contra ILP).</p>
</div>
""", unsafe_allow_html=True)

geo_mz = load_manzanas()
geo_secciones = load_geojson()
df_spt = load_spt()
df_prior = load_priorizacion_secciones()

secciones_modo_a = sorted(
    s for s in df_spt[df_spt["modo_spt"] == "A"]["seccion"].tolist()
    if s in df_prior["seccion"].tolist()
)
SECCIONES_MODO_B = [207, 214, 215, 217, 219]
todas_las_secciones = sorted(secciones_modo_a + SECCIONES_MODO_B)

OPCION_TODAS = "Todas las secciones (vista general)"

# Orden de acumulación: cada corte incluye a los anteriores.
ORDEN_CORTES = ["meta_500", "meta_700", "meta_865"]

CAPA_COLOR = {
    "meta_500": corte_color(500),       # ámbar oscuro — máxima prioridad
    "meta_700": corte_color(700),       # ámbar base
    "meta_865": corte_color(865),       # ámbar claro — universo focalizado completo
    "fuera_focalizado": "#3a4255",      # gris — dentro de la sección, fuera del corte 80%
}
CAPA_LABEL = {
    "meta_500": "Meta 500 (máxima prioridad)",
    "meta_700": "Meta 700 (+200 siguientes)",
    "meta_865": "Meta 865 (universo focalizado completo)",
    "fuera_focalizado": "Fuera del corte 80% de la sección",
}
CORTE_LABEL = {
    "meta_500": "500 — máxima prioridad",
    "meta_700": "700 — incluye las 500 + 200 siguientes",
    "meta_865": "865 — universo focalizado completo",
}

# ════════════════════════════════════════════════════════════════════════════
# SELECTOR DE SECCIÓN (o vista general) + CORTE DE PRIORIZACIÓN
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### Sección")
    opciones_sel = [OPCION_TODAS] + todas_las_secciones
    sec_sel = st.selectbox(
        "Vista general o detalle de una sección específica",
        opciones_sel,
        index=0,
        format_func=lambda s: (
            OPCION_TODAS if s == OPCION_TODAS
            else f"Sección {s}" + (" ⚠️" if s == 160 else "") + (" · rural" if s in SECCIONES_MODO_B else "")
        ),
    )

    vista_general = sec_sel == OPCION_TODAS
    es_modo_b = (not vista_general) and (sec_sel in SECCIONES_MODO_B)

    mostrar_corte = vista_general or not es_modo_b
    if mostrar_corte:
        st.markdown("### Corte de priorización")
        corte_sel = st.radio(
            "Cada corte incluye a los anteriores",
            ORDEN_CORTES,
            index=2,  # default: 865 — universo focalizado completo, todas visibles
            format_func=lambda c: CORTE_LABEL[c],
        )
        st.markdown("### Capa adicional")
        show_fuera = st.checkbox("⬛ Fuera del corte 80%", value=False)
    else:
        corte_sel = None
        show_fuera = False

# Capas incluidas en el mapa según el corte acumulativo elegido
if corte_sel is not None:
    idx_corte = ORDEN_CORTES.index(corte_sel)
    capas_incluidas = ORDEN_CORTES[: idx_corte + 1]
else:
    capas_incluidas = []
if show_fuera:
    capas_incluidas = capas_incluidas + ["fuera_focalizado"]

# ════════════════════════════════════════════════════════════════════════════
# CONTEXTO DE SECCIÓN: alerta operativa + arquetipo (solo en modo detalle)
# ════════════════════════════════════════════════════════════════════════════

tiene_alerta = False

if not vista_general:
    fila_spt = df_spt[df_spt["seccion"] == sec_sel]
    tiene_alerta = bool(fila_spt.iloc[0]["flag_alerta_operativa"]) if not fila_spt.empty else False

    if not fila_spt.empty:
        row_spt = fila_spt.iloc[0]
        arq = ARQUETIPOS.get(row_spt["perfil_mensaje_sugerido"], DEFAULT_ARQUETIPO)

        st.markdown(f"""
        <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']};
                    border-left:3px solid {COLOR['amber']}; border-radius:0 8px 8px 0;
                    padding:14px 18px; margin-bottom:14px; display:flex; align-items:flex-start; gap:12px;">
          <span style="font-size:1.5rem; line-height:1;">{arq['icono']}</span>
          <div>
            <div style="font-family:'JetBrains Mono',monospace; font-size:.64rem; font-weight:700;
                        letter-spacing:.1em; text-transform:uppercase; color:{COLOR['text_muted']}; margin-bottom:4px;">
              Segmento característico de esta sección
            </div>
            <div style="font-size:.92rem; font-weight:700; color:{COLOR['text_primary']}; margin-bottom:3px;">
              {arq['nombre']}
            </div>
            <div style="font-size:.78rem; color:{COLOR['text_secondary']};">
              📣 {arq['mensaje']} <span style="color:{COLOR['text_muted']};">· Canal: {arq['canal']}</span>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    if tiene_alerta:
        st.markdown(
            f"""<div style="background:rgba(196,112,63,.12); border:1px solid rgba(196,112,63,.4);
            border-radius:8px; padding:12px 16px; margin-bottom:16px; font-size:.85rem; color:#e88a5d;">
            ⚠️ <b>Alerta operativa documentada</b> en esta sección. Se incluye en el índice y en este
            mapa <b>sin penalizar</b> su peso ni su ranking, solo con este aviso visual.</div>""",
            unsafe_allow_html=True,
        )

    if es_modo_b:
        st.markdown(
            f"""<div style="background:rgba(91,122,158,.12); border:1px solid rgba(91,122,158,.4);
            border-radius:8px; padding:14px 18px; margin-bottom:16px; font-size:.86rem; color:#8fb0d6;
            display:flex; align-items:flex-start; gap:10px;">
            <span style="font-size:1.3rem;">📍</span>
            <span><b>Sección rural sin desagregación censal por manzana</b> (Modo B del SPT).
            Esta localidad no tiene el detalle de lista nominal por manzana que sí existe en las
            37 secciones urbanas/mixtas — el criterio operativo aquí es <b>barrido total de la
            localidad</b>, no priorización interna por manzana.</span>
            </div>""",
            unsafe_allow_html=True,
        )
        st.info(
            "No hay cortes de priorización que mostrar para esta sección: se trabaja completa, "
            "sin subdivisión interna por manzana.",
            icon="🚶",
        )
        if st.button("Ver ficha completa en Plan Territorial →", key="m1_link_modob"):
            st.session_state["m1_sel_seccion"] = int(sec_sel)
            st.switch_page("pages/1_M1_Plan_Territorial.py")
        st.stop()

    if st.button("Ver ficha completa en Plan Territorial →", key="m1_link_modoa"):
        st.session_state["m1_sel_seccion"] = int(sec_sel)
        st.switch_page("pages/1_M1_Plan_Territorial.py")

else:
    st.info(
        "Vista general: todas las secciones a la vez. Elige una sección específica en la "
        "barra lateral para ver su ficha, alerta operativa y arquetipo de mensaje.",
        icon="🗺️",
    )

# ════════════════════════════════════════════════════════════════════════════
# KPIs (por sección en modo detalle; agregados en vista general)
# ════════════════════════════════════════════════════════════════════════════

if not vista_general:
    fila_prior = df_prior[df_prior["seccion"] == sec_sel]
    if not fila_prior.empty:
        r = fila_prior.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        for col, val, label in [
            (c1, f"#{int(r['ranking'])}", "Ranking de prioridad (37 secc.)"),
            (c2, fmt_num(r["n_manzanas_elegibles"]), f"Manzanas elegibles de {fmt_num(r['n_manzanas_totales'])}"),
            (c3, fmt_num(r["ln_agregada_elegibles"]), "LN agregada elegible"),
            (c4, f"{r['pct_ln_elegibles']*100:.1f}%", "% de LN de la sección cubierta"),
        ]:
            with col:
                st.markdown(f"""
                <div class="kpi-card">
                  <div class="kpi-val">{val}</div>
                  <div class="kpi-label">{label}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# MANZANAS A RENDERIZAR
# ════════════════════════════════════════════════════════════════════════════

if vista_general:
    feats_render = [
        f for f in geo_mz["features"] if f["properties"]["en_alcance_42_secciones"]
    ]
else:
    feats_render = [
        f for f in geo_mz["features"]
        if f["properties"]["seccion"] == sec_sel
        and f["properties"]["en_alcance_42_secciones"]
    ]

if not feats_render:
    st.warning("No hay manzanas geolocalizadas para mostrar en el archivo cargado.")
    st.stop()

# ── Ranking por LN dentro de cada sección — solo universo elegible (500/700/865),
#    excluye manzanas "fuera del corte 80%" (esas no compiten por prioridad) ──
from collections import defaultdict
_feats_elegibles = [f for f in feats_render if f["properties"]["capa_prioridad"] in ORDEN_CORTES]
_grupos_seccion = defaultdict(list)
for _f in _feats_elegibles:
    _grupos_seccion[_f["properties"]["seccion"]].append(_f)
RANK_LOOKUP = {}
for _sec_id, _feats_grupo in _grupos_seccion.items():
    _ordenado = sorted(
        _feats_grupo, key=lambda f: f["properties"]["LN_estimada_manzana"], reverse=True
    )
    _total = len(_ordenado)
    for _i, _f in enumerate(_ordenado, start=1):
        RANK_LOOKUP[(_f["properties"]["seccion"], _f["properties"]["id_unidad"])] = (_i, _total)

if vista_general:
    # Universo focalizado completo (500+700+865, sin "fuera del corte"), fijo — denominador de LN.
    feats_focalizado = [
        f for f in feats_render if f["properties"]["capa_prioridad"] in ORDEN_CORTES
    ]
    ln_total_focalizado = sum(f["properties"]["LN_estimada_manzana"] for f in feats_focalizado)

    # Corte actualmente seleccionado (excluye "fuera del corte 80%" del cálculo de LN/%).
    corte_capas_activas = [c for c in capas_incluidas if c in ORDEN_CORTES]
    feats_corte = [
        f for f in feats_render if f["properties"]["capa_prioridad"] in corte_capas_activas
    ]
    ln_corte = sum(f["properties"]["LN_estimada_manzana"] for f in feats_corte)
    pct_ln_corte = (ln_corte / ln_total_focalizado * 100) if ln_total_focalizado else 0
    n_secciones_corte = len({f["properties"]["seccion"] for f in feats_corte})

    c1, c2, c3 = st.columns(3)
    for col, val, label in [
        (c1, fmt_num(len(feats_corte)), "Manzanas totales en universo focalizado"),
        (c2, fmt_num(n_secciones_corte), "Secciones con detalle de manzana"),
        (c3, f"{fmt_num(ln_corte)} ({pct_ln_corte:.1f}%)", "LN cubierta (del total focalizado)"),
    ]:
        with col:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-val">{val}</div>
              <div class="kpi-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

# Conteo de manzanas por capa, para el selector y la leyenda
conteo_capas = {capa: 0 for capa in list(CAPA_LABEL)}
for feat in feats_render:
    c = feat["properties"]["capa_prioridad"]
    if c in conteo_capas:
        conteo_capas[c] += 1

if not vista_general:
    corte_capas_activas = [c for c in capas_incluidas if c in ORDEN_CORTES]
    manzanas_corte_actual = sum(conteo_capas.get(c, 0) for c in corte_capas_activas)
    manzanas_elegibles_totales = sum(conteo_capas.get(c, 0) for c in ORDEN_CORTES)

    ln_corte_seccion = sum(
        f["properties"]["LN_estimada_manzana"] for f in feats_render
        if f["properties"]["capa_prioridad"] in corte_capas_activas
    )
    ln_elegible_seccion = sum(
        f["properties"]["LN_estimada_manzana"] for f in feats_render
        if f["properties"]["capa_prioridad"] in ORDEN_CORTES
    )
    pct_ln_seccion = (ln_corte_seccion / ln_elegible_seccion * 100) if ln_elegible_seccion else 0

    cc1, cc2 = st.columns(2)
    for col, val, label in [
        (cc1, f"{manzanas_corte_actual} de {manzanas_elegibles_totales}",
         f"Manzanas visibles en corte {CORTE_LABEL[corte_sel].split(' —')[0]}"),
        (cc2, f"{fmt_num(ln_corte_seccion)} ({pct_ln_seccion:.1f}%)",
         "LN cubierta en este corte"),
    ]:
        with col:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-val">{val}</div>
              <div class="kpi-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    if manzanas_elegibles_totales == manzanas_corte_actual and corte_sel != "meta_500":
        st.caption(
            f"Ya se muestran las {manzanas_corte_actual} manzanas elegibles de la sección — "
            "no hay más por agregar en cortes más amplios, por eso el mapa no cambia al subir de nivel."
        )
    st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# MAPA
# ════════════════════════════════════════════════════════════════════════════

lats, lons = [], []
for feat in feats_render:
    coords = feat["geometry"]["coordinates"]
    def _flatten(c):
        if isinstance(c[0], (float, int)):
            lats.append(c[1]); lons.append(c[0])
        else:
            for cc in c:
                _flatten(cc)
    _flatten(coords)
center = [sum(lats) / len(lats), sum(lons) / len(lons)] if lats else [18.9, -98.43]
zoom_inicial = 12 if vista_general else 15

m = folium.Map(location=center, zoom_start=zoom_inicial, tiles="CartoDB dark_matter")

# ── Contorno(s) de sección (contexto espacial, sin relleno) ──
if vista_general:
    feats_seccion_borde = [
        f for f in geo_secciones["features"]
        if f["properties"].get("seccion") in todas_las_secciones
    ]
    df_spt_alcance = df_spt[df_spt["seccion"].isin(todas_las_secciones)]
    spt_vmin = float(df_spt_alcance["indice_spt"].min()) if not df_spt_alcance.empty else 0
    spt_vmax = float(df_spt_alcance["indice_spt"].max()) if not df_spt_alcance.empty else 100
else:
    feats_seccion_borde = [
        f for f in geo_secciones["features"] if f["properties"].get("seccion") == sec_sel
    ]
    spt_vmin = spt_vmax = None

for feat_seccion in feats_seccion_borde:
    sec_borde = feat_seccion["properties"].get("seccion")

    if vista_general:
        fila_spt_borde = df_spt[df_spt["seccion"] == sec_borde]
        if not fila_spt_borde.empty:
            val_spt = float(fila_spt_borde.iloc[0]["indice_spt"])
            fill_color = score_color(val_spt, spt_vmin, spt_vmax)
            tooltip_txt = (
                f"Sección {sec_borde} · Índice SPT: {val_spt:.1f} "
                f"(ranking #{int(fila_spt_borde.iloc[0]['ranking'])})"
            )
        else:
            fill_color = COLOR["text_muted"]
            tooltip_txt = f"Sección {sec_borde} · sin dato SPT"

        folium.GeoJson(
            feat_seccion,
            style_function=lambda x, c=fill_color: {
                "fillOpacity": .75, "fillColor": c, "color": "#0f1218", "weight": 1,
            },
            highlight_function=lambda x: {"weight": 2.5, "color": "#eef1f0", "fillOpacity": .9},
            tooltip=folium.Tooltip(tooltip_txt),
        ).add_to(m)
    else:
        folium.GeoJson(
            feat_seccion,
            style_function=lambda x: {
                "fillOpacity": 0, "color": COLOR["text_secondary"],
                "weight": 2, "dashArray": "6,4",
            },
            tooltip=folium.Tooltip(f"Límite de la sección {sec_borde}"),
        ).add_to(m)

hay_limite = len(feats_seccion_borde) > 0

groups = {}
for capa in capas_incluidas:
    fg = folium.FeatureGroup(name=CAPA_LABEL[capa], show=True)
    groups[capa] = fg

for feat in feats_render:
    props = feat["properties"]
    capa = props["capa_prioridad"]
    if capa not in groups:
        continue

    color = CAPA_COLOR.get(capa, "#5b7a9e")
    sec_feat = props["seccion"]
    alerta = " ⚠️" if (sec_feat == 160) else ""
    peso_borde = 2 if capa == "meta_500" else 1  # corte 500: borde reforzado, máxima prioridad

    rank_i, rank_total = RANK_LOOKUP.get((sec_feat, props["id_unidad"]), (None, None))
    ranking_txt = f"Manzana #{rank_i} de {rank_total}" if rank_i else "Manzana s/d"

    tooltip_html = (
        f"<b>{ranking_txt}</b>{alerta}<br>"
        f"Sección: {sec_feat}<br>"
        f"LN estimada: {props['LN_estimada_manzana']:.1f}<br>"
        f"Capa: {CAPA_LABEL.get(capa, capa)}"
    )

    folium.GeoJson(
        feat,
        style_function=lambda x, c=color, w=peso_borde: {
            "fillColor": c, "color": "#0f1218", "weight": w, "fillOpacity": .8,
        },
        highlight_function=lambda x: {"weight": 2.5, "color": "#eef1f0", "fillOpacity": .95},
        tooltip=folium.Tooltip(
            tooltip_html,
            style="font-family:'DM Sans',sans-serif; font-size:12.5px; background:#1b212b; "
                  "color:#eef1f0; border:1px solid #3a4255; border-radius:6px;",
        ),
    ).add_to(groups[capa])

for fg in groups.values():
    fg.add_to(m)

st_folium(
    m, height=560, use_container_width=True,
    key=f"m2_map_{sec_sel}_{corte_sel}_{show_fuera}",
)

# ── Leyenda dinámica: solo capas activas, con conteo + límite/SPT de sección ──
if vista_general:
    limite_html = (
        f'<span style="display:inline-flex; align-items:center; gap:6px; margin-right:16px; font-size:.78rem; color:{COLOR["text_secondary"]};">'
        f'<span style="width:11px; height:11px; border-radius:3px; background:linear-gradient(90deg,{COLOR["steel"]},{COLOR["amber"]}); display:inline-block;"></span>'
        f'Índice SPT por sección (acero = menor prioridad, ámbar = mayor)</span>'
    ) if hay_limite else ""
else:
    limite_html = (
        f'<span style="display:inline-flex; align-items:center; gap:6px; margin-right:16px; font-size:.78rem; color:{COLOR["text_secondary"]};">'
        f'<span style="width:16px; height:0; border-top:2px dashed {COLOR["text_secondary"]}; display:inline-block;"></span>'
        f'Límite de la sección</span>'
    ) if hay_limite else ""

if capas_incluidas:
    legend_html = limite_html + "".join(
        f'<span style="display:inline-flex; align-items:center; gap:6px; margin-right:16px; font-size:.78rem; color:{COLOR["text_secondary"]};">'
        f'<span style="width:11px; height:11px; border-radius:3px; background:{CAPA_COLOR[capa]}; display:inline-block;"></span>'
        f'{CAPA_LABEL[capa]} <span style="color:{COLOR["text_muted"]};">({conteo_capas.get(capa, 0)})</span></span>'
        for capa in capas_incluidas
    )
    st.markdown(f'<div style="margin-top:10px;">{legend_html}</div>', unsafe_allow_html=True)
else:
    if limite_html:
        st.markdown(f'<div style="margin-top:10px;">{limite_html}</div>', unsafe_allow_html=True)
    st.caption("Ninguna capa activa — elige un corte de priorización en la barra lateral.")

total_visible = sum(conteo_capas.get(c, 0) for c in capas_incluidas)
total_universo = len(feats_render)
ambito_txt = "el universo focalizado (todas las secciones)" if vista_general else "la sección"
st.caption(
    f"Mostrando {total_visible} de {total_universo} manzanas de {ambito_txt}. "
    "El corte es acumulativo: 700 incluye las manzanas de 500, y 865 incluye a las de 700."
)

# ════════════════════════════════════════════════════════════════════════════
# DESCARGA DE MAPA DE CAMPO (PDF) — solo modo detalle.
# Documento oficial para brigadistas; generado en proyecto aparte.
# ════════════════════════════════════════════════════════════════════════════

if not vista_general:
    ruta_pdf = os.path.join(BASE_DIR, "data", "mapas", f"seccion_{sec_sel}.pdf")
    st.markdown("<br>", unsafe_allow_html=True)
    if os.path.exists(ruta_pdf):
        with open(ruta_pdf, "rb") as f:
            st.download_button(
                "📄 Descargar mapa de campo (PDF) — sección " + str(sec_sel),
                data=f.read(),
                file_name=f"seccion_{sec_sel}.pdf",
                mime="application/pdf",
            )
    else:
        st.caption(f"Mapa de campo aún no generado para la sección {sec_sel}.")

# ════════════════════════════════════════════════════════════════════════════
# RANKING DE MANZANAS POR LN (solo modo detalle) — insumo de planeación.
# El mapa impreso, no esta tabla, es lo que orienta al brigadista en campo.
# ════════════════════════════════════════════════════════════════════════════

if not vista_general:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="font-family:'Barlow Condensed',sans-serif; font-weight:800;
                text-transform:uppercase; color:{COLOR['text_primary']}; font-size:1.15rem; margin-bottom:2px;">
      Ranking de manzanas por LN — sección {sec_sel}
    </div>
    <div style="font-size:.8rem; color:{COLOR['text_secondary']}; margin-bottom:10px;">
      Orden de cobertura sugerido dentro de esta sección. Insumo de planeación — en campo,
      el mapa impreso es la referencia operativa.
    </div>
    """, unsafe_allow_html=True)

    feats_elegibles_sec = [
        f for f in feats_render if f["properties"]["capa_prioridad"] in ORDEN_CORTES
    ]
    n_total_sec = len(feats_elegibles_sec)
    filas_ranking = sorted(
        (
            {
                "ln": f["properties"]["LN_estimada_manzana"],
                "capa": f["properties"]["capa_prioridad"],
                "ranking_i": RANK_LOOKUP[(f["properties"]["seccion"], f["properties"]["id_unidad"])][0],
            }
            for f in feats_elegibles_sec
        ),
        key=lambda r: r["ln"], reverse=True,
    )
    for fila in filas_ranking:
        fila["ranking"] = f"{fila['ranking_i']} de {n_total_sec}"
        fila["corte"] = CORTE_LABEL.get(fila["capa"], fila["capa"]).split(" —")[0]

    df_ranking = pd.DataFrame(filas_ranking)[["ranking", "corte", "ln", "capa"]]
    df_ranking.columns = ["Ranking", "Corte", "LN estimada", "_capa"]

    corte_activo = set(corte_capas_activas)

    def _resalta_corte_activo(row):
        activo = row["_capa"] in corte_activo
        estilos = [""] * len(row)
        if activo:
            estilos = [f"font-weight:700; background-color:rgba(232,163,61,.10);"] * len(row)
        return estilos

    def _color_columna_corte(val):
        color_map = {"500": CAPA_COLOR["meta_500"], "700": CAPA_COLOR["meta_700"], "865": CAPA_COLOR["meta_865"]}
        c = color_map.get(val, "#5b7a9e")
        return f"background-color:{c}; color:#14181f; font-weight:700; border-radius:4px; text-align:center;"

    _base_styler = df_ranking.style.apply(_resalta_corte_activo, axis=1)
    _color_fn = getattr(_base_styler, "map", None) or _base_styler.applymap
    styler = (
        _color_fn(_color_columna_corte, subset=["Corte"])
        .format({"LN estimada": "{:.1f}"})
        .hide(axis="columns", subset=["_capa"])
    )

    st.dataframe(styler, use_container_width=True, height=420, hide_index=True)
    st.caption(
        "Filas resaltadas: manzanas del corte actualmente seleccionado en la barra lateral. "
        "El ranking es por sección (no municipal) — la posición 1 siempre corresponde al corte 500."
    )