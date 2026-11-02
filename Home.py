"""
PIE Atlixco — Home
Plataforma de Inteligencia Electoral · Arturo Solano Escobedo · Proceso interno Morena
"""

import streamlit as st

from app_utils import GLOBAL_CSS, COLOR, check_password, sidebar_sesion

st.set_page_config(
    page_title="PIE Atlixco · Arturo Solano",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

check_password()
sidebar_sesion()

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Hero ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']};
            border-radius:10px; padding:48px 40px; margin-bottom:28px;">
  <div style="font-family:'JetBrains Mono',monospace; font-size:.72rem; font-weight:700;
              letter-spacing:.12em; text-transform:uppercase; color:{COLOR['amber']}; margin-bottom:16px;">
    Plataforma de Inteligencia Electoral · Atlixco, Puebla
  </div>
  <h1 style="font-family:'Barlow Condensed',sans-serif; font-weight:800; text-transform:uppercase;
             font-size:2.8rem; line-height:1; margin:0 0 8px; color:{COLOR['text_primary']};">
    PIE Atlixco<br><span style="color:{COLOR['amber']};">Arturo Solano Escobedo</span>
  </h1>
  <p style="font-size:1.02rem; color:{COLOR['text_secondary']}; max-width:600px; margin:16px 0 0; line-height:1.6;">
    Proceso interno de Morena — candidatura a la presidencia municipal. Segmentación
    territorial basada en encuesta propia, censo ITER y lista nominal, para saber
    dónde invertir tiempo de campaña primero.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Ticker de estado ─────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
for col, val, label, ctx in [
    (c1, "42", "Secciones priorizadas", "ordenadas por índice territorial (SPT)"),
    (c2, "37", "Secciones urbanas", "con manzanas prioritarias identificadas"),
    (c3, "5", "Secciones rurales", "para barrido"),
    (c4, "80%", "Lista Nominal", "meta de cobertura operativa"),
]:
    with col:
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-val">{val}</div>
          <div class="kpi-label">{label}</div>
          <div class="kpi-ctx">{ctx}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Estaciones / módulos ─────────────────────────────────────────────────
st.markdown(f"""
<div style="font-family:'JetBrains Mono',monospace; font-size:.7rem; font-weight:700;
            letter-spacing:.12em; text-transform:uppercase; color:{COLOR['steel']}; margin-bottom:10px;">
  Módulos
</div>
""", unsafe_allow_html=True)

col_a, col_b = st.columns(2)
with col_a:
    st.markdown(f"""
    <div class="stations-grid" style="grid-template-columns: 1fr;">
      <article class="station">
        <span class="station-status on"><i></i>EN OPERACIÓN</span>
        <div class="station-tag">01 · Planeación Territorial</div>
        <h3>¿A dónde manda el equipo las brigadas?</h3>
        <p>Ordena las 74 secciones del municipio de mayor a menor prioridad y arma el
        recorrido del día, con el mensaje listo para mandarle al brigadista por WhatsApp
        y el enlace del mapa de su sección.</p>
      </article>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.page_link("pages/1_M1_Planeacion_Territorial.py", label="→ Ir al Módulo 1 · Planeación Territorial", icon="🗺️")

with col_b:
    st.markdown(f"""
    <div class="stations-grid" style="grid-template-columns: 1fr;">
      <article class="station">
        <span class="station-status on"><i></i>EN OPERACIÓN</span>
        <div class="station-tag">02 · Manzanas Prioritarias</div>
        <h3>¿Qué manzana toca primero dentro de cada sección?</h3>
        <p>Dentro de cada sección urbana, muestra qué manzanas tocar primero para cubrir
        la mayor cantidad de lista nominal con el menor esfuerzo de brigadeo.</p>
      </article>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.page_link("pages/2_M2_Manzanas.py", label="→ Ir al Módulo 2 · Manzanas Prioritarias", icon="🧱")

st.markdown("<br>", unsafe_allow_html=True)

st.markdown(f"""
<div class="stations-grid" style="grid-template-columns: 1fr;">
  <article class="station">
    <span class="station-status on"><i></i>EN OPERACIÓN</span>
    <div class="station-tag">03 · ¿Cómo vamos en campo?</div>
    <h3>Seguimiento del operativo de inducción</h3>
    <p>Pulso en vivo del operativo de campo: entrevistas acumuladas contra la meta,
    ritmo diario, productividad por brigadista y dónde está trabajando el equipo hoy.
    Los datos vienen de Kobo y solo incluyen los registros ya sincronizados. Arrancó
    el 28 de octubre.</p>
  </article>
</div>
""", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)
st.page_link("pages/3_M3_Como_vamos_en_campo.py", label="→ Ir al Módulo 3 · ¿Cómo vamos en campo?", icon="📡")

st.markdown("<br>", unsafe_allow_html=True)

st.markdown(f"""
<div class="stations-grid" style="grid-template-columns: 1fr;">
  <article class="station">
    <span class="station-status on"><i></i>EN OPERACIÓN</span>
    <div class="station-tag">04 · ¿Cómo vamos en campo, por colonia?</div>
    <h3>El mismo avance, en el nombre que reconocen las brigadas</h3>
    <p>Vista complementaria al Módulo 3: mismo operativo de inducción, orientado por
    colonia en vez de número de sección. El universo elegible (LN corte 500) es exacto;
    las encuestas por colonia son una estimación por reparto proporcional, ya que Bubble
    solo captura la sección de cada encuesta.</p>
  </article>
</div>
""", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)
st.page_link("pages/4_M4_Colonias.py", label="→ Ir al Módulo 4 · ¿Cómo vamos en campo, por colonia?", icon="🏘️")

st.markdown(f"""
<div style="margin-top:36px; padding-top:16px; border-top:1px solid {COLOR['border_subtle']};
            font-family:'JetBrains Mono',monospace; font-size:.68rem; color:{COLOR['text_muted']};
            letter-spacing:.04em;">
  PIE ATLIXCO · ARTURO SOLANO ESCOBEDO · PROCESO INTERNO MORENA 2026 · CONFIDENCIAL<br>
  USO EXCLUSIVO DEL EQUIPO DE CAMPAÑA
</div>
""", unsafe_allow_html=True)