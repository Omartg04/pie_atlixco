"""
extraer_bubble_completo.py
PIE Atlixco — Extrae TODOS los registros de Bubble con todos sus campos.

USO:
    python extraer_bubble_completo.py

REQUISITOS:
    pip install requests pandas
"""

import requests
import pandas as pd
import time

# ── CREDENCIALES ─────────────────────────────────────────────────────────────
TOKEN    = "4079ccda281d8c251f26ec482bf7356d"
BASE_URL = "https://encuestainduccionatlixco.bubbleapps.io/api/1.1/obj/Encuesta"
HEADERS  = {"Authorization": f"Bearer {TOKEN}"}
LIMIT    = 100   # máximo permitido por Bubble por llamada

# ── PAGINACIÓN ────────────────────────────────────────────────────────────────
def fetch_all():
    todos = []
    cursor = 0
    total = None

    while True:
        params = {
            "limit": LIMIT,
            "cursor": cursor,
            "sort_field": "Created Date",
            "descending": "false",
        }

        try:
            r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=60)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"\n  Error en cursor {cursor}: {e}")
            print("  Reintentando en 3 segundos...")
            time.sleep(3)
            continue

        body = r.json().get("response", {})

        if total is None:
            total = body.get("count", 0)
            print(f"Total de registros en Bubble: {total}\n")

        resultados = body.get("results", [])
        if not resultados:
            break

        todos.extend(resultados)
        cursor += len(resultados)

        pct = cursor / total * 100 if total else 0
        print(f"  Descargados: {cursor:>5} / {total}  ({pct:.1f}%)", end="\r")

        # Si recibimos menos registros que el límite, ya terminamos
        if len(resultados) < LIMIT:
            break

        time.sleep(0.2)   # pausa corta para no saturar la API

    print(f"\nDescarga completa: {len(todos)} registros.")
    return todos

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    registros = fetch_all()

    if not registros:
        print("No se obtuvieron registros. Verifica las credenciales.")
        return

    df = pd.DataFrame(registros)

    print(f"\nCampos encontrados ({len(df.columns)}):")
    for col in df.columns:
        no_nulos = df[col].notna().sum()
        print(f"  {col:<45} {no_nulos:>5} registros con dato")

    salida = "bubble_completo.csv"
    df.to_csv(salida, index=False, encoding="utf-8-sig")
    print(f"\n✅ Guardado: {salida}  ({df.shape[0]} filas × {df.shape[1]} columnas)")
    print("   Sube ese archivo a la conversación con Claude.")

if __name__ == "__main__":
    main()