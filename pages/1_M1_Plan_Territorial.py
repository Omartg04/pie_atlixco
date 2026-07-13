"""
M1 — Plan Territorial
PIE Atlixco · Arturo Solano Escobedo · Proceso interno Morena
Mapa de 42 secciones + ficha de detalle + tabla de ranking (sincronizados).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from utils import (
    GLOBAL_CSS, COLOR, load_spt, load_geojson,
    score_color, fuente_tag_html, fmt_pct, fmt_num,
    ARQUETIPOS, DEFAULT_ARQUETIPO, check_password,
)

st.set_page_config(
    page_title="M1 · Plan Territorial · PIE Atlixco",
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

df = load_spt()
geo = load_geojson()

# ── Pesos de composición del índice por modo (acordados en Fase 2) ─────────
PESOS = {
    "A": {"ln": 35, "arquetipo": 35, "demografico": 20, "electoral": 10},
    "B": {"ln": 0, "arquetipo": 55, "demografico": 30, "electoral": 15},
}

# ── Promedios por zona, para el badge "por qué esta sección" ───────────────
ZONA_PROM = df.groupby("zona")[["pct_reconocimiento_arturo", "pct_conversion_preferencia"]].mean()

# ════════════════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="header-modulo">
  <div class="hm-dots"><span></span><span></span><span></span></div>
  <div class="hm-eyebrow">Módulo 01 · En operación</div>
  <h1>Plan Territorial</h1>
  <p>¿A dónde debe ir primero el equipo de Arturo Solano? Este mapa ordena las 42
  secciones de mayor a menor prioridad, y al elegir una te explica por qué,
  qué tanto lo conocen, qué tan bien convierte ese conocimiento en preferencia,
  y qué tipo de mensaje funciona mejor ahí.</p>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# FILTROS (selectores desplegables)
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### Buscar sección")
    todas_secciones = sorted(df["seccion"].tolist())
    buscar_sel = st.selectbox(
        "Ir directo a una sección",
        ["(ninguna)"] + todas_secciones,
        format_func=lambda s: "Escribe o elige..." if s == "(ninguna)" else f"Sección {s}",
    )

    st.markdown("### Filtros")

    zonas = ["Todas"] + sorted(df["zona"].dropna().unique().tolist())
    f_zona = st.selectbox("Zona", zonas)

    tipos = ["Todos"] + sorted(df["tipo_urbano_rural"].dropna().unique().tolist())
    f_tipo = st.selectbox("Tipo", tipos)

    f_alcance = st.radio(
        "Alcance",
        ["Todas", "Urbanas", "Rurales"],
        horizontal=True,
        help="Urbanas: secciones con detalle de manzana (Modo A). "
             "Rurales: secciones de barrido total por localidad (Modo B).",
    )

    perfiles = ["Todos"] + sorted(df["perfil_mensaje_sugerido"].dropna().unique().tolist())
    f_perfil = st.selectbox("Perfil de mensaje sugerido", perfiles)

    solo_alerta = st.checkbox("Solo secciones con alerta operativa", value=False)

df_f = df.copy()
if f_zona != "Todas":
    df_f = df_f[df_f["zona"] == f_zona]
if f_tipo != "Todos":
    df_f = df_f[df_f["tipo_urbano_rural"] == f_tipo]
if f_alcance == "Urbanas":
    df_f = df_f[df_f["modo_spt"] == "A"]
elif f_alcance == "Rurales":
    df_f = df_f[df_f["modo_spt"] == "B"]
if f_perfil != "Todos":
    df_f = df_f[df_f["perfil_mensaje_sugerido"] == f_perfil]
if solo_alerta:
    df_f = df_f[df_f["flag_alerta_operativa"] == True]

if df_f.empty:
    st.warning("No hay secciones que cumplan estos filtros.")
    st.stop()

lookup = df_f.set_index("seccion")
lookup_global = df.set_index("seccion")

# ════════════════════════════════════════════════════════════════════════════
# ESTADO DE SELECCIÓN (compartido entre mapa y tabla)
# ════════════════════════════════════════════════════════════════════════════

if "m1_sel_seccion" not in st.session_state:
    st.session_state["m1_sel_seccion"] = int(df_f.sort_values("ranking").iloc[0]["seccion"])

if buscar_sel != "(ninguna)":
    st.session_state["m1_sel_seccion"] = int(buscar_sel)

if st.session_state["m1_sel_seccion"] not in lookup.index:
    st.session_state["m1_sel_seccion"] = int(df_f.sort_values("ranking").iloc[0]["seccion"])


def set_seccion(sec: int) -> None:
    st.session_state["m1_sel_seccion"] = int(sec)


# ════════════════════════════════════════════════════════════════════════════
# FRASE "POR QUÉ ESTA SECCIÓN"
# ════════════════════════════════════════════════════════════════════════════

def frase_diagnostico(row: pd.Series) -> str:
    zona = row["zona"]
    if zona not in ZONA_PROM.index:
        return "Sin promedio de zona disponible para comparar."
    prom_recon = ZONA_PROM.loc[zona, "pct_reconocimiento_arturo"]
    prom_conv = ZONA_PROM.loc[zona, "pct_conversion_preferencia"]
    recon = row["pct_reconocimiento_arturo"]
    conv = row["pct_conversion_preferencia"]

    recon_alto = pd.notna(recon) and recon >= prom_recon
    conv_alto = pd.notna(conv) and conv >= prom_conv

    if conv_alto and not recon_alto:
        return "Conversión sólida con reconocimiento aún bajo — invertir en darse a conocer aquí rinde rápido."
    if recon_alto and not conv_alto:
        return "Ya la conocen, pero no se traduce en preferencia — foco en mensaje de conversión, no de exposición."
    if recon_alto and conv_alto:
        return "Sección fuerte: reconocimiento y conversión por arriba del promedio de su zona."
    return "Terreno por construir: reconocimiento y conversión por debajo del promedio de su zona."


# ════════════════════════════════════════════════════════════════════════════
# FICHA DE SECCIÓN (versión compacta — lateral al mapa)
# ════════════════════════════════════════════════════════════════════════════

def render_section_card_compacta(row: pd.Series) -> None:
    sc = float(row["indice_spt"])
    s_color = score_color(sc, df["indice_spt"].min(), df["indice_spt"].max())
    modo = row["modo_spt"]
    alerta = bool(row["flag_alerta_operativa"])
    arq = ARQUETIPOS.get(row["perfil_mensaje_sugerido"], DEFAULT_ARQUETIPO)

    alerta_html = '<span class="tag alerta">⚠ ALERTA OPERATIVA</span>' if alerta else ""
    alcance_txt = "Urbana/Mixta" if modo == "A" else "Rural (barrido total)"

    st.markdown(f"""
    <div class="card-wrap">
      <div style="background:linear-gradient(135deg,{COLOR['bg_raised_2']} 0%,{COLOR['bg_base']} 100%);
                  border:1px solid {COLOR['border_subtle']}; border-bottom:3px solid {s_color};
                  border-radius:10px 10px 0 0; padding:20px 24px;">
        <div style="font-family:'JetBrains Mono',monospace; font-size:.7rem; font-weight:700;
                    letter-spacing:.1em; text-transform:uppercase; color:{COLOR['text_secondary']}; margin-bottom:10px;">
          SECCIÓN {int(row.name)} · {row['zona']} · {alcance_txt}
        </div>
        <div style="display:flex; align-items:center; gap:20px; flex-wrap:wrap;">
          <div>
            <span style="font-family:'JetBrains Mono',monospace; font-size:2.4rem; font-weight:700; color:{s_color}; line-height:1;">
              {sc:.1f}
            </span>
            <span style="font-size:.78rem; color:{COLOR['text_muted']}; margin-left:4px;">/100</span>
          </div>
          <div style="flex:1; min-width:140px;">
            <div style="background:rgba(255,255,255,.1); border-radius:6px; height:9px; overflow:hidden; margin-bottom:6px;">
              <div style="height:100%; border-radius:6px; width:{min(sc,100):.0f}%; background:{s_color};"></div>
            </div>
            <div style="font-size:.8rem; color:{COLOR['text_secondary']};">
              Ranking #{int(row['ranking'])} de {len(df)}
            </div>
          </div>
        </div>
        <div style="margin-top:12px;">{alerta_html}</div>
      </div>

      <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']}; border-top:none;
                  padding:16px 24px; font-size:.82rem; color:{COLOR['text_secondary']}; line-height:1.5;">
        💡 {frase_diagnostico(row)}
      </div>

      <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']}; border-top:none;
                  border-radius:0 0 10px 10px; padding:18px 24px;">
        <div style="font-family:'JetBrains Mono',monospace; font-size:.64rem; font-weight:700; letter-spacing:.1em;
                    text-transform:uppercase; color:{COLOR['text_muted']}; margin-bottom:10px;">
          Segmento característico
        </div>
        <div style="display:flex; align-items:flex-start; gap:12px;">
          <span style="font-size:1.7rem; line-height:1;">{arq['icono']}</span>
          <div>
            <div style="font-size:.95rem; font-weight:700; color:{COLOR['text_primary']}; margin-bottom:3px;">
              {arq['nombre']}
            </div>
            <div style="font-size:.78rem; color:{COLOR['text_secondary']}; line-height:1.45; margin-bottom:8px;">
              {arq['desc']}
            </div>
            <div style="background:{COLOR['bg_raised_2']}; border-left:3px solid {COLOR['amber']};
                        border-radius:0 6px 6px 0; padding:8px 12px; font-size:.78rem; color:{COLOR['text_secondary']};">
              📣 {arq['mensaje']}<br>
              <span style="color:{COLOR['text_muted']};">Canal: {arq['canal']}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# BLOQUE DE DETALLE — debajo del mapa, a ancho completo
# ════════════════════════════════════════════════════════════════════════════

def render_detalle_completo(row: pd.Series) -> None:
    modo = row["modo_spt"]
    pesos = PESOS.get(modo, PESOS["A"])

    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace; font-size:.68rem; font-weight:700; letter-spacing:.1em;
                text-transform:uppercase; color:{COLOR['text_muted']}; margin:20px 0 12px;">
      Por qué esta sección — sección {int(row.name)}, variables de contexto
    </div>
    """, unsafe_allow_html=True)

    ctx_items = [
        ("Reconocimiento Arturo", fmt_pct(row["pct_reconocimiento_arturo"]), "", None),
        ("Conversión a preferencia", fmt_pct(row["pct_conversion_preferencia"]), fuente_tag_html(row["fuente_dato_conversion"]),
         "De quienes SÍ conocen a Arturo en esta sección, qué % lo prefiere como candidato interno de Morena "
         "sobre los otros 4 aspirantes. Alto = ya lo conocen y les convence; bajo = lo conocen pero no logra "
         "convertirse en preferencia."),
        ("Afectación por inseguridad", fmt_pct(row["pct_afectacion_inseguridad"]), fuente_tag_html(row["fuente_afectacion"]), None),
        ("Bloque Morena 2024", fmt_pct(row["pct_bloque_morena_2024"]), "", None),
        ("Grado prom. escolaridad", f"{row['GRAPROES']:.1f}" if pd.notna(row["GRAPROES"]) else "—", fuente_tag_html(row["fuente_dato_demografico"]), None),
        ("Población 60+", fmt_pct(row["pct_poblacion_60mas"]), "", None),
        ("Lista nominal 18+", fmt_num(row["P_18YMAS"]), "", None),
        ("LN agregada elegible", fmt_num(row["lista_nominal_agregada_elegible"]), "", None),
        ("Manzanas prioritarias", fmt_num(row["n_manzanas_prioritarias"]), "", None),
    ]

    cols = st.columns(3)
    for i, (label, val, tag, ayuda) in enumerate(ctx_items):
        with cols[i % 3]:
            ayuda_html = f'<span title="{ayuda}" style="cursor:help; color:{COLOR["text_muted"]}; font-size:.7rem;"> ⓘ</span>' if ayuda else ""
            st.markdown(f"""
            <div style="background:{COLOR['bg_raised_2']}; border:1px solid {COLOR['border_subtle']};
                        border-radius:8px; padding:14px 14px; text-align:center; margin-bottom:12px;">
              <div style="font-family:'JetBrains Mono',monospace; font-size:1.25rem; font-weight:700; color:{COLOR['text_primary']};">{val}</div>
              <div style="font-size:.7rem; color:{COLOR['text_muted']}; margin-top:3px; line-height:1.3;">{label}{ayuda_html}</div>
              <div style="margin-top:4px;">{tag}</div>
            </div>
            """, unsafe_allow_html=True)

    st.caption(
        "💬 **% Conversión** = de quienes ya conocen a Arturo, qué porcentaje lo prefiere como "
        "candidato interno de Morena frente a los otros 4 aspirantes. Es el indicador más importante "
        "del SPT: una sección con reconocimiento bajo pero conversión alta rinde más rápido que una "
        "con reconocimiento alto que no logra convertirse en preferencia."
    )

    comp_segments = [
        ("LN por manzana", pesos["ln"], "#e8a33d"),
        ("Arquetipos/encuesta", pesos["arquetipo"], "#5b7a9e"),
        ("Demográfico (censo)", pesos["demografico"], "#3f7a52"),
        ("Electoral (histórico)", pesos["electoral"], "#8b95a8"),
    ]
    bar_html = "".join(
        f'<div style="width:{w}%; background:{c};" title="{label}: {w}%"></div>'
        for label, w, c in comp_segments if w > 0
    )
    legend_html = "".join(
        f'<span style="display:inline-flex; align-items:center; gap:5px; margin-right:14px; font-size:.72rem; color:{COLOR["text_secondary"]};">'
        f'<span style="width:9px; height:9px; border-radius:2px; background:{c}; display:inline-block;"></span>{label} · {w}%</span>'
        for label, w, c in comp_segments if w > 0
    )
    st.markdown(f"""
    <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']};
                border-radius:10px; padding:16px 20px; margin-top:4px;">
      <div style="font-family:'JetBrains Mono',monospace; font-size:.64rem; font-weight:700; letter-spacing:.1em;
                  text-transform:uppercase; color:{COLOR['text_muted']}; margin-bottom:10px;">
        Composición del índice — {"Urbana/Mixta" if modo == "A" else "Rural"}
      </div>
      <div style="display:flex; height:14px; border-radius:7px; overflow:hidden; margin-bottom:10px;">
        {bar_html}
      </div>
      <div>{legend_html}</div>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# MAPA
# ════════════════════════════════════════════════════════════════════════════

def build_map(df_sel: pd.DataFrame, geo: dict, vmin: float, vmax: float, sel_seccion: int = None) -> folium.Map:
    ids_sel = set(df_sel["seccion"].tolist())

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

    feat_sel = None
    if sel_seccion is not None:
        feat_sel = next(
            (f for f in geo["features"] if f["properties"].get("seccion") == sel_seccion), None
        )

    if feat_sel is not None:
        center = _centroid([feat_sel]) or [18.9, -98.43]
        zoom = 16
    else:
        center = _centroid(geo["features"]) or [18.9, -98.43]
        zoom = 13

    m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB dark_matter")
    lookup_sel = df_sel.set_index("seccion")

    def style_fn(feature):
        sec = feature["properties"].get("seccion")
        base = {"fillColor": "#2a3140", "color": "#3a4255", "weight": .5, "fillOpacity": .15}
        if sec not in ids_sel:
            return base
        val = lookup_sel.loc[sec, "indice_spt"]
        color = score_color(val, vmin, vmax)
        style = {"fillColor": color, "color": "#0f1218", "weight": 1, "fillOpacity": .75}
        if sec == sel_seccion:
            style["color"] = "#eef1f0"
            style["weight"] = 3
        return style

    def highlight_fn(feature):
        return {"weight": 2.5, "color": "#eef1f0", "fillOpacity": .9}

    TOOLTIP_DEFAULTS = {
        "Ranking": "—", "Índice SPT": "—", "Zona": "—", "Modo": "—",
        "Reconocimiento": "—", "Conversión": "—", "Perfil": "sin datos SPT",
    }

    geo_rich = {"type": "FeatureCollection", "features": []}
    for feat in geo["features"]:
        f2 = dict(feat)
        f2["properties"] = dict(feat["properties"])
        f2["properties"].update(TOOLTIP_DEFAULTS)
        sec = f2["properties"].get("seccion")
        if sec in ids_sel:
            r = lookup_sel.loc[sec]
            f2["properties"].update({
                "Ranking": f"#{int(r['ranking'])}",
                "Índice SPT": f"{r['indice_spt']:.1f}",
                "Zona": str(r["zona"]),
                "Modo": "Urbana/Mixta" if r["modo_spt"] == "A" else "Rural",
                "Reconocimiento": fmt_pct(r["pct_reconocimiento_arturo"]),
                "Conversión": fmt_pct(r["pct_conversion_preferencia"]),
                "Perfil": str(r["perfil_mensaje_sugerido"]),
            })
        geo_rich["features"].append(f2)

    folium.GeoJson(
        geo_rich,
        style_function=style_fn,
        highlight_function=highlight_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["seccion", "Ranking", "Índice SPT", "Zona", "Modo", "Reconocimiento", "Conversión", "Perfil"],
            aliases=["Sección", "Ranking", "Índice SPT", "Zona", "Modo", "Reconoc.", "Conversión", "Perfil"],
            sticky=True, labels=True,
            style="font-family:'DM Sans',sans-serif; font-size:12.5px; background:#1b212b; "
                  "color:#eef1f0; border:1px solid #3a4255; border-radius:6px;",
            max_width=260,
        ),
        name="secciones",
    ).add_to(m)

    return m


# ════════════════════════════════════════════════════════════════════════════
# LAYOUT PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

tab_mapa, tab_tabla = st.tabs(["🗺️ Mapa", "📋 Tabla / ranking"])

with tab_mapa:
    vmin, vmax = df_f["indice_spt"].min(), df_f["indice_spt"].max()

    # ── Barra de intensidad ARRIBA del mapa ──
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px; font-size:.76rem; color:{COLOR['text_muted']};">
      <span>Baja prioridad</span>
      <div style="flex:1; height:8px; border-radius:4px;
                  background:linear-gradient(90deg,#5b7a9e 0%,#8a8564 50%,#e8a33d 100%);"></div>
      <span>Alta prioridad</span>
    </div>
    <div style="font-size:.72rem; color:{COLOR['text_muted']}; margin-bottom:14px;">
      Colores más brillantes (ámbar) = mayor índice SPT = mayor prioridad territorial.
      Secciones en gris no forman parte del filtro activo. Rango actual: {vmin:.1f}–{vmax:.1f}.
    </div>
    """, unsafe_allow_html=True)

    col_map, col_card = st.columns([1.4, 1], gap="medium")

    with col_map:
        sel_actual = st.session_state["m1_sel_seccion"]
        m = build_map(df_f, geo, vmin, vmax, sel_seccion=sel_actual)
        map_out = st_folium(m, height=520, use_container_width=True, key=f"m1_map_{sel_actual}")

        if map_out and map_out.get("last_active_drawing"):
            props = map_out["last_active_drawing"].get("properties", {})
            sec = props.get("seccion")
            if sec in lookup.index and sec != st.session_state["m1_sel_seccion"]:
                set_seccion(sec)
                st.rerun()

    with col_card:
        render_section_card_compacta(lookup.loc[st.session_state["m1_sel_seccion"]])

    render_detalle_completo(lookup.loc[st.session_state["m1_sel_seccion"]])

with tab_tabla:
    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace; font-size:.7rem; color:{COLOR['text_muted']}; margin-bottom:10px;">
      {len(df_f)} secciones bajo los filtros activos · haz clic en una fila para ver su ficha en el mapa
    </div>
    """, unsafe_allow_html=True)

    tabla = df_f.sort_values("ranking")[[
        "ranking", "seccion", "zona", "tipo_urbano_rural", "modo_spt", "indice_spt",
        "flag_alerta_operativa", "pct_reconocimiento_arturo", "pct_conversion_preferencia",
        "perfil_mensaje_sugerido",
    ]].rename(columns={
        "ranking": "Ranking", "seccion": "Sección", "zona": "Zona",
        "tipo_urbano_rural": "Tipo", "modo_spt": "Modo", "indice_spt": "Índice SPT",
        "flag_alerta_operativa": "Alerta", "pct_reconocimiento_arturo": "% Reconoc.",
        "pct_conversion_preferencia": "% Conversión", "perfil_mensaje_sugerido": "Perfil de mensaje",
    })

    evento = st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Índice SPT": st.column_config.ProgressColumn(
                "Índice SPT", min_value=0, max_value=float(df["indice_spt"].max()), format="%.1f"
            ),
        },
    )

    if evento and evento.selection and evento.selection.get("rows"):
        fila_idx = evento.selection["rows"][0]
        sec_tabla = int(tabla.iloc[fila_idx]["Sección"])
        if sec_tabla != st.session_state["m1_sel_seccion"]:
            set_seccion(sec_tabla)
            st.rerun()

    st.info(f"Ficha activa: **Sección {st.session_state['m1_sel_seccion']}** — cámbiala aquí o en el mapa.", icon="📌")