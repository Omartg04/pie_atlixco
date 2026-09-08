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
BASE_URL = "https://encuestainduccionatlixco.bubbleapps.io/api/1.1/obj/encuesta"  # ← minúsculas
HEADERS  = {"Authorization": f"Bearer {TOKEN}"}
LIMIT    = 100

# ── DIAGNÓSTICO INICIAL ───────────────────────────────────────────────────────
def diagnostico():
    """Hace UNA sola llamada y muestra todo — para identificar el error exacto."""
    print("=" * 60)
    print("DIAGNÓSTICO — primera llamada a Bubble")
    print(f"URL: {BASE_URL}")
    print("=" * 60)

    r = requests.get(BASE_URL, headers=HEADERS, params={"limit": 1, "cursor": 0}, timeout=20)

    print(f"\nHTTP Status: {r.status_code} {r.reason}")
    print(f"\nResponse body (primeros 1000 chars):")
    print(r.text[:1000])
    print()

    if r.status_code == 400:
        print("⚠️  400 Bad Request — opciones:")
        print("   1. El nombre del tipo en Bubble no es 'encuesta'.")
        print("      → En Bubble editor: Data tab, verifica el nombre exacto del tipo.")
        print("   2. La Data API no está habilitada para este tipo.")
        print("      → En Bubble editor: Settings → API → 'Enable Data API'")
        print("        y verifica que 'encuesta' aparezca en la lista de tipos expuestos.")
        print("   3. Las Privacy Rules bloquean el acceso API.")
        print("      → En Bubble editor: Data → Privacy → tipo encuesta → 'View all fields'")
        print()
        return False

    if r.status_code == 401:
        print("⚠️  401 Unauthorized — el token no es válido o venció.")
        return False

    if r.status_code == 404:
        print("⚠️  404 Not Found — el nombre del tipo o la URL base son incorrectos.")
        print("   Prueba con el nombre exacto que ves en el editor de Bubble.")
        return False

    if r.status_code == 200:
        body = r.json().get("response", {})
        count = body.get("count", "N/A")
        results = body.get("results", [])
        print(f"✅  200 OK — {count} registros totales en Bubble")
        if results:
            print(f"\nCampos del primer registro:")
            for k, v in results[0].items():
                print(f"  {k:<45} {str(v)[:60]}")
        else:
            print("   (0 registros — la base está vacía o todos filtrados)")
        return True

    print(f"Status inesperado: {r.status_code}")
    return False


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
            if hasattr(e, 'response') and e.response is not None:
                print(f"  Response body: {e.response.text[:500]}")
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

        if len(resultados) < LIMIT:
            break

        time.sleep(0.2)

    print(f"\nDescarga completa: {len(todos)} registros.")
    return todos


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    # Primero diagnóstico — si falla, para aquí con info útil
    ok = diagnostico()
    if not ok:
        print("\nCorrege el problema indicado arriba antes de continuar.")
        return

    print("\n" + "=" * 60)
    print("Descargando todos los registros...")
    print("=" * 60 + "\n")

    registros = fetch_all()

    if not registros:
        print("No se obtuvieron registros.")
        return

    df = pd.DataFrame(registros)

    print(f"\nCampos encontrados ({len(df.columns)}):")
    for col in df.columns:
        no_nulos = df[col].notna().sum()
        print(f"  {col:<45} {no_nulos:>5} registros con dato")

    salida = "bubble_completo.csv"
    df.to_csv(salida, index=False, encoding="utf-8-sig")
    print(f"\n✅ Guardado: {salida}  ({df.shape[0]} filas × {df.shape[1]} columnas)")

if __name__ == "__main__":
    main()