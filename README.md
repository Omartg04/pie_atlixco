# PIE Atlixco — Plan Territorial (Arturo Solano Escobedo)

App Streamlit multipágina.

```
Home.py                          # landing
pages/1_M1_Plan_Territorial.py   # mapa + ficha de sección + tabla ranking (activo)
pages/2_M2_Manzanas.py           # placeholder, pendiente de insumo de manzanas
utils.py                         # CSS compartido, carga de datos, helpers
data/
  SPT_indice_secciones_enriquecido.csv
  atlixco_secciones_zonas.geojson
```

## Correr local
```
pip install -r requirements.txt
streamlit run Home.py
```

## Desplegar en Streamlit Cloud
Sube este folder como repo de GitHub y apunta la app principal a `Home.py`.

## Pendiente — Módulo 2 (manzanas)
Requiere estos dos archivos en `data/` para activarse:
- `atlixco_unificado_web.geojson`
- `atlixco_37_secciones_manzana.csv`
