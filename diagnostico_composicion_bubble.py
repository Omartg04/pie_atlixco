"""
diagnostico_composicion_bubble.py — PIE Atlixco

Diagnóstico de solo lectura: no modifica nada, no depende de Streamlit.
Corre junto a bubble_connector.py (misma carpeta) con:

    python diagnostico_composicion_bubble.py

Qué hace:
  1. Lee la private_key de .streamlit/secrets.toml (igual que generar_reporte_m3.py).
  2. Descarga TODOS los registros crudos de Bubble (sin transformar).
  3. Imprime:
     - Total de registros crudos.
     - El conjunto completo de llaves (campos) que aparecen en al menos un
       registro — para detectar cualquier campo de estatus/completitud que
       hoy NO esté en FIELD_MAP (ej. algo tipo "terminada", "status",
       "Step", "completed", etc.).
     - Para cada llave candidata a estatus, un conteo de valores únicos.
     - Cuántos registros faltan por completo el campo `Modified Date`
       (posible proxy de "nunca se guardó/avanzó" si el form actualiza esa
       fecha en cada página).
     - Distribución de `duracion_min` (fecha_modificacion - fecha_creacion)
       tras aplicar la misma transformación que usa la app — duraciones muy
       cortas (ej. <1 min) son sospechosas de abandono o prueba.
     - Cuántos registros caen antes del ancla real del operativo (18 jul,
       9:00 AM) y cuántos son de los nombres de prueba excluidos, para
       verificar que ese filtro sigue vigente y no está ocultando algo más.
"""
import os
import sys
import json
from collections import Counter

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bubble_connector import _fetch_all_raw, _transform, ANCLA_OPERATIVO, FIELD_MAP

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOMBRES_EXCLUIDOS = {"omar téllez", "omar tellez"}

# Palabras clave que sugieren un campo de estatus/completitud, para
# resaltarlas dentro del listado completo de llaves crudas.
PALABRAS_ESTATUS = [
    "status", "estatus", "terminad", "complet", "finaliz", "step", "paso",
    "progress", "avance", "submit", "enviad", "draft", "borrador",
]


def leer_private_key() -> str:
    ruta_secrets = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    if not os.path.exists(ruta_secrets):
        sys.exit(f"❌ No se encontró {ruta_secrets}.")
    with open(ruta_secrets, "rb") as f:
        secrets = tomllib.load(f)
    key = secrets.get("bubble", {}).get("private_key")
    if not key:
        sys.exit("❌ No se encontró [bubble] private_key en secrets.toml.")
    return key


def main():
    print("→ Consultando Data API de Bubble (registros crudos, sin transformar)...")
    private_key = leer_private_key()
    raw = _fetch_all_raw(private_key)
    print(f"\n=== TOTAL DE REGISTROS CRUDOS EN BUBBLE: {len(raw)} ===\n")

    if not raw:
        sys.exit("No hay registros. Nada que diagnosticar todavía.")

    # ── 1. Todas las llaves que aparecen en al menos un registro ───────────
    todas_llaves = set()
    for r in raw:
        todas_llaves.update(r.keys())

    llaves_mapeadas = set(FIELD_MAP.keys())
    llaves_sin_mapear = sorted(todas_llaves - llaves_mapeadas)

    print("=== LLAVES CRUDAS SIN MAPEAR EN FIELD_MAP ===")
    print("(revisa si alguna de estas es un campo de estatus/completitud)\n")
    for k in llaves_sin_mapear:
        marca = " ⚠️ posible estatus" if any(p in k.lower() for p in PALABRAS_ESTATUS) else ""
        print(f"  - {k}{marca}")

    print(f"\nTotal llaves crudas: {len(todas_llaves)} · Mapeadas: {len(llaves_mapeadas & todas_llaves)} "
          f"· Sin mapear: {len(llaves_sin_mapear)}")

    # ── 2. Conteo de valores para cada llave candidata a estatus ───────────
    candidatas = [k for k in todas_llaves if any(p in k.lower() for p in PALABRAS_ESTATUS)]
    if candidatas:
        print("\n=== DISTRIBUCIÓN DE VALORES — CAMPOS CANDIDATOS A ESTATUS ===")
        for k in candidatas:
            valores = Counter(str(r.get(k)) for r in raw)
            print(f"\n  Campo: {k}")
            for val, n in valores.most_common(10):
                print(f"    {val!r}: {n}")
    else:
        print("\n(No se encontró ningún campo con nombre sugerente de estatus/completitud "
              "entre las llaves crudas — revisa manualmente el listado de arriba por si acaso.)")

    # ── 3. Registros sin Modified Date ──────────────────────────────────────
    sin_modified = sum(1 for r in raw if not r.get("Modified Date"))
    print(f"\n=== REGISTROS SIN 'Modified Date': {sin_modified} de {len(raw)} ===")

    # ── 4. Duraciones tras transformación real de la app ───────────────────
    df = _transform(raw)
    print("\n=== DISTRIBUCIÓN DE duracion_min (tras transformación real) ===")
    print(df["duracion_min"].describe())
    print(f"\nRegistros con duracion_min < 1 minuto: {(df['duracion_min'] < 1).sum()}")
    print(f"Registros con duracion_min < 2 minutos: {(df['duracion_min'] < 2).sum()}")

    # ── 5. Corte del operativo y exclusiones ────────────────────────────────
    antes_ancla = (df["fecha_creacion"] < ANCLA_OPERATIVO).sum()
    de_prueba = df["nombre_encuestador"].str.strip().str.lower().isin(NOMBRES_EXCLUIDOS).sum()
    print(f"\n=== CORTE DEL OPERATIVO ===")
    print(f"Registros antes del ancla (18 jul 2026, 9:00 AM): {antes_ancla}")
    print(f"Registros de nombres de prueba excluidos ({', '.join(NOMBRES_EXCLUIDOS)}): {de_prueba}")
    print(f"Registros que quedarían dentro del operativo real: "
          f"{len(df) - antes_ancla - de_prueba} (aprox., puede haber solape)")

    print("\n✅ Diagnóstico completo. Pega esta salida completa de vuelta para decidir "
          "si hace falta un filtro adicional de completitud en _transform().")


if __name__ == "__main__":
    main()
