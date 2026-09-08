import json

RUTA_GEOJSON = "/Users/omartellez/pie_atlixco/data/atlixco_unificado_web_capas.geojson"

with open(RUTA_GEOJSON, "r", encoding="utf-8") as f:
    geo = json.load(f)

props0 = geo["features"][0]["properties"]
print("Todas las llaves disponibles en 'properties':")
for k in sorted(props0.keys()):
    print(f"  {k!r}: {props0[k]!r}")

# Busca candidatos que contengan "secc" en el nombre (variantes probables)
print("\nLlaves que contienen 'secc':")
for k in props0.keys():
    if "secc" in k.lower():
        print(f"  {k!r}")
