import json

RUTA_GEOJSON = "/Users/omartellez/pie_atlixco/data/atlixco_unificado_web_capas.geojson"

with open(RUTA_GEOJSON, "r", encoding="utf-8") as f:
    geo = json.load(f)

print(f"Total features: {len(geo['features'])}")

# Muestra las primeras 3 features con sus props relevantes, tal cual vienen
for feat in geo["features"][:3]:
    props = feat.get("properties", {})
    print("---")
    print("seccion_electoral:", repr(props.get("seccion_electoral")), type(props.get("seccion_electoral")))
    print("seleccionada_500:", repr(props.get("seleccionada_500")), type(props.get("seleccionada_500")))
    print("LN_estimada_manzana:", repr(props.get("LN_estimada_manzana")), type(props.get("LN_estimada_manzana")))

# Cuenta cuántas features tienen seleccionada_500 "truthy" bajo distintas comparaciones
vals = set(props.get("seleccionada_500") for f in geo["features"] for props in [f.get("properties", {})])
print("\nValores únicos de seleccionada_500 en todo el archivo:", vals)
