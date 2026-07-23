"""
Diagnóstico de mapeo de campos — Data API de Bubble ("Encuesta")

Corre esto localmente (no desde el sandbox) para confirmar, con datos reales,
qué variante de cada campo dudoso existe realmente en Bubble, y cuántos
registros la tienen contestada. Esto nos dice si el problema de "solo
algunos tabulados se reportan" es:
  (a) el instrumento sigue en captura (formulario largo, respuestas parciales
      normales), o
  (b) el FIELD_MAP tiene mal el nombre de algún campo (ej. mayúscula/minúscula
      equivocada) y por eso SIEMPRE sale vacío, sin importar si el
      encuestado sí contestó esa página.

Uso:
    export BUBBLE_PRIVATE_KEY="4079ccda281d8c251f26ec482bf7356d"
    python diagnostico_field_map.py
"""
import os
import json

import requests

BUBBLE_ENDPOINT = "https://encuestainduccionatlixco.bubbleapps.io/api/1.1/obj/Encuesta"
PRIVATE_KEY = os.getenv("BUBBLE_PRIVATE_KEY", "")

# Candidatos a verificar: (nombre amigable, [variantes posibles del campo])
CANDIDATOS = [
    ("aprobación alcaldesa",        ["P22_1_texto"]),
    ("aprobación gobernador",       ["P22_2_texto"]),
    ("aprobación presidenta",       ["P22_3_texto"]),
    ("conocimiento Arturo",         ["P8_1_texto"]),
    ("Amor Puebla",                 ["atl_1_texto", "Atl_1_texto"]),
    ("percepción inseguridad",      ["atl_3_texto", "Atl_3_texto"]),
    ("comité vigilancia",           ["atl_4_texto", "Atl_4_texto"]),
    ("alarma vecinal",              ["atl_5_texto", "Atl_5_texto"]),
    ("seguridad (Atl_2)",           ["atl_2_texto", "Atl_2_texto"]),
    ("cumplimiento Arturo",         ["P14_1_texto"]),
    ("honestidad Arturo",           ["P10_1_texto"]),
    ("buena candidatura",           ["P15_1_texto"]),
    ("votar o no",                  ["P16_1_texto"]),
    ("principal problema estado",  ["P2_1_texto"]),
    ("otro problema estado",        ["P2_1_otro"]),
    ("tipo inseguridad",            ["P2_2_text", "P2_2_texto"]),
    ("otro tipo inseguridad",       ["P2_2_otro"]),
]


def main():
    if not PRIVATE_KEY:
        print('⚠️  Corre primero: export BUBBLE_PRIVATE_KEY="tu_key_aqui"')
        return

    headers = {"Authorization": f"Bearer {PRIVATE_KEY}"}
    todos = []
    cursor = 0
    while True:
        resp = requests.get(BUBBLE_ENDPOINT, headers=headers,
                             params={"limit": 100, "cursor": cursor}, timeout=20)
        resp.raise_for_status()
        body = resp.json().get("response", {})
        batch = body.get("results", [])
        todos.extend(batch)
        remaining = body.get("remaining", 0)
        if remaining <= 0 or not batch:
            break
        cursor += 100

    print(f"Total de registros descargados: {len(todos)}\n")

    if not todos:
        print("⚠️  No hay registros en Bubble todavía.")
        return

    # ── Todas las llaves que existen en al menos un registro ────────────────
    llaves_presentes = set()
    for r in todos:
        llaves_presentes.update(r.keys())

    print("── Verificación por campo candidato ─────────────────────────────")
    for nombre_amigable, variantes in CANDIDATOS:
        encontrada = None
        for v in variantes:
            if v in llaves_presentes:
                encontrada = v
                break
        if encontrada is None:
            print(f"❌ {nombre_amigable}: NINGUNA variante existe ({variantes}) — revisar en Bubble")
            continue
        no_nulos = sum(1 for r in todos if r.get(encontrada) not in (None, "", []))
        print(f"✅ {nombre_amigable}: usa '{encontrada}' — {no_nulos}/{len(todos)} registros contestados")

    print("\n── Todas las llaves detectadas en los datos (referencia) ────────")
    for k in sorted(llaves_presentes):
        print(f"   - {k}")

    print("\n── Valores ÚNICOS reales por campo (para corregir las listas de opciones) ──")
    campos_a_revisar = [
        "P22_1_texto", "P22_2_texto", "P22_3_texto", "P8_1_texto",
        "atl_1_texto", "atl_3_texto", "atl_4_texto", "atl_5_texto", "atl_2_texto",
        "P14_1_texto", "P10_1_texto", "P15_1_texto", "P16_1_texto",
        "P2_1_texto", "P2_2_text",
    ]
    for campo in campos_a_revisar:
        valores = sorted({str(r.get(campo)) for r in todos if r.get(campo) not in (None, "", [])})
        print(f"\n{campo}:")
        for v in valores:
            print(f"   - {v!r}")


if __name__ == "__main__":
    main()