"""
verificar_conteo_hoy.py — PIE Atlixco

Verifica, con datos crudos de Bubble, cuántas encuestas hay por día calendario
y por encuestador — para confirmar si el número que muestra el reporte/app
es correcto, antes de asumir que hay un error de conexión.

Uso:
    python verificar_conteo_hoy.py
"""
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from bubble_connector import _fetch_all_raw, _transform, ANCLA_OPERATIVO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOMBRES_EXCLUIDOS = {"omar téllez", "omar tellez"}


def main():
    ruta_secrets = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    with open(ruta_secrets, "rb") as f:
        secrets = tomllib.load(f)
    private_key = secrets["bubble"]["private_key"]

    print("→ Descargando TODOS los registros crudos de Bubble (sin filtrar)...")
    raw = _fetch_all_raw(private_key)
    print(f"   Total crudo en Bubble: {len(raw)}\n")

    df = _transform(raw)
    print(f"→ Después de transformar (fechas parseadas, sección numérica): {len(df)} registros")
    print(f"   (los que se pierden aquí no tienen fecha_creacion o seccion_electoral válida)\n")

    print("── Conteo por día calendario (hora local México, TODOS los registros) ──")
    conteo_dia_todos = df["fecha_creacion"].dt.date.value_counts().sort_index()
    for dia, n in conteo_dia_todos.items():
        print(f"   {dia} ({dia.strftime('%A')}): {n}")

    df_filtrado = df[
        (df["fecha_creacion"] >= ANCLA_OPERATIVO)
        & (~df["nombre_encuestador"].str.strip().str.lower().isin(NOMBRES_EXCLUIDOS))
    ].copy()

    print(f"\n→ Tras aplicar corte de operativo (>= 18 jul 9:00 AM) y exclusión de pruebas: "
          f"{len(df_filtrado)} registros\n")

    print("── Conteo por día calendario (SOLO dentro del operativo real) ──")
    conteo_dia_filtrado = df_filtrado["fecha_creacion"].dt.date.value_counts().sort_index()
    for dia, n in conteo_dia_filtrado.items():
        print(f"   {dia} ({dia.strftime('%A')}): {n}")

    hoy = datetime.now().date()
    df_hoy = df_filtrado[df_filtrado["fecha_creacion"].dt.date == hoy]
    print(f"\n── Detalle de HOY ({hoy}) — {len(df_hoy)} encuestas ──")
    if len(df_hoy):
        por_encuestador = df_hoy["nombre_encuestador"].value_counts()
        for nombre, n in por_encuestador.items():
            print(f"   {nombre}: {n}")
        encuestadores_sin_actividad_hoy = (
            set(df_filtrado["nombre_encuestador"].unique()) - set(df_hoy["nombre_encuestador"].unique())
        )
        if encuestadores_sin_actividad_hoy:
            print(f"\n   ⚠️  Sin ninguna encuesta hoy: {', '.join(sorted(encuestadores_sin_actividad_hoy))}")
    else:
        print("   Sin encuestas hoy.")

    print(f"\n── Totales acumulados por encuestador (todo el operativo) ──")
    for nombre, n in df_filtrado["nombre_encuestador"].value_counts().items():
        print(f"   {nombre}: {n}")


if __name__ == "__main__":
    main()
