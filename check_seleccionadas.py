import json

RUTA_GEOJSON = "/Users/omartellez/pie_atlixco/data/atlixco_unificado_web_capas.geojson"

with open(RUTA_GEOJSON, "r", encoding="utf-8") as f:
    geo = json.load(f)

seleccionadas = [
    f["properties"] for f in geo["features"]
    if f.get("properties", {}).get("seleccionada_500") is True
]

print(f"Total features con seleccionada_500 is True: {len(seleccionadas)}")

if seleccionadas:
    print("\nPrimeras 5:")
    for p in seleccionadas[:5]:
        print(f"  seccion={p.get('seccion')!r} ({type(p.get('seccion'))}), "
              f"LN_estimada_manzana={p.get('LN_estimada_manzana')!r}")

    secciones_nulas = sum(1 for p in seleccionadas if p.get("seccion") is None)
    print(f"\nDe esas, con seccion=None: {secciones_nulas}")
else:
    print("\n[!] Cero features cumplen seleccionada_500 is True — revisar si el valor "
          "real es 1/0, 'True'/'False' string, u otro tipo mezclado en el archivo.")
    # Muestra tipos únicos otra vez con conteo
    from collections import Counter
    tipos = Counter(type(f.get("properties", {}).get("seleccionada_500")).__name__ for f in geo["features"])
    print("Conteo por tipo de dato de seleccionada_500:", dict(tipos))
