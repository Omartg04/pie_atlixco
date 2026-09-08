"""
diagnostico_stakeholder_m3.py

Diagnóstico para el reporte stakeholder M3 (Tabla 1: ranking SPT por sección,
Tabla 2: escenarios de ritmo). Corre esto en el entorno con acceso a
st.secrets["bubble"] y a bubble_connector.py (mismo repo del proyecto).

Uso:
    Este script SÍ necesita correr dentro de un contexto Streamlit porque
    get_encuestas_induccion() usa @st.cache_data y st.session_state
    internamente (definidos en bubble_connector.py). Colócalo en la raíz
    del repo (junto a bubble_connector.py) y corre:

        streamlit run diagnostico_stakeholder_m3.py

    Verás el diagnóstico impreso como una página de Streamlit. El JSON se
    guarda igual en disco, en diagnostico_outputs/.

Output: imprime en pantalla (vía st.write/st.dataframe) + guarda un JSON en
    diagnostico_outputs/stakeholder_m3_YYYYMMDD_HHMM.json
Comparte ese JSON completo de vuelta (o el archivo).
"""

import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from bubble_connector import (
    get_encuestas_induccion,
    ahora_mexico,
    HABITANTES_PROMEDIO_VIVIENDA,
    ANCLA_OPERATIVO,
)

# ------------------------------------------------------------------
# 1. CONFIG
# ------------------------------------------------------------------
CORTE_OPERATIVO = ANCLA_OPERATIVO  # 2026-07-18 09:00 — misma ancla que M3
NOMBRES_EXCLUIR = {"OMAR TELLEZ", "OMAR TÉLLEZ"}  # ya vienen en mayúsculas de _transform()

RUTA_GEOJSON = "/Users/omartellez/pie_atlixco/data/atlixco_unificado_web_capas.geojson"
RUTA_SPT = "/Users/omartellez/pie_atlixco/data/SPT_indice_secciones_enriquecido.csv"

OUT_DIR = "diagnostico_outputs"
os.makedirs(OUT_DIR, exist_ok=True)


def cargar_encuestas():
    """
    Trae el DataFrame ya transformado y filtrado por get_encuestas_induccion()
    (mismo pipeline que usa M3: fecha_creacion en hora México, nombre_encuestador
    ya normalizado upper/strip) y aplica el filtro operativo estándar:
    fecha_creacion >= ANCLA_OPERATIVO, excluyendo registros de prueba.
    """
    private_key = st.secrets["bubble"]["private_key"]
    df, ultima_act, info = get_encuestas_induccion(private_key)

    if info.get("degradado"):
        st.warning(f"[AVISO] Carga degradada: {info.get('mensaje')}")

    # Filtro: excluir pruebas (nombre_encuestador ya viene normalizado en upper)
    df = df[~df["nombre_encuestador"].isin(NOMBRES_EXCLUIR)].copy()

    # Filtro: corte operativo
    df = df[df["fecha_creacion"] >= CORTE_OPERATIVO].copy()

    df["fecha_solo"] = df["fecha_creacion"].dt.date

    return df


def main():
    st.title("Diagnóstico stakeholder M3")
    st.write(f"Corte operativo: {CORTE_OPERATIVO}")
    st.write(f"Ejecutado: {ahora_mexico()}")

    df = cargar_encuestas()
    total_encuestas = len(df)
    st.subheader(f"Total encuestas válidas (post-filtro): {total_encuestas}")

    # ----------------------------------------------------------
    # A. ENCUESTADORES ACTIVOS PROMEDIO POR DÍA
    # ----------------------------------------------------------
    encuestadores_por_dia = df.groupby("fecha_solo")["nombre_encuestador"].nunique()
    dias_con_actividad = len(encuestadores_por_dia)
    promedio_encuestadores_dia = encuestadores_por_dia.mean()

    st.markdown("### A. Encuestadores activos")
    st.write(f"Días con actividad: {dias_con_actividad}")
    st.write(f"Promedio encuestadores activos/día: {promedio_encuestadores_dia:.2f}")
    st.write("Detalle por día:")
    st.dataframe(encuestadores_por_dia)

    # ----------------------------------------------------------
    # B. RITMO: ENCUESTAS POR ENCUESTADOR-DÍA
    # ----------------------------------------------------------
    encuestas_por_dia = df.groupby("fecha_solo").size()
    # encuestador-días totales = suma de encuestadores únicos por día
    encuestador_dias_totales = encuestadores_por_dia.sum()
    ritmo_real_encuesta_por_encuestador_dia = total_encuestas / encuestador_dias_totales

    st.markdown("### B. Ritmo observado")
    st.write(f"Encuestador-días totales (suma de encuestadores únicos/día): {encuestador_dias_totales}")
    st.write(f"Ritmo real: {ritmo_real_encuesta_por_encuestador_dia:.2f} encuestas / encuestador / día")
    st.write("Encuestas por día (bruto, sin dividir por encuestador):")
    st.dataframe(encuestas_por_dia)

    # ----------------------------------------------------------
    # C. ENCUESTAS POR SECCIÓN (para Tabla 1)
    # ----------------------------------------------------------
    # seccion_electoral ya viene como int (ver _transform en bubble_connector.py)
    col_seccion = "seccion_electoral"
    encuestas_por_seccion = df.groupby(col_seccion).size().sort_values(ascending=False)

    st.markdown(f"### C. Encuestas por sección (col usada: {col_seccion})")
    st.dataframe(encuestas_por_seccion)

    secciones_con_avance = int((encuestas_por_seccion >= 1).sum())
    st.write(f"Secciones con al menos 1 encuesta: {secciones_con_avance}")

    # ----------------------------------------------------------
    # D. LN PROYECTADA CUBIERTA POR SECCIÓN
    # ----------------------------------------------------------
    ln_cubierta_por_seccion = None
    ln_total_por_seccion = None
    try:
        import json as _json
        with open(RUTA_GEOJSON, "r", encoding="utf-8") as f:
            geo = _json.load(f)

        filas_geo = []
        for feat in geo["features"]:
            props = feat.get("properties", {})
            if props.get("seleccionada_500") is True:
                filas_geo.append({
                    "seccion_electoral": props.get("seccion"),
                    "LN_estimada_manzana": props.get("LN_estimada_manzana", 0) or 0,
                })

        st.write(f"[DEBUG] filas_geo encontradas: {len(filas_geo)}")

        df_geo = pd.DataFrame(filas_geo)
        st.write(f"[DEBUG] df_geo shape: {df_geo.shape}")
        st.write("[DEBUG] df_geo head:", df_geo.head())

        df_geo["seccion_electoral"] = pd.to_numeric(df_geo["seccion_electoral"], errors="coerce")

        ln_total_por_seccion = (
            df_geo.groupby("seccion_electoral")["LN_estimada_manzana"]
            .sum()
            .rename("LN_corte_500")
        )
        st.write(f"[DEBUG] ln_total_por_seccion shape: {ln_total_por_seccion.shape}")
        st.markdown("### D. LN corte 500 por sección (de GeoJSON)")
        st.dataframe(ln_total_por_seccion)

        ln_cubierta_por_seccion = (
            encuestas_por_seccion * HABITANTES_PROMEDIO_VIVIENDA
        ).rename("LN_proyectada_cubierta")

    except Exception as e:
        st.warning(f"[AVISO] No se pudo leer el GeoJSON automáticamente: {e}")
        st.write(f"Ruta usada: {RUTA_GEOJSON} — ajusta RUTA_GEOJSON si no es correcta.")

    # ----------------------------------------------------------
    # E. RESUMEN PARA EL REPORTE (fechas de proyección)
    # ----------------------------------------------------------
    dias_habiles_proyeccion = pd.bdate_range("2026-08-04", "2026-08-31")
    n_dias_habiles = len(dias_habiles_proyeccion)

    st.markdown("### E. Horizonte de proyección")
    st.write(f"Días hábiles del 4 al 31 de agosto 2026 (L-V): {n_dias_habiles}")

    # ----------------------------------------------------------
    # OUTPUT JSON
    # ----------------------------------------------------------
    resumen = {
        "ejecutado": str(ahora_mexico()),
        "total_encuestas_validas": total_encuestas,
        "dias_con_actividad": dias_con_actividad,
        "promedio_encuestadores_activos_dia": round(float(promedio_encuestadores_dia), 3),
        "encuestador_dias_totales": int(encuestador_dias_totales),
        "ritmo_real_encuestas_por_encuestador_dia": round(float(ritmo_real_encuesta_por_encuestador_dia), 3),
        "secciones_con_al_menos_1_encuesta": secciones_con_avance,
        "dias_habiles_proyeccion_4_al_31_agosto": n_dias_habiles,
        "encuestas_por_seccion": encuestas_por_seccion.to_dict(),
        "encuestadores_por_dia": {str(k): int(v) for k, v in encuestadores_por_dia.items()},
        "encuestas_por_dia": {str(k): int(v) for k, v in encuestas_por_dia.items()},
    }

    if ln_total_por_seccion is not None:
        resumen["ln_corte_500_por_seccion"] = {
            str(k): float(v) for k, v in ln_total_por_seccion.to_dict().items()
        }

    out_path = os.path.join(
        OUT_DIR, f"stakeholder_m3_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2, default=str)

    st.success(f"✅ JSON guardado en: {out_path}")
    st.write("Comparte este archivo completo de vuelta en el chat (o pega su contenido).")

    with open(out_path, "r", encoding="utf-8") as f:
        st.download_button(
            "Descargar JSON de diagnóstico",
            data=f.read(),
            file_name=os.path.basename(out_path),
            mime="application/json",
        )


if __name__ == "__main__":
    main()