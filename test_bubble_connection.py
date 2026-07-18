"""
Prueba de conexión — Data API de Bubble (formulario de inducción Atlixco)

Cómo correrlo:
    1. Ajusta BUBBLE_THING_NAME abajo con el nombre real del "thing" en Bubble
       (la palabra que va después de /obj/ en el endpoint).
    2. En terminal, desde tu máquina (NO desde este sandbox):
         python test_bubble_connection.py
    3. Revisa la salida: debe traer count/remaining/results y un registro
       de ejemplo con las llaves del diccionario de variables.

No commitear este archivo con la key adentro. Aquí la dejamos como variable
de entorno para que ni siquiera quede escrita en el script si lo compartes.
"""
import json
import os

import requests

# ── Config — ajustar antes de correr ────────────────────────────────────────
BUBBLE_DATA_API_ROOT = "https://encuestainduccionatlixco.bubbleapps.io/api/1.1/obj"
BUBBLE_THING_NAME    = "Encuesta"

# La private key se lee de variable de entorno para no dejarla escrita aquí.
# En tu terminal, antes de correr el script:
#   export BUBBLE_PRIVATE_KEY="4079ccda281d8c251f26ec482bf7356d"
PRIVATE_KEY = os.getenv("BUBBLE_PRIVATE_KEY", "")

ENDPOINT = f"{BUBBLE_DATA_API_ROOT}/{BUBBLE_THING_NAME}"


def main():
    if not PRIVATE_KEY:
        print("⚠️  No se encontró BUBBLE_PRIVATE_KEY en el entorno.")
        print('    Corre primero: export BUBBLE_PRIVATE_KEY="tu_key_aqui"')
        return

    if BUBBLE_THING_NAME == "CAMBIAR_ESTO":
        print("⚠️  Falta ajustar BUBBLE_THING_NAME con el nombre real del thing.")
        return

    headers = {"Authorization": f"Bearer {PRIVATE_KEY}"}
    params = {"limit": 5, "cursor": 0}

    print(f"→ Consultando: {ENDPOINT}")
    try:
        resp = requests.get(ENDPOINT, headers=headers, params=params, timeout=15)
        print(f"→ Status code: {resp.status_code}")
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Error de conexión: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"   Respuesta cruda: {e.response.text[:500]}")
        return

    body = resp.json().get("response", {})
    results = body.get("results", [])
    remaining = body.get("remaining", "?")
    count = body.get("count", "?")

    print(f"\n✅ Conexión exitosa.")
    print(f"   count (total tabla, sin filtros) : {count}")
    print(f"   remaining (después de este batch) : {remaining}")
    print(f"   registros en este batch           : {len(results)}")

    if results:
        print("\n── Primer registro (crudo) ──────────────────────────")
        print(json.dumps(results[0], indent=2, ensure_ascii=False))

        print("\n── Llaves presentes en el registro ──────────────────")
        for k in results[0].keys():
            print(f"   - {k}")
    else:
        print("\n⚠️  No se recibieron registros. Revisa si ya hay encuestas")
        print("    capturadas en Bubble o si el nombre del thing es correcto.")


if __name__ == "__main__":
    main()