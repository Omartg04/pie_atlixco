"""
Utilidades compartidas — Inteligencia Electoral Zacatlán | JCLY Morena 2026
"""
import streamlit as st


def _carto_api_key() -> str:
    """Lee la API key de Carto desde secrets, soportando dos formatos:

        [carto]
        api_key = "..."

    o bien (formato plano):

        CARTO_API_KEY = "..."
    """
    key = st.secrets.get("carto", {}).get("api_key", "")
    if not key:
        key = st.secrets.get("CARTO_API_KEY", "")
    return key


CARTO_API_KEY = _carto_api_key()

# URL de tiles CartoDB Positron con API key (el shorthand "CartoDB positron"
# de folium usa la URL pública sin key → watermark "API KEY REQUIRED").
CARTO_TILES = (
    f"https://basemaps.cartocdn.com/rastertiles/light_all/{{z}}/{{x}}/{{y}}.png"
    f"?key={CARTO_API_KEY}"
)
CARTO_ATTR = (
    "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> "
    "contributors © <a href='https://carto.com/attributions'>CARTO</a>"
)
