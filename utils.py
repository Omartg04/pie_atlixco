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
}

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
    """Geojson de manzanas/localidades con capas de priorización 500/700/865."""
    path = os.path.join(DATA_DIR, "atlixco_unificado_web_capas.geojson")
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