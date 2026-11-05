#!/usr/bin/env python3
"""Genera un KML con las manzanas donde el operativo todavía no pasa.

Cruza los puntos GPS de las visitas de Kobo contra los polígonos de manzana y
marca cuáles ya tienen visita y cuáles no. El KML se importa a Google My Maps
igual que los mapas de sección.

Uso, desde la raíz del repo:

    python3 mapa_pendientes.py
    python3 mapa_pendientes.py --secciones 160,161,162 --salida zona_160.kml
    python3 mapa_pendientes.py --manzanas data/otro.geojson --secciones 208

LÍMITE IMPORTANTE: una manzana sale como pendiente si no hay ninguna visita
GEORREFERENCIADA dentro. Las visitas sin GPS no se pueden ubicar, así que una
manzana trabajada por un brigadista cuyo teléfono no registró posición aparece
como pendiente. El script reporta cuántas visitas quedaron sin ubicar y de qué
brigadistas, para que el dato se lea con esa reserva.
"""
import argparse
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geo_secciones import (anillos, bbox, dentro, distancia_al_borde_m)

MANZANAS = "data/manzanas_zona_160.geojson"
CONTORNOS = "data/m1_contornos.geojson"

AMBAR_FILL, AMBAR_LINE = "8c3da3e8", "ff3da3e8"
GRIS_FILL, GRIS_LINE = "3a9e9e9e", "ff6a6a6a"
CONTORNO_LINE = "ff5b7a9e"


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


def _ring_kml(r):
    return " ".join(f"{x},{y},0" for x, y in r)


def _placemark(geom, estilo, nombre, desc=""):
    out = []
    coords = ([geom["coordinates"]] if geom["type"] == "Polygon"
              else geom["coordinates"])
    for poly in coords:
        ext, ints = poly[0], poly[1:]
        huecos = "".join(
            f"<innerBoundaryIs><LinearRing><coordinates>{_ring_kml(r)}"
            f"</coordinates></LinearRing></innerBoundaryIs>" for r in ints)
        out.append(
            f"<Placemark><name>{html.escape(nombre)}</name>"
            f"<description><![CDATA[{desc}]]></description>"
            f"<styleUrl>#{estilo}</styleUrl><Polygon>"
            f"<outerBoundaryIs><LinearRing><coordinates>{_ring_kml(ext)}"
            f"</coordinates></LinearRing></outerBoundaryIs>{huecos}"
            f"</Polygon></Placemark>")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--secciones", default="160,161,162",
                    help="separadas por coma; por default el territorio de la 160 vieja")
    ap.add_argument("--manzanas", default=MANZANAS)
    ap.add_argument("--contornos", default=CONTORNOS)
    ap.add_argument("--salida", default="manzanas_pendientes.kml")
    ap.add_argument("--snap", type=float, default=30.0,
                    help="metros: un punto que cae en la calle se asigna a la "
                         "manzana más cercana dentro de este margen (0 desactiva)")
    args = ap.parse_args()

    import kobo_connector as kc

    secciones = {int(x) for x in args.secciones.split(",") if x.strip()}
    cfg = leer_secrets()
    faltan = [k for k in ("base_url", "asset_uid", "api_token") if not cfg.get(k)]
    if faltan:
        sys.exit("Faltan en [kobo]: " + ", ".join(faltan))

    with open(args.manzanas, encoding="utf-8") as fh:
        gj = json.load(fh)
    mz = [f for f in gj["features"] if f["properties"].get("seccion") in secciones]
    if not mz:
        sys.exit(f"No hay manzanas de {sorted(secciones)} en {args.manzanas}")
    for f in mz:
        f["_rings"] = anillos(f["geometry"])
        f["_bb"] = bbox(f["_rings"])
    print(f"Manzanas en el territorio: {len(mz)}")

    print("Consultando Kobo...")
    envios = kc.fetch_all(cfg["base_url"], cfg["asset_uid"], cfg["api_token"])

    puntos, sin_gps = [], []
    for raw in envios:
        lat, lon, _p = kc._gps(kc._get(raw, "gps"), raw.get("_geolocation"))
        brig = str(raw.get("brigadista") or "?")
        if lat is None:
            sin_gps.append(brig)
        else:
            puntos.append((lat, lon, brig,
                           str(raw.get("inicio") or "")[:10]))
    print(f"Visitas: {len(envios)}  ·  con GPS {len(puntos)}  ·  sin GPS {len(sin_gps)}")

    # ── asignar cada punto a una manzana ────────────────────────────────────
    visitas = defaultdict(list)
    dentro_n = snap_n = fuera_n = 0
    for lat, lon, brig, fecha in puntos:
        destino = None
        for f in mz:
            bb = f["_bb"]
            if not (bb[0] <= lon <= bb[2] and bb[1] <= lat <= bb[3]):
                continue
            if any(dentro(lon, lat, r) for r in f["_rings"]):
                destino = f
                break
        if destino is not None:
            dentro_n += 1
        elif args.snap > 0:
            # Un punto puede caer en la calle: con 17 m de precisión típica, el
            # domicilio real está en la manzana de enfrente. Se asigna a la más
            # cercana dentro del margen en vez de descartarlo.
            mejor, mejor_d = None, None
            for f in mz:
                d = distancia_al_borde_m(
                    lat, lon, 0,
                    {0: (f["_bb"], f["_rings"], 0)})
                if d is not None and (mejor_d is None or d < mejor_d):
                    mejor, mejor_d = f, d
            if mejor is not None and mejor_d <= args.snap:
                destino, snap_n = mejor, snap_n + 1
        if destino is None:
            fuera_n += 1
            continue
        visitas[destino["properties"]["id_unidad"]].append((brig, fecha))

    print(f"  dentro de una manzana: {dentro_n}")
    print(f"  asignadas por cercanía (<={args.snap:.0f} m): {snap_n}")
    print(f"  fuera del territorio o sin manzana cerca: {fuera_n}")

    visitadas = [f for f in mz if visitas.get(f["properties"]["id_unidad"])]
    pendientes = [f for f in mz if not visitas.get(f["properties"]["id_unidad"])]

    print(f"\n{'='*62}")
    print(f"MANZANAS YA VISITADAS: {len(visitadas)} de {len(mz)}")
    print(f"MANZANAS PENDIENTES:   {len(pendientes)}")
    por_sec = Counter(f["properties"]["seccion"] for f in pendientes)
    tot_sec = Counter(f["properties"]["seccion"] for f in mz)
    for s in sorted(tot_sec):
        print(f"    sección {s}: {por_sec.get(s,0)} pendientes de {tot_sec[s]}")
    ln_pend = sum(f["properties"].get("LN_manzana") or 0 for f in pendientes)
    print(f"    LN en las pendientes: {ln_pend:,.0f} "
          f"(las del bloque 160R no tienen LN asignada por manzana)")

    if sin_gps:
        print(f"\n⚠️  {len(sin_gps)} visitas NO se pudieron ubicar por falta de GPS.")
        print("    Una manzana trabajada por estos brigadistas sale como pendiente:")
        for b, n in Counter(sin_gps).most_common():
            print(f"      {b}: {n}")

    # ── KML ─────────────────────────────────────────────────────────────────
    cuerpo = []
    try:
        with open(args.contornos, encoding="utf-8") as fh:
            cont = json.load(fh)
        refs = [f for f in cont["features"]
                if f["properties"].get("seccion_geom") in secciones]
        if refs:
            cuerpo.append("<Folder><name>Contorno de las secciones</name>" + "".join(
                _placemark(f["geometry"], "contorno",
                           f"Seccion {f['properties']['seccion_geom']}")
                for f in refs) + "</Folder>")
    except FileNotFoundError:
        pass

    marcas = []
    for f in sorted(pendientes, key=lambda x: (x["properties"]["seccion"],
                                               x["properties"]["manzana"])):
        p = f["properties"]
        ln = p.get("LN_manzana")
        etiqueta = f"Mz {p['manzana']} · Sec {p['seccion']}"
        if ln:
            etiqueta += f" · ~{round(ln)} electores"
        marcas.append(_placemark(
            f["geometry"], "pendiente", etiqueta,
            f"<b>SIN VISITA REGISTRADA</b><br>Sección {p['seccion']}<br>"
            f"Manzana {p['manzana']}<br>{p.get('nav_nombre') or 'sin colonia'}<br>"
            + (f"LN estimada: ~{round(ln)} electores<br>" if ln else
               "Sin LN asignada por manzana (bloque reseccionado)<br>")
            + f"ID: {p.get('id_unidad')}"))
    cuerpo.append(f"<Folder><name>PENDIENTES ({len(pendientes)})</name>"
                  + "".join(marcas) + "</Folder>")

    marcas = []
    for f in sorted(visitadas, key=lambda x: (x["properties"]["seccion"],
                                              x["properties"]["manzana"])):
        p = f["properties"]
        vs = visitas[p["id_unidad"]]
        brigs = ", ".join(sorted({b for b, _ in vs}))
        fechas = ", ".join(sorted({d for _, d in vs if d}))
        marcas.append(_placemark(
            f["geometry"], "visitada", f"Mz {p['manzana']} · {len(vs)} visitas",
            f"<b>YA VISITADA</b><br>Sección {p['seccion']}<br>"
            f"Manzana {p['manzana']}<br>{len(vs)} visitas registradas<br>"
            f"Brigadistas: {brigs}<br>Fechas: {fechas}"))
    cuerpo.append(f"<Folder><name>Ya visitadas ({len(visitadas)})</name>"
                  + "".join(marcas) + "</Folder>")

    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<name>Atlixco · Manzanas pendientes · secciones {', '.join(str(s) for s in sorted(secciones))}</name>
<description><![CDATA[{len(pendientes)} manzanas sin visita registrada de {len(mz)}.<br>
<b>Ojo:</b> {len(sin_gps)} visitas no traen GPS y no se pudieron ubicar, asi que
alguna manzana marcada como pendiente puede haberse trabajado ya.<br>
<i>Operativo de induccion 2026 - PIE Atlixco</i>]]></description>
<Style id="contorno"><LineStyle><color>{CONTORNO_LINE}</color><width>4</width></LineStyle>
<PolyStyle><fill>0</fill><outline>1</outline></PolyStyle></Style>
<Style id="pendiente"><LineStyle><color>{AMBAR_LINE}</color><width>2</width></LineStyle>
<PolyStyle><color>{AMBAR_FILL}</color><fill>1</fill><outline>1</outline></PolyStyle></Style>
<Style id="visitada"><LineStyle><color>{GRIS_LINE}</color><width>1</width></LineStyle>
<PolyStyle><color>{GRIS_FILL}</color><fill>1</fill><outline>1</outline></PolyStyle></Style>
{''.join(cuerpo)}
</Document></kml>"""

    Path(args.salida).write_text(doc, encoding="utf-8")
    print(f"\nKML escrito: {args.salida} ({len(doc)/1024:.0f} KB)")
    print("Importalo en Google My Maps con 'Crear capa -> Importar'.")


if __name__ == "__main__":
    main()
