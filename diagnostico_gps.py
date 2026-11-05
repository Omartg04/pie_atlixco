#!/usr/bin/env python3
"""Diagnóstico de georreferencia — PIE Atlixco.

Contesta por qué M3 no muestra puntos: si el problema es que no hay GPS en los
datos, o en qué forma lo manda Kobo.

Uso, desde la raíz del repo:

    python3 diagnostico_gps.py

Lee las credenciales de .streamlit/secrets.toml. No imprime coordenadas ni
ningún dato de personas: solo conteos y nombres de campo.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def leer_secrets() -> dict:
    ruta = Path(".streamlit/secrets.toml")
    if not ruta.exists():
        sys.exit("No encuentro .streamlit/secrets.toml. Corre esto desde la raíz del repo.")
    try:
        import tomllib
        with ruta.open("rb") as fh:
            return tomllib.load(fh).get("kobo", {})
    except ModuleNotFoundError:
        cfg, bloque = {}, False
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            t = linea.strip()
            if t.startswith("["):
                bloque = t == "[kobo]"
                continue
            if bloque and "=" in t:
                k, v = t.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
        return cfg


def main() -> None:
    import kobo_connector as kc

    cfg = leer_secrets()
    faltan = [k for k in ("base_url", "asset_uid", "api_token") if not cfg.get(k)]
    if faltan:
        sys.exit("Faltan en [kobo]: " + ", ".join(faltan))

    print("Consultando Kobo...")
    envios = kc.fetch_all(cfg["base_url"], cfg["asset_uid"], cfg["api_token"])
    print(f"\n{'='*62}\nENVÍOS RECIBIDOS: {len(envios)}\n{'='*62}")
    if not envios:
        print("Kobo no devolvió registros. Revisa el asset_uid y que haya envíos "
              "sincronizados.")
        return

    # ── 1. ¿Qué campos llegan? ──────────────────────────────────────────────
    llaves = Counter()
    for r in envios:
        llaves.update(r.keys())
    rel = [k for k in llaves if "gps" in k.lower() or "geo" in k.lower()
           or "locat" in k.lower() or k.endswith("ubicacion")]
    print("\n1 · CAMPOS DE UBICACIÓN PRESENTES")
    if rel:
        for k in sorted(rel):
            print(f"    {k:30} en {llaves[k]:>5} de {len(envios)} envíos")
    else:
        print("    NINGUNO. Kobo no está mandando ningún campo de ubicación.")
        print("    Los campos vacíos se omiten del JSON, así que esto significa")
        print("    que ninguna visita registró coordenadas.")

    # ── 2. ¿En qué forma? ───────────────────────────────────────────────────
    gps_con_valor = gps_vacio = gps_ausente = 0
    geoloc_util = 0
    for r in envios:
        v = kc._get(r, "gps")
        if v is None:
            gps_ausente += 1
        elif str(v).strip() == "":
            gps_vacio += 1
        else:
            gps_con_valor += 1
        g = r.get("_geolocation")
        if isinstance(g, (list, tuple)) and len(g) >= 2 \
                and g[0] is not None and g[1] is not None:
            geoloc_util += 1

    print("\n2 · FORMA EN QUE LLEGA")
    print(f"    campo 'gps' con valor      {gps_con_valor:>5}")
    print(f"    campo 'gps' vacío ('')     {gps_vacio:>5}  ← el conector pierde estos")
    print(f"    campo 'gps' ausente        {gps_ausente:>5}")
    print(f"    '_geolocation' utilizable  {geoloc_util:>5}")

    # ── 3. ¿Qué resuelve el conector hoy? ───────────────────────────────────
    schema = json.load(open("schema_xlsform_v06.json", encoding="utf-8"))
    datos = kc.transform(envios, schema)
    resueltos = len(datos["supervision_gps_privado"])
    print("\n3 · LO QUE RESUELVE EL CONECTOR")
    print(f"    visitas con coordenada     {resueltos:>5} de {len(datos['visitas_operativas'])}")
    print(f"    visitas sin GPS (estado)   {datos['estado']['visitas_sin_gps']:>5}")

    # ── 4. Veredicto ────────────────────────────────────────────────────────
    print(f"\n{'='*62}\nVEREDICTO\n{'='*62}")
    recuperables = gps_vacio and geoloc_util
    if resueltos:
        print(f"    HAY GPS: {resueltos} visitas con coordenada.")
        print("    Si M3 no muestra el mapa, el problema es el despliegue, no los datos.")
    elif recuperables:
        print("    HAY GPS RECUPERABLE pero el conector lo descarta.")
        print(f"    {gps_vacio} envíos traen 'gps' vacío y '_geolocation' utilizable:")
        print("    el respaldo del conector solo entra cuando 'gps' está AUSENTE,")
        print("    no cuando llega como cadena vacía. El parche de app_utils lo")
        print("    corrige rellenando 'gps' desde '_geolocation' antes de agregar.")
    else:
        print("    NO HAY GPS EN LOS DATOS.")
        print("    El campo de ubicación es opcional en el instrumento. Si los")
        print("    brigadistas lo omiten o el teléfono no fija posición, la visita")
        print("    se captura sin coordenadas. Para que haya puntos que mostrar,")
        print("    hay que pedir que lo llenen o volverlo obligatorio en el XLSForm.")

    print("\n5 · UN ENVÍO DE MUESTRA (solo nombres de campo, sin valores)")
    print("   ", sorted(envios[0].keys()))


if __name__ == "__main__":
    main()
