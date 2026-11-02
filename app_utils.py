"""
PIE Atlixco — utilidades compartidas
Sistema de diseño: esquema oscuro neutro (sin color partidista), inspirado en el
mockup de referencia (index.html) pero con paleta propia ámbar/acero.
"""

import os
import json

import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ════════════════════════════════════════════════════════════════════════════
# PALETA — lineamiento de marca del proyecto (fija, no se cambia por módulo)
# ════════════════════════════════════════════════════════════════════════════

COLOR = {
    "bg_base":       "#14181f",
    "bg_raised":     "#1b212b",
    "bg_raised_2":   "#202836",
    "border_subtle": "rgba(255,255,255,.08)",
    "border_strong": "rgba(255,255,255,.16)",
    "text_primary":  "#eef1f0",
    "text_secondary": "#8b95a8",
    "text_muted":    "#5e6779",
    "amber":         "#e8a33d",   # acento primario — prioridad / score
    "steel":         "#5b7a9e",   # acento secundario — informativo / navegación
    "green":         "#3f7a52",   # positivo / dato "sección" (no imputado)
    "green_text":    "#5fae78",
    "red_soft":      "#c4703f",   # alerta operativa (no partidista: ámbar-terracota)
    # ── Escala tonal de cortes de manzana (M2) — acumulativos, misma familia ámbar ──
    "corte_500":     "#a8681f",   # oscuro/saturado — núcleo, máxima prioridad
    "corte_700":     "#e8a33d",   # = amber base — prioridad media
    "corte_865":     "#f6d9a8",   # claro/desaturado — cierre de universo elegible
}

# ════════════════════════════════════════════════════════════════════════════
# BASEMAP — CARTO ahora exige API key en los tiles raster (si falta, sale el
# watermark "API KEY REQUIRED" sobre el mapa). Se toma de
# st.secrets["carto"]["api_key"] si existe; si no, cae al key que Omar
# compartió como respaldo para no romper el mapa mientras se agrega a
# secrets.toml. Recomendado: mover el key a .streamlit/secrets.toml (mismo
# patrón que ya se usa para [bubble]) y quitar el fallback de aquí.
# ════════════════════════════════════════════════════════════════════════════
_CARTO_API_KEY_FALLBACK = "cb1_2vkv_1_663774fb3312be33ef90a6d2"
CARTO_API_KEY = st.secrets.get("carto", {}).get("api_key", _CARTO_API_KEY_FALLBACK)
CARTO_ATTR = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
    'contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
)


def carto_tiles(style: str = "dark_all") -> str:
    """URL de tiles raster de CARTO con API key incluida, lista para pasarse a
    folium.Map(tiles=carto_tiles(), attr=CARTO_ATTR). Estilo por default:
    dark_all (el que usan M3/M4 hoy, vía el alias "CartoDB dark_matter" que
    ya no funciona sin key). Otros estilos: "light_all", o "rastertiles/voyager"
    (voyager usa un path distinto al de dark_all/light_all)."""
    return f"https://basemaps.cartocdn.com/{style}/{{z}}/{{x}}/{{y}}.png?key={CARTO_API_KEY}"


FONT_DISPLAY = "'Barlow Condensed', sans-serif"
FONT_BODY = "'DM Sans', sans-serif"
FONT_MONO = "'JetBrains Mono', monospace"

GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');

html, body, [class*="css"] {{ font-family: {FONT_BODY}; }}

.stApp {{ background: {COLOR['bg_base']}; }}

[data-testid="stSidebar"] {{
    background-color: {COLOR['bg_raised']} !important;
    border-right: 1px solid {COLOR['border_subtle']};
}}
[data-testid="stSidebar"] *, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] div, [data-testid="stSidebar"] label {{
    color: {COLOR['text_primary']} !important;
}}

h1, h2, h3 {{ color: {COLOR['text_primary']} !important; }}
p, span, div {{ color: {COLOR['text_secondary']}; }}

/* ── Contraste de widgets (selectbox, radio, checkbox, inputs) ── */
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {{
    background-color: {COLOR['bg_raised_2']} !important;
    border: 1px solid {COLOR['border_strong']} !important;
    color: {COLOR['text_primary']} !important;
}}
[data-baseweb="select"] span,
[data-baseweb="select"] div {{
    color: {COLOR['text_primary']} !important;
}}
/* El menú desplegable se renderiza en un portal fuera del sidebar */
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="popover"] ul {{
    background-color: {COLOR['bg_raised_2']} !important;
    border: 1px solid {COLOR['border_strong']} !important;
}}
[data-baseweb="popover"] li,
[data-baseweb="popover"] li span,
[data-baseweb="popover"] [role="option"] {{
    background-color: {COLOR['bg_raised_2']} !important;
    color: {COLOR['text_primary']} !important;
}}
[data-baseweb="popover"] li:hover,
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [aria-selected="true"] {{
    background-color: {COLOR['bg_base']} !important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label p {{
    color: {COLOR['text_secondary']} !important;
}}
div[role="radiogroup"] label {{ color: {COLOR['text_primary']} !important; }}

/* ── Header de módulo ── */
.header-modulo {{
    --accent: {COLOR['amber']};
    background: {COLOR['bg_raised']};
    padding: 28px 32px 24px; border-radius: 8px; margin-bottom: 22px;
    position: relative; overflow: hidden;
    border-bottom: 2px solid var(--accent);
    border: 1px solid {COLOR['border_subtle']};
    border-bottom: 2px solid var(--accent);
}}
.header-modulo::after {{
    content: ''; position: absolute; top: -45px; right: -45px;
    width: 180px; height: 180px; border-radius: 50%; background: rgba(255,255,255,0.03);
}}
.header-modulo .hm-eyebrow {{
    font-family: {FONT_MONO}; font-size: 0.68rem; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent); margin-bottom: 8px;
}}
.header-modulo h1 {{
    font-family: {FONT_DISPLAY}; font-weight: 800; text-transform: uppercase;
    color: {COLOR['text_primary']} !important; font-size: 1.9rem; letter-spacing: -0.005em;
    margin: 0 0 6px; line-height: 1.05;
}}
.header-modulo p {{ color: {COLOR['text_secondary']}; font-size: 0.92rem; margin: 0; max-width: 660px; line-height: 1.5; }}
.header-modulo .hm-dots {{ position: absolute; right: 28px; top: 26px; display: flex; gap: 6px; }}
.header-modulo .hm-dots span {{ width: 5px; height: 5px; border-radius: 50%; background: var(--accent); opacity: 0.5; }}
.header-modulo .hm-dots span:first-child {{ opacity: 1; }}

/* ── Tags de procedencia del dato ── */
.tag {{
    font-family: {FONT_MONO}; display: inline-block; font-size: 0.62rem; font-weight: 700;
    padding: 2px 8px; border-radius: 3px; margin-right: 4px; letter-spacing: 0.05em;
    text-transform: uppercase; vertical-align: middle;
}}
.tag.seccion  {{ background: rgba(95,174,120,.16); color: {COLOR['green_text']}; border: 1px solid rgba(95,174,120,.35); }}
.tag.zona     {{ background: rgba(139,149,168,.14); color: {COLOR['text_secondary']}; border: 1px solid {COLOR['border_strong']}; }}
.tag.alerta   {{ background: rgba(196,112,63,.18); color: #e88a5d; border: 1px solid rgba(196,112,63,.4); }}

/* ── KPI cards ── */
.kpi-card {{
    background: {COLOR['bg_raised']}; border-left: 3px solid {COLOR['amber']};
    border-radius: 0 8px 8px 0; padding: 14px 16px; height: 100%;
    border: 1px solid {COLOR['border_subtle']}; border-left: 3px solid {COLOR['amber']};
}}
.kpi-val   {{ font-family: {FONT_MONO}; font-size: 1.6rem; font-weight: 700; color: {COLOR['text_primary']}; line-height: 1.1; }}
.kpi-label {{ font-size: 0.78rem; font-weight: 600; color: {COLOR['text_primary']}; margin-top: 4px; }}
.kpi-ctx   {{ font-size: 0.72rem; color: {COLOR['text_muted']}; margin-top: 2px; line-height: 1.3; }}

/* ── Teaser card (módulo pendiente) ── */
.teaser-card {{
    background: {COLOR['bg_raised']};
    border: 1px dashed {COLOR['border_strong']}; border-radius: 14px;
    padding: 40px 40px; text-align: center; margin-top: 16px;
}}
.teaser-card h3 {{ font-family: {FONT_DISPLAY}; font-weight:700; font-size: 1.3rem; color: {COLOR['text_primary']}; margin-bottom: 10px; }}
.teaser-card p  {{ font-size: 0.88rem; color: {COLOR['text_secondary']}; line-height: 1.65; margin: 0 auto; max-width: 520px; }}
.teaser-chip {{
    display: inline-block; background: {COLOR['bg_raised_2']}; border: 1px solid {COLOR['border_strong']};
    border-radius: 10px; padding: 8px 18px; font-size: 0.8rem;
    color: {COLOR['text_primary']}; font-weight: 600; margin: 4px; font-family: {FONT_MONO};
}}

/* ── Station cards (Home) ── */
.stations-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:1px;
    background:{COLOR['border_subtle']}; border:1px solid {COLOR['border_subtle']}; border-radius:8px; overflow:hidden; }}
.station {{ background:{COLOR['bg_raised']}; padding:26px 24px; }}
.station-num {{ font-family:{FONT_MONO}; font-size:.85rem; color:{COLOR['text_muted']}; }}
.station-status {{ font-family:{FONT_MONO}; font-size:.64rem; font-weight:700; letter-spacing:.06em;
    display:flex; align-items:center; gap:6px; float:right; }}
.station-status.on {{ color:{COLOR['green_text']}; }}
.station-status.pending {{ color:{COLOR['text_muted']}; }}
.station-status i {{ width:6px; height:6px; border-radius:50%; display:inline-block; }}
.station-status.on i {{ background:{COLOR['green_text']}; }}
.station-status.pending i {{ background:{COLOR['text_muted']}; }}
.station-tag {{ font-family:{FONT_MONO}; font-size:.7rem; font-weight:700; letter-spacing:.06em;
    text-transform:uppercase; color:{COLOR['amber']}; margin-bottom:8px; }}
.station h3 {{ font-family:{FONT_DISPLAY}; font-weight:700; font-size:1.35rem; color:{COLOR['text_primary']};
    margin:0 0 8px; line-height:1.2; }}
.station p {{ color:{COLOR['text_secondary']}; font-size:.87rem; line-height:1.55; margin:0; }}

/* ── Ficha de sección (card blanca sobre fondo oscuro, alto contraste legible) ── */
.card-wrap {{ font-family: {FONT_BODY}; max-width: 100%; }}
</style>
"""


# ════════════════════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_spt() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "SPT_indice_secciones_enriquecido.csv")
    df = pd.read_csv(path)
    df["seccion"] = df["seccion"].astype(int)
    return df


@st.cache_data
def load_geojson() -> dict:
    path = os.path.join(DATA_DIR, "atlixco_secciones_zonas.geojson")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_manzanas() -> dict:
    """Geojson de manzanas/localidades con capas de priorización 500/700/865.
    Cada feature trae ademas colonia_nombre/colonia_tipo/colonia_cvegeo/
    origen_colonia (INEGI/INE/None) para las unidades dentro de las 37
    secciones en_alcance_42_secciones — ver memoria_calculo_modulo_colonias_atlixco.md."""
    path = os.path.join(DATA_DIR, "atlixco_unificado_web_capas.geojson")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_colonias_geojson() -> dict:
    """Geojson de poligonos de colonia (INEGI 2025 + rescatadas del INE donde
    INEGI no tenia cobertura), en WGS84, listo para folium. Usado por M4
    (cobertura por colonia). Ver memoria_calculo_modulo_colonias_atlixco.md
    para la metodologia del cruce manzana->colonia."""
    path = os.path.join(DATA_DIR, "colonias_atlixco_web.geojson")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_priorizacion_secciones() -> pd.DataFrame:
    """Insumo LN por manzana agregado a nivel sección (37 secciones Modo A)."""
    path = os.path.join(DATA_DIR, "secciones_priorizacion_865.xlsx")
    df = pd.read_excel(path, sheet_name="Priorizacion 865", engine="openpyxl")
    df.columns = [
        "ranking", "seccion", "tipo", "ln_real_seccion", "n_manzanas_totales",
        "n_manzanas_elegibles", "ln_agregada_elegibles", "pct_ln_elegibles",
        "ln_promedio_manzana", "piso_minimo", "techo_maximo", "minimo_garantizado",
    ]
    n_antes = len(df)
    df = df[df["seccion"].notna()].copy()
    n_descartadas = n_antes - len(df)
    if n_descartadas:
        st.warning(
            f"⚠️ Se descartaron {n_descartadas} fila(s) sin número de sección válido "
            "en secciones_priorizacion_865.xlsx (probable fila de notas/total al final "
            "de la hoja). Revisa el archivo si esperabas ver las 37 secciones completas.",
            icon="⚠️",
        )
    df["seccion"] = df["seccion"].astype(int)
    return df


# ── Insumos del marco V2 (octubre 2026) — M1 Planeación Territorial ─────────
# Cuatro archivos ligeros que SUSTITUYEN al índice SPT como insumo de
# priorización. El tablero deliberadamente NO carga
# pie_019_atlixco_unificado_v2.geojson (3.5 MB, 3,282 polígonos de manzana):
# la geometría de manzana vive en los KML de My Maps, que es donde el
# brigadista la necesita. Aquí solo entran propiedades y los 70 contornos.
#
# Llaves, para no confundirlas:
#   SECCION       — las 74 secciones vigentes (sin 160, con 3119-3123)
#   seccion_geom  — la llave de dibujo, 70 polígonos (con 160, sin las nuevas).
#                   Las 5 del bloque 160R comparten el polígono de la 160.

@st.cache_data
def load_m1_secciones() -> pd.DataFrame:
    """74 secciones con IRE, capa de LN, caracterización electoral y de edad,
    y el agregado de manzanas prioritarias. Ordenado por RANKING_IRE."""
    path = os.path.join(DATA_DIR, "m1_secciones.csv")
    df = pd.read_csv(path)
    df["SECCION"] = df["SECCION"].astype(int)
    df["seccion_geom"] = df["seccion_geom"].astype(int)
    return df.sort_values("RANKING_IRE").reset_index(drop=True)


@st.cache_data
def load_m1_manzanas() -> pd.DataFrame:
    """969 unidades: 692 manzanas del corte al 50% + 277 del bloque 160R
    (estas últimas sin LN asignada, regla §13.3 del SOP de crosswalk).
    Sin geometría. La llave 'seccion' es seccion_geom, no la vigente."""
    path = os.path.join(DATA_DIR, "m1_manzanas_prioritarias.csv")
    df = pd.read_csv(path)
    df["seccion"] = df["seccion"].astype(int)
    df["manzana"] = df["manzana"].astype(int)
    return df


@st.cache_data
def load_m1_contornos() -> dict:
    """70 contornos de sección con la capa de LN y el ranking para el
    coroplético. El polígono de la 160 lleva la mejor capa de sus 5 secciones
    vigentes y queda marcado con es_bloque=1."""
    path = os.path.join(DATA_DIR, "m1_contornos.geojson")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_mapas_catalogo() -> pd.DataFrame:
    """Catálogo de mapas de campo: una fila por sección vigente con la URL
    /viewer de My Maps. Sustituye la lista MAPAS_CAMPO hardcodeada — actualizar
    un mapa es editar un CSV, no el código."""
    path = os.path.join(DATA_DIR, "mapas_catalogo.csv")
    df = pd.read_csv(path, dtype={"url_my_maps_viewer": str})
    df["seccion"] = df["seccion"].astype(int)
    return df


def ahora_mexico() -> "datetime":
    """Hora local de Ciudad de México. Streamlit Cloud corre en UTC, así que
    datetime.now() a secas adelanta el día seis horas."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Mexico_City"))


# ── Avance de campo desde Kobo ──────────────────────────────────────────────
# El operativo de inducción captura en KoboToolbox con el XLSForm v0.6
# (form_id=atlixco_visitas_20261028_v01). El conector del paquete v1.2 se usa
# como librería: fetch_all() trae los envíos y transform() los agrega. No se
# escriben ni se leen CSV — la tabla vive en memoria el tiempo del cacheo.
#
# El token NUNCA va en el repo. Vive en st.secrets["kobo"]["api_token"].
#
# Estados, decididos con el coordinador:
#   sin_iniciar  0 entrevistas
#   en_proceso   1 .. meta-1
#   cubierta     >= meta
#
# La meta son 11 brigadistas x 25 entrevistas = 275 por sección. Dos secciones
# tienen menos electores que eso en toda su lista nominal (156 con 186 y 172
# con 271): ahí la meta es su propia LN, porque no se puede entrevistar a más
# gente de la que vive en la sección. Sin ese ajuste quedarían en "en proceso"
# para siempre.
#
# "Entrevista" = visita con contacto real: completas + parciales. Un rechazo o
# una casa sola son visitas, no entrevistas.

META_ENTREVISTAS_SECCION = 275
BRIGADISTAS_ESPERADOS = 11
META_POR_BRIGADISTA = 25
RESULTADOS_QUE_CUENTAN = ("completas", "parciales")

# Polling recomendado por el paquete del conector.
KOBO_TTL_SEG = 300

# ── Umbrales de calidad (M3) ────────────────────────────────────────────────
# Racha de capturas rápidas: N entrevistas seguidas del mismo brigadista el
# mismo día por debajo del umbral. Solo cuentan completas y parciales — un
# rechazo o una casa sola de 30 segundos es lo normal, no una señal.
UMBRAL_DURACION_RAPIDA_MIN = 2.0
MIN_RACHA_RAPIDA = 3


def meta_de_seccion(ln_seccion: float | int | None) -> int:
    """Meta de entrevistas de una sección, acotada por su lista nominal."""
    try:
        ln = int(ln_seccion)
    except (TypeError, ValueError):
        return META_ENTREVISTAS_SECCION
    return min(META_ENTREVISTAS_SECCION, ln) if ln > 0 else META_ENTREVISTAS_SECCION


TABLAS_KOBO = ("visitas_operativas", "resumen_diario",
               "productividad_brigadista", "cobertura_seccion",
               "respuestas_agregadas")


@st.cache_data(ttl=KOBO_TTL_SEG, show_spinner=False)
def load_kobo_tablas() -> tuple[dict, dict, str]:
    """Una sola consulta a Kobo, compartida por M1 y M3.

    Devuelve ({nombre: DataFrame}, estado, error). M1 usa cobertura_seccion;
    M3 usa el resto. Al estar cacheada aquí, abrir los dos módulos no dispara
    dos llamadas a la API.
    """
    vacias = {t: pd.DataFrame() for t in TABLAS_KOBO}
    cfg = st.secrets.get("kobo", {})
    base = str(cfg.get("base_url", "") or "").strip()
    uid = str(cfg.get("asset_uid", "") or "").strip()
    token = str(cfg.get("api_token", "") or "").strip()
    if not (base and uid and token):
        return vacias, {}, ""

    try:
        import json as _json
        import kobo_connector as kc

        with open(os.path.join(BASE_DIR, "schema_xlsform_v06.json"),
                  encoding="utf-8") as fh:
            schema = _json.load(fh)
        envios = kc.fetch_all(base, uid, token)
        datos = kc.transform(envios, schema)
    except Exception as exc:
        return vacias, {}, f"{type(exc).__name__}: {exc}"

    tablas = {t: pd.DataFrame(datos.get(t, [])) for t in TABLAS_KOBO}

    # El conector conserva las visitas con seccion_fuera_catalogo en
    # visitas_operativas, pero arma cobertura_seccion solo sobre las 70 del
    # catálogo: esas visitas no suman a ninguna sección. Se cuadra el total
    # contra estado.json para que no se pierdan en silencio. Va aquí y no en la
    # vista de M1 porque es una propiedad del extracto: M3 la necesita igual.
    estado = dict(datos.get("estado", {}))
    unicos = int(estado.get("registros_unicos", 0) or 0)
    cob = tablas.get("cobertura_seccion", pd.DataFrame())
    en_cobertura = int(pd.to_numeric(cob.get("visitas"), errors="coerce").fillna(0).sum()) \
        if not cob.empty else 0
    estado["visitas_en_cobertura"] = en_cobertura
    estado["visitas_sin_seccion_valida"] = max(0, unicos - en_cobertura)
    return tablas, estado, ""


def limpiar_cache_kobo() -> None:
    """Fuerza la relectura de Kobo desde cualquier módulo."""
    load_kobo_tablas.clear()
    load_kobo.clear()


@st.cache_data(ttl=KOBO_TTL_SEG, show_spinner=False)
def load_kobo() -> tuple[pd.DataFrame, dict, str]:
    """Avance por sección desde Kobo. Devuelve (df, estado, error).

    df: una fila por seccion_operativa (la llave de 70, con la 160 agrupando
    3119-3123) con entrevistas/visitas/resultados. estado: el bloque de
    integridad del conector. Si error no está vacío, df viene vacío y la capa
    debe desactivarse — NO significa que no haya avance.
    """
    vacio = pd.DataFrame(columns=["seccion_operativa", "entrevistas", "visitas",
                                  "completas", "parciales", "rechazos",
                                  "casas_solas"])
    tablas, estado_raw, error = load_kobo_tablas()
    if error:
        return vacio, {}, error

    df = tablas.get("cobertura_seccion", pd.DataFrame()).copy()
    if df.empty:
        return vacio, estado_raw, ""
    datos = {"estado": estado_raw}

    df["seccion_operativa"] = pd.to_numeric(df["seccion_operativa"], errors="coerce")
    df = df[df["seccion_operativa"].notna()].copy()
    df["seccion_operativa"] = df["seccion_operativa"].astype(int)
    for col in ("visitas", "completas", "parciales", "rechazos", "casas_solas"):
        df[col] = pd.to_numeric(df.get(col), errors="coerce").fillna(0).astype(int)
    df["entrevistas"] = sum(df[c] for c in RESULTADOS_QUE_CUENTAN)
    return df, datos["estado"], ""


# ── Cobertura declarada por el coordinador ──────────────────────────────────
# "Cubierta" = una brigada ya trabajó esa sección. Es una declaración, no un
# dato derivado: no hay meta por sección contra la cual calcular avance, y el
# conector de Kobo todavía no existe. Puede reabrirse: basta cambiar o borrar
# la fila en la hoja.
#
# Fuente, en orden de preferencia:
#   1. st.secrets["cobertura"]["url"] — Google Sheet publicada como CSV. La URL
#      vive en secrets y no en el repo.
#   2. data/cobertura_secciones.csv — respaldo local, para desarrollo o si se
#      decide dejar de usar la hoja.
#   3. Nada — la capa de cobertura se desactiva y el mapa muestra todo. NUNCA
#      se esconde una sección por un fallo de lectura: eso haría que un día sin
#      conexión se leyera como "ya cubrimos todo". Mismo criterio que L3.
#
# El cacheo es corto a propósito: el coordinador marca en su teléfono y espera
# ver el cambio al recargar, no en media hora.

ESTADOS_COBERTURA = ("cubierta", "en_proceso")

_ALIAS_COLUMNAS = {
    "seccion": {"seccion", "sección", "seccion_electoral", "sec", "section"},
    "estado": {"estado", "status", "cobertura", "estatus"},
    "fecha": {"fecha", "date", "dia", "día"},
    "nota": {"nota", "notas", "comentario", "comentarios", "observaciones"},
}


def _normaliza_columna(nombre: str) -> str | None:
    limpio = str(nombre).strip().lower().replace(" ", "_")
    for canonico, alias in _ALIAS_COLUMNAS.items():
        if limpio in alias:
            return canonico
    return None


# Lo que cuenta como marca afirmativa en la columna de estado. La hoja la llena
# una persona en su teléfono: hay que aceptar lo que escribiría de verdad, no
# solo la palabra canónica.
_MARCAS_CUBIERTA = {"cubierta", "cubierto", "si", "sí", "x", "1", "true",
                    "listo", "ok", "hecho", "terminada", "terminado"}
_MARCAS_PROCESO = {"en_proceso", "proceso", "en_curso", "curso", "parcial",
                   "trabajando", "2"}


@st.cache_data(ttl=120, show_spinner=False)
def load_cobertura() -> tuple[pd.DataFrame, str, str, list[str]]:
    """Lee la cobertura declarada. Devuelve (df, origen, error, no_reconocidos).

    df trae columnas seccion/estado/fecha/nota, con estado ya normalizado a
    uno de ESTADOS_COBERTURA. Una sección ausente de la hoja, o con la celda
    de estado VACÍA, es 'sin_iniciar': la hoja se reparte prellenada con las
    74 secciones y la celda vacía es el estado de arranque.

    no_reconocidos lista los valores de estado que no se pudieron interpretar.
    No se adivinan: una celda con un typo se reporta en vez de marcarse, para
    que nadie dé por cubierta una sección por una palabra mal escrita.

    Si error no está vacío, la capa de cobertura debe desactivarse y mostrarse
    el aviso: df viene vacío y NO significa que nada esté cubierto.
    """
    vacio = pd.DataFrame(columns=["seccion", "estado", "fecha", "nota"])

    url = str(st.secrets.get("cobertura", {}).get("url", "") or "").strip()
    local = os.path.join(DATA_DIR, "cobertura_secciones.csv")

    if url:
        origen, fuente = "hoja", url
    elif os.path.exists(local):
        origen, fuente = "archivo", local
    else:
        return vacio, "ninguna", "", []

    try:
        df = pd.read_csv(fuente, dtype=str)
    except Exception as exc:  # red caída, hoja despublicada, permisos, HTML
        return vacio, origen, f"{type(exc).__name__}: {exc}", []

    renombres = {c: _normaliza_columna(c) for c in df.columns}
    df = df.rename(columns={k: v for k, v in renombres.items() if v})
    if "seccion" not in df.columns:
        return vacio, origen, (
            "La hoja no tiene una columna de sección. Columnas encontradas: "
            + ", ".join(str(c) for c in df.columns)
        ), []

    for col in ("estado", "fecha", "nota"):
        if col not in df.columns:
            df[col] = ""
    df = df[["seccion", "estado", "fecha", "nota"]].fillna("")

    df["seccion"] = pd.to_numeric(df["seccion"], errors="coerce")
    df = df[df["seccion"].notna()].copy()
    df["seccion"] = df["seccion"].astype(int)

    est = df["estado"].astype(str).str.strip().str.lower().str.replace(" ", "_")

    # Celda vacía = sin iniciar. La hoja va prellenada con las 74 secciones, así
    # que el estado de arranque de cada fila es el vacío. Interpretarlo como
    # cubierta daría el municipio entero por trabajado desde el día uno.
    df = df[est != ""].copy()
    est = est[est != ""]

    no_reconocidos = sorted(set(est[~est.isin(_MARCAS_CUBIERTA | _MARCAS_PROCESO)]))
    df["estado"] = est.map(
        lambda v: "cubierta" if v in _MARCAS_CUBIERTA
        else ("en_proceso" if v in _MARCAS_PROCESO else None)
    )
    df = df[df["estado"].notna()].copy()

    # Si una sección aparece dos veces, manda la última fila de la hoja: es la
    # más reciente desde el punto de vista de quien la escribió.
    df = df.drop_duplicates(subset=["seccion"], keep="last").reset_index(drop=True)
    return df, origen, "", no_reconocidos


# ════════════════════════════════════════════════════════════════════════════
# HELPERS DE ESTILO
# ════════════════════════════════════════════════════════════════════════════

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(v))) for v in rgb])


def score_color(score: float, vmin: float = 0, vmax: float = 100) -> str:
    """Gradiente continuo: acero (baja prioridad) → oliva → ámbar (alta prioridad).
    Colores más brillantes/cálidos = mayor índice SPT = mayor prioridad."""
    if pd.isna(score):
        return "#5b7a9e"
    span = vmax - vmin if vmax > vmin else 1
    t = max(0.0, min(1.0, (score - vmin) / span))

    stops = [(0.0, "#5b7a9e"), (0.5, "#8a8564"), (1.0, "#e8a33d")]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t0 <= t <= t1:
            local_t = (t - t0) / (t1 - t0) if t1 > t0 else 0
            rgb0, rgb1 = _hex_to_rgb(c0), _hex_to_rgb(c1)
            rgb = [a + (b - a) * local_t for a, b in zip(rgb0, rgb1)]
            return _rgb_to_hex(rgb)
    return "#e8a33d"


def corte_color(corte: int) -> str:
    """Color por corte acumulativo de manzana (500/700/865).
    Escala tonal de la familia ámbar: oscuro = mayor prioridad (500),
    claro = cierre de universo elegible (865)."""
    return {
        500: COLOR["corte_500"],
        700: COLOR["corte_700"],
        865: COLOR["corte_865"],
    }.get(corte, COLOR["corte_865"])


def fuente_tag_html(fuente: str) -> str:
    if pd.isna(fuente):
        return ""
    if "zona" in str(fuente).lower():
        return '<span class="tag zona">ZONA (RESPALDO)</span>'
    return '<span class="tag seccion">SECCIÓN</span>'


def fmt_pct(x, nd=1):
    if pd.isna(x):
        return "—"
    return f"{x:.{nd}f}%"


def fmt_num(x):
    if pd.isna(x):
        return "—"
    return f"{int(x):,}"


# ════════════════════════════════════════════════════════════════════════════
# ARQUETIPOS — perfiles de mensaje definidos en Fase 1 (Bloque de cierre)
# ════════════════════════════════════════════════════════════════════════════

ARQUETIPOS = {
    "Mujeres 45-59 (seguridad)": {
        "icono": "🛡️",
        "nombre": "Mujeres 45-59 · Seguridad",
        "desc": "Mejor combinación de afectación por inseguridad, reconocimiento de "
                "Arturo y conversión entre quienes lo conocen.",
        "mensaje": "Seguridad en la calle, cercanía y compromiso verificable.",
        "canal": "Radio",
    },
    "60+": {
        "icono": "🤝",
        "nombre": "60+ · Identidad Bienestar",
        "desc": "Alta conversión ligada a cumplimiento e identidad con programas "
                "sociales (Bienestar).",
        "mensaje": "Cercanía, cumplimiento de compromisos y continuidad de apoyos.",
        "canal": "Radio",
    },
    "Escolaridad básica": {
        "icono": "🎓",
        "nombre": "Escolaridad básica · Cercanía/Bienestar",
        "desc": "Segmento de mayor volumen pero menor conversión — zonas de alto LN, "
                "necesita más contacto directo.",
        "mensaje": "Cercanía personal e identidad con Bienestar, tono cotidiano.",
        "canal": "Visita casa por casa",
    },
    "Jóvenes 18-29": {
        "icono": "📱",
        "nombre": "Jóvenes 18-29 · Infraestructura urbana",
        "desc": "Segundo grupo con menor reconocimiento; mayor peso de calles en "
                "mal estado como problema principal.",
        "mensaje": "Cercanía e infraestructura urbana, tono directo.",
        "canal": "Facebook + TikTok",
    },
    "General / mixto": {
        "icono": "🧭",
        "nombre": "General / mixto",
        "desc": "Sin un perfil dominante claro — combinación equilibrada de "
                "segmentos, sin sesgo fuerte hacia uno en particular.",
        "mensaje": "Mensaje general de cercanía y resultados, sin segmentar canal.",
        "canal": "Mixto",
    },
}
DEFAULT_ARQUETIPO = ARQUETIPOS["General / mixto"]


# ════════════════════════════════════════════════════════════════════════════
# ACCESO — contraseña compartida (sin usuarios diferenciados)
# ════════════════════════════════════════════════════════════════════════════

def check_password() -> None:
    """Bloquea la página hasta que se ingrese usuario + contraseña válidos.

    Requiere en st.secrets un bloque:
        [users]
        arturo_solano = "..."
        victor_giorgiana = "..."
        yarith_tannos = "..."
        jclq = "..."
        data_ai = "..."
    (Streamlit Cloud: Settings → Secrets; local: .streamlit/secrets.toml,
    en .gitignore, nunca se sube). Las 5 cuentas tienen los mismos privilegios;
    el usuario solo sirve para identificar quién entró, no para restringir nada.

    Llamar como primera línea de cada página (Home.py y cada archivo en pages/).
    La sesión se comparte entre todas las páginas: una vez logueado, no se
    vuelve a pedir al cambiar de módulo dentro del mismo navegador/sesión.
    """
    if st.session_state.get("auth_ok"):
        return

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="max-width:420px; margin:80px auto 0; background:{COLOR['bg_raised']};
                border:1px solid {COLOR['border_subtle']}; border-radius:10px;
                padding:36px 32px; text-align:center;">
      <div style="font-family:'JetBrains Mono',monospace; font-size:.68rem; font-weight:700;
                  letter-spacing:.1em; text-transform:uppercase; color:{COLOR['amber']}; margin-bottom:10px;">
        Acceso restringido
      </div>
      <div style="font-family:'Barlow Condensed',sans-serif; font-weight:800; text-transform:uppercase;
                  font-size:1.4rem; color:{COLOR['text_primary']}; margin-bottom:4px;">
        PIE Atlixco
      </div>
      <div style="font-size:.82rem; color:{COLOR['text_secondary']}; margin-bottom:20px;">
        Uso exclusivo del equipo de campaña
      </div>
    </div>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        user = st.text_input("Usuario", label_visibility="collapsed", placeholder="Usuario")
        pwd = st.text_input("Contraseña", type="password", label_visibility="collapsed",
                             placeholder="Contraseña")
        entrar = st.button("Entrar", use_container_width=True)

    if entrar:
        usuarios = st.secrets.get("users", {})
        user_clean = (user or "").strip().lower()
        if user_clean in usuarios and pwd == usuarios[user_clean]:
            st.session_state["auth_ok"] = True
            st.session_state["auth_user"] = user_clean
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

    st.stop()


def sidebar_sesion() -> None:
    """Muestra el usuario logueado y un botón de cerrar sesión en la sidebar.
    Llamar después de check_password() en cada página."""
    st.sidebar.markdown(
        f"<div style='font-family:\"JetBrains Mono\",monospace; font-size:.7rem; "
        f"color:{COLOR['text_muted']};'>Sesión: <b style='color:{COLOR['text_secondary']};'>"
        f"{st.session_state.get('auth_user', '—')}</b></div>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Cerrar sesión", use_container_width=True):
        st.session_state["auth_ok"] = False
        st.session_state["auth_user"] = None
        st.rerun()
    st.sidebar.markdown(
        f"<hr style='border-color:{COLOR['border_subtle']}; margin:8px 0 16px;'>",
        unsafe_allow_html=True,
    )