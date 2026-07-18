"""
PIE Atlixco · bubble_connector.py
Conector a la Data API de Bubble para el formulario de inducción ("Encuesta").

Confirmado en campo (18 jul 2026):
  - Thing: "Encuesta"
  - Nombres de campo = códigos crudos de Bubble, NO los nombres amigables del
    diccionario. Mayúsculas/minúsculas tal cual las regresa la API:
    atl_1/atl_1_texto, atl_2/atl_2_texto (confirmados en muestra real);
    Atl_3/Atl_4/Atl_5 y P10_1/P15_1/P16_1/P2_1/P2_2 se mapean por analogía
    con el mismo patrón (P mayúscula + número, atl minúscula + número) —
    ajustar aquí si algún campo no llega con el nombre esperado.
  - seccion_electoral llega como STRING con cero a la izquierda ("0164").
  - Created By es el ID interno del usuario de Bubble, NO un correo — no se
    usa. La llave de agrupación por encuestador es `nombre_encuestador`
    (texto libre, confirmado confiable por el usuario).
  - P12_1 aparece en registros reales pero no está documentado en el
    diccionario — se ignora explícitamente (fuera de alcance de M3).

Uso:
    from bubble_connector import get_encuestas_induccion
    df, ultima_act, info = get_encuestas_induccion(private_key=st.secrets["bubble"]["private_key"])
"""
import time
import logging
from datetime import datetime, timezone, date

import requests
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

BUBBLE_DATA_API_ROOT = "https://encuestainduccionatlixco.bubbleapps.io/api/1.1/obj"
BUBBLE_THING_NAME = "Encuesta"
BUBBLE_ENDPOINT = f"{BUBBLE_DATA_API_ROOT}/{BUBBLE_THING_NAME}"
BUBBLE_PAGE_SIZE = 100
CACHE_TTL_SEC = 600  # 10 min — dentro del rango 5-10 min acordado

ANCLA_OPERATIVO = datetime(2026, 7, 18, 9, 0, 0)

# ── Mapeo campos Bubble (crudo) → app ───────────────────────────────────────
# Confirmados en muestra real: atl_1, atl_2, P8_1, P14_1, P22_1/2/3.
# Por analogía (mismo patrón de mayúsculas/minúsculas), sin confirmar aún:
# atl_3, atl_4, atl_5, P10_1, P15_1, P16_1, P2_1, P2_2 — si Bubble regresa
# alguno con otra capitalización, ajustar solo esta tabla.
FIELD_MAP = {
    "_id":               "id_unico",
    "Created Date":      "fecha_creacion",
    "Modified Date":     "fecha_modificacion",
    "nombre_encuestador": "nombre_encuestador",
    "seccion_electoral": "seccion_electoral",
    "municipio_texto":   "municipio_texto",
    "localidad":         "localidad",
    "P22_1_texto":       "aprobacion_atlixco",
    "P22_2_texto":       "aprobacion_gobernador",
    "P22_3_texto":       "aprobacion_presidenta",
    "P8_1_texto":        "conocimiento_arturo",
    "atl_1_texto":       "amor_puebla",
    "atl_3_texto":       "percepcion_inseguridad",
    "atl_4_texto":       "comite_vigilancia",
    "atl_5_texto":       "alarma_vecinal",
    "atl_2_texto":       "seguridad",
    "P14_1_texto":       "cumplimiento_arturo",
    "P10_1_texto":       "honestidad_arturo",
    "P15_1_texto":       "buena_candidatura_arturo",
    "P16_1_texto":       "votar_o_no_arturo",
    "P2_1_texto":        "principal_problema_estado_opciones",
    "P2_1_otro":         "principal_problema_estado_otro",
    "P2_2_text":         "tipo_inseguridad_opciones",
    "P2_2_otro":         "tipo_inseguridad_otro",
}

# Campos de PII — nunca se incorporan al DataFrame final, solo se usan para
# derivar un booleano de "se capturó o no".
CAMPOS_PII = ["nombre_encuestado", "celular_encuestado", "email_encuestado"]

_ISO_FMT = "%Y-%m-%dT%H:%M:%S.000Z"


def semana_operativo(fecha) -> str:
    if isinstance(fecha, pd.Timestamp):
        fecha = fecha.to_pydatetime()
    delta = fecha - ANCLA_OPERATIVO
    semana_num = (delta.days // 7) + 1
    return f"S{max(semana_num, 1)}"


# ── Paginación ───────────────────────────────────────────────────────────────

def _fetch_all_raw(private_key: str) -> list[dict]:
    """
    Descarga completa en serie. A esta escala (decenas/cientos de registros,
    no 50K+) no hace falta paginación por ventanas de tiempo ni descarga
    paralela — una sola pasada de páginas de 100 es más que suficiente y
    más simple de mantener.
    """
    headers = {"Authorization": f"Bearer {private_key}"}
    resultados: list[dict] = []
    cursor = 0

    while True:
        resp = requests.get(
            BUBBLE_ENDPOINT, headers=headers,
            params={"limit": BUBBLE_PAGE_SIZE, "cursor": cursor}, timeout=20,
        )
        resp.raise_for_status()
        body = resp.json().get("response", {})
        batch = body.get("results", [])
        resultados.extend(batch)
        remaining = body.get("remaining", 0)
        if remaining <= 0 or not batch:
            break
        cursor += BUBBLE_PAGE_SIZE

    return resultados


def _transform(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=list(FIELD_MAP.values()) + [
            "duracion_min", "tiene_celular", "tiene_email", "semana_operativo",
        ])

    filas = []
    for r in records:
        fila = {app_key: r.get(bubble_key) for bubble_key, app_key in FIELD_MAP.items()}
        fila["tiene_celular"] = bool(r.get("celular_encuestado"))
        fila["tiene_email"] = bool(r.get("email_encuestado"))
        filas.append(fila)

    df = pd.DataFrame(filas)

    for col in ("fecha_creacion", "fecha_modificacion"):
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce").dt.tz_localize(None)

    df["duracion_min"] = (
        (df["fecha_modificacion"] - df["fecha_creacion"]).dt.total_seconds().div(60).round(1)
    )

    # seccion_electoral llega como string con cero a la izquierda ("0164")
    df["seccion_electoral"] = pd.to_numeric(df["seccion_electoral"], errors="coerce")

    df = df[df["fecha_creacion"].notna() & df["seccion_electoral"].notna()].copy()
    df["seccion_electoral"] = df["seccion_electoral"].astype(int)
    df["semana_operativo"] = df["fecha_creacion"].apply(semana_operativo)

    return df


# ── Cache global + salvaguarda anti-degradación ─────────────────────────────

@st.cache_data(ttl=CACHE_TTL_SEC, show_spinner=False)
def _load_full(private_key: str) -> tuple[pd.DataFrame, float]:
    raw = _fetch_all_raw(private_key)
    df = _transform(raw)
    return df, time.time()


_SANITY_MARGIN = 0.90  # margen de tolerancia — Bubble nunca borra registros


def get_encuestas_induccion(
    private_key: str, force_refresh: bool = False,
) -> tuple[pd.DataFrame, datetime | None, dict]:
    """
    Retorna (df, ultima_actualizacion, info). info = {"degradado": bool, "mensaje": str|None}.

    Salvaguarda anti-degradación: si el conteo nuevo es menor al último "bueno"
    conocido en session_state (con margen de tolerancia), se descarta la
    respuesta y se conserva el último dato confiable — Bubble nunca borra
    registros, así que el total nunca debe decrecer legítimamente.
    """
    if force_refresh:
        _load_full.clear()

    try:
        df, ts = _load_full(private_key)
    except Exception as e:
        logger.warning("Error cargando desde Bubble: %s", e)
        last_df = st.session_state.get("_m3_last_good_df")
        last_ts = st.session_state.get("_m3_last_good_ts")
        if last_df is not None:
            return last_df, _ts_to_dt(last_ts), {
                "degradado": True,
                "mensaje": "No se pudo conectar con Bubble. Mostrando el último dato confiable.",
            }
        return pd.DataFrame(), None, {
            "degradado": True,
            "mensaje": "No se pudo conectar con Bubble y no hay datos previos en esta sesión.",
        }

    info = {"degradado": False, "mensaje": None}
    last_good_count = st.session_state.get("_m3_last_good_count", 0)
    nuevo_count = len(df)

    if last_good_count > 0 and nuevo_count < last_good_count * _SANITY_MARGIN:
        logger.warning(
            "Carga degradada: %d registros nuevos vs %d últimos buenos.",
            nuevo_count, last_good_count,
        )
        _load_full.clear()
        last_df = st.session_state.get("_m3_last_good_df")
        last_ts = st.session_state.get("_m3_last_good_ts")
        info = {
            "degradado": True,
            "mensaje": (
                f"Bubble devolvió una respuesta incompleta ({nuevo_count} de "
                f"{last_good_count} registros esperados). Mostrando el último dato confiable."
            ),
        }
        if last_df is not None:
            return last_df, _ts_to_dt(last_ts), info
    else:
        st.session_state["_m3_last_good_df"] = df
        st.session_state["_m3_last_good_count"] = nuevo_count
        st.session_state["_m3_last_good_ts"] = ts

    return df, _ts_to_dt(ts), info


def _ts_to_dt(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)
