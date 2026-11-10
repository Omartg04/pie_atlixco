#!/usr/bin/env python3
"""Exporta las visitas, una fila por visita, para analizarlas fuera del tablero.

Uso, desde cualquier carpeta:

    python3 exportar_visitas.py                      todo el operativo
    python3 exportar_visitas.py --fecha 2026-11-10   un solo día

Salida: exportes/visitas_AAAAMMDD_HHMM.csv (UTF-8, abre bien en Excel).

Mismo procesamiento que el tablero: fecha recuperada de `start`, GPS rescatado
y reglas de correcciones_seccion.csv.

Lo que el archivo NO trae, a propósito: coordenadas ni respuestas del
cuestionario. La ubicación se resuelve aquí, en tu computadora, y sale
convertida en dos datos que no identifican domicilios: la sección cuyo
polígono contiene el punto y, si no coincide con la declarada, la distancia en
metros al borde de la declarada. Eso basta para revisar cruces de frontera sin
que las ubicaciones salgan de tu máquina.

Sí trae nombres de brigadista: es para uso interno de coordinación.
"""
import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd  # noqa: E402

from reporte_brigadista import BASE_DIR, cargar_visitas  # noqa: E402

MX = "America/Mexico_City"
COLUMNAS = [
    "registro_id", "fecha_visita", "hora_inicio", "minutos", "brigadista_codigo",
    "brigadista", "seccion_declarada_original", "seccion_operativa",
    "seccion_por_gps", "dist_borde_declarada_m", "resultado", "entrega_volante",
    "gps_registrado", "gps_precision_m", "version_formulario", "incidencias",
    "fecha_recepcion_kobo",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fecha", help="AAAA-MM-DD; omitido = todo el operativo")
    args = ap.parse_args()

    import geo_secciones as geo

    vis, _reglas, gps = cargar_visitas(con_gps=True)
    polis = geo.cargar_poligonos(os.path.join(BASE_DIR, "data", "m1_contornos.geojson"))

    ini = pd.to_datetime(vis["inicio"], errors="coerce", utc=True)
    fin = pd.to_datetime(vis["fin"], errors="coerce", utc=True)
    vis["hora_inicio"] = ini.dt.tz_convert(MX).dt.strftime("%H:%M")
    vis["minutos"] = ((fin - ini).dt.total_seconds() / 60).round(1)

    # Ubicación → sección y distancia al borde. Las coordenadas se quedan aquí.
    sec_gps, dist = {}, {}
    if not gps.empty:
        orig = vis.set_index("registro_id")["seccion_declarada_original"].to_dict()
        for r in gps.itertuples(index=False):
            try:
                lat, lon = float(r.latitud), float(r.longitud)
            except (TypeError, ValueError):
                continue
            s = geo.seccion_de_punto(lat, lon, polis)
            sec_gps[r.registro_id] = "" if s is None else str(s)
            dec = str(orig.get(r.registro_id, ""))
            if s is not None and dec.isdigit() and int(dec) != s:
                d = geo.distancia_al_borde_m(lat, lon, int(dec), polis)
                dist[r.registro_id] = round(d) if d is not None else ""
    vis["seccion_por_gps"] = vis["registro_id"].map(sec_gps).fillna("")
    vis["dist_borde_declarada_m"] = vis["registro_id"].map(dist).fillna("")

    if args.fecha:
        vis = vis[vis["fecha_visita"] == args.fecha]
        if vis.empty:
            sys.exit(f"No hay visitas con fecha {args.fecha}. Corre diagnostico_dias.py "
                     f"para ver si ya sincronizaron.")

    salida_dir = os.path.join(BASE_DIR, "exportes")
    os.makedirs(salida_dir, exist_ok=True)
    ahora = datetime.now().strftime("%Y%m%d_%H%M")
    sufijo = f"_{args.fecha.replace('-', '')}" if args.fecha else ""
    ruta = os.path.join(salida_dir, f"visitas{sufijo}_{ahora}.csv")
    vis = vis.sort_values(["fecha_visita", "brigadista_codigo", "hora_inicio"])
    vis[[c for c in COLUMNAS if c in vis.columns]].to_csv(ruta, index=False,
                                                          encoding="utf-8-sig")
    print(f"{len(vis):,} visitas · {vis['fecha_visita'].nunique()} jornada(s) → {ruta}")


if __name__ == "__main__":
    main()
