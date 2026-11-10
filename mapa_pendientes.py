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


# ── Reporte HTML autocontenido ──────────────────────────────────────────────
# El mapa es SVG generado en Python, sin JavaScript ni librerías. Mismo criterio
# que ya se había tomado en el proyecto al descartar D3 para los mapas de calor:
# un archivo que se abre en cualquier navegador, se manda por correo y no
# depende de que cargue nada de internet.

_C = {"bg": "#14181f", "panel": "#1b212b", "borde": "rgba(255,255,255,.10)",
      "texto": "#eef1f0", "tenue": "#8b95a8", "mudo": "#5e6779",
      "ambar": "#e8a33d", "acero": "#5b7a9e", "verde": "#3f7a52"}


def _proyecta(lat, lon, ref_lat):
    """Equirectangular local. A escala de un municipio la distorsión es
    inapreciable y evita arrastrar pyproj."""
    import math
    return lon * math.cos(math.radians(ref_lat)), lat


def _svg(mz, visitas, refs_geom, ancho=900, alto=620, margen=14):
    pts = []
    for f in mz:
        for r in f["_rings"]:
            pts.extend(r)
    for g in refs_geom:
        for r in anillos(g):
            pts.extend(r)
    if not pts:
        return "<p>Sin geometría.</p>"
    ref_lat = sum(y for _, y in pts) / len(pts)
    proj = [_proyecta(y, x, ref_lat) for x, y in pts]
    xs = [p[0] for p in proj]; ys = [p[1] for p in proj]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    dx, dy = (x1 - x0) or 1e-9, (y1 - y0) or 1e-9
    esc = min((ancho - 2 * margen) / dx, (alto - 2 * margen) / dy)
    offx = (ancho - dx * esc) / 2
    offy = (alto - dy * esc) / 2

    def path(ring):
        d = []
        for lon, lat in ring:
            px, py = _proyecta(lat, lon, ref_lat)
            d.append(f"{offx + (px - x0) * esc:.1f},{alto - offy - (py - y0) * esc:.1f}")
        return "M" + "L".join(d) + "Z"

    capas = []
    for g in refs_geom:
        for r in anillos(g):
            capas.append(f'<path d="{path(r)}" fill="none" '
                         f'stroke="{_C["acero"]}" stroke-width="1.6" opacity=".85"/>')
    vis, pen = [], []
    for f in mz:
        tiene = bool(visitas.get(f["properties"]["id_unidad"]))
        destino = vis if tiene else pen
        p = f["properties"]
        tip = (f"{p.get('nav_nombre') or 'sin colonia'} · Mz {p['manzana']} · "
               f"Sec {p['seccion']}")
        if tiene:
            tip += f" · {len(visitas[p['id_unidad']])} visitas"
        for r in f["_rings"]:
            destino.append(
                f'<path d="{path(r)}" fill="{_C["acero"] if tiene else _C["ambar"]}" '
                f'fill-opacity="{.22 if tiene else .72}" '
                f'stroke="{_C["acero"] if tiene else _C["ambar"]}" '
                f'stroke-width=".7"><title>{html.escape(tip)}</title></path>')
    return (f'<svg viewBox="0 0 {ancho} {alto}" width="100%" '
            f'style="max-width:{ancho}px;height:auto;display:block;margin:0 auto">'
            + "".join(vis) + "".join(pen) + "".join(capas) + "</svg>")


def _tabla(grupo, titulo, nota=""):
    if not grupo:
        return ""
    filas = []
    for n, c in sorted(grupo.items(), key=lambda kv: -(kv[1]["mz"] - kv[1]["vis"])):
        faltan = c["mz"] - c["vis"]
        ln_p = c["ln"] - c["ln_vis"]
        ln_txt = f"{ln_p:,.0f}" if c["ln"] else "<span style='color:#5e6779'>s/d</span>"
        secs = ", ".join(str(x) for x in sorted(c["secs"]))
        etq = ("sin colonia asignada"
               if str(n).strip().upper() in {"NINGUNO", "NINGUNA", "SIN COLONIA", ""}
               else n)
        filas.append(
            f"<tr><td>{html.escape(etq)}</td><td class='n'>{c['mz']}</td>"
            f"<td class='n'><b>{faltan}</b></td><td class='n'>{ln_txt}</td>"
            f"<td class='s'>{secs}</td></tr>")
    return (f"<h3>{titulo} <span class='cuenta'>{len(grupo)}</span></h3>"
            + (f"<p class='nota'>{nota}</p>" if nota else "")
            + "<table><thead><tr><th>Colonia o localidad</th><th class='n'>Manzanas</th>"
              "<th class='n'>Faltan</th><th class='n'>LN pendiente</th>"
              "<th class='s'>Secciones</th></tr></thead><tbody>"
            + "".join(filas) + "</tbody></table>")


def _reporte_html(mz, visitas, col, sin_tocar, parciales, completas, refs_geom,
                  secciones, sin_gps, n_envios, dentro_n, snap_n, fuera_n, snap):
    from datetime import datetime
    pend = [f for f in mz if not visitas.get(f["properties"]["id_unidad"])]
    visd = len(mz) - len(pend)
    ln_pend = sum(f["properties"].get("LN_manzana") or 0 for f in pend)
    secs_txt = ", ".join(str(s) for s in sorted(secciones))
    aviso = ""
    if sin_gps:
        c = Counter(sin_gps)
        quienes = " · ".join(f"{b}: {n}" for b, n in c.most_common(6))
        aviso = (f"<div class='aviso'><b>{len(sin_gps)} visitas sin GPS no se "
                 f"pudieron ubicar.</b> Este mapa marca dónde <i>no hay registro "
                 f"de visita</i>, no dónde no se ha trabajado: una manzana "
                 f"cubierta por un brigadista cuyo teléfono no registró posición "
                 f"aparece como pendiente.<br><span class='quienes'>{quienes}"
                 f"</span></div>")
    mz_sin_tocar = sum(c["mz"] for c in sin_tocar.values())
    cuarto = ((f"{ln_pend:,.0f}", "LN pendiente conocida",
               f"de {sum(f['properties'].get('LN_manzana') or 0 for f in mz):,.0f} con LN por manzana")
              if ln_pend >= 1 else
              (f"{mz_sin_tocar:,}", "Manzanas en colonias intactas",
               "bloques contiguos, listos para asignar"))
    kpis = [(f"{len(pend):,}", "Manzanas pendientes", f"de {len(mz):,} del territorio"),
            (f"{len(sin_tocar)}", "Colonias sin tocar", f"de {len(col)} en total"),
            (f"{visd:,}", "Manzanas con visita", f"{visd/len(mz)*100:.0f}% del territorio"),
            cuarto]
    kpis_html = "".join(
        f"<div class='kpi'><div class='v'>{v}</div><div class='l'>{l}</div>"
        f"<div class='c'>{c}</div></div>" for v, l, c in kpis)

    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cobertura del territorio · secciones {secs_txt}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:{_C['bg']};color:{_C['texto']};
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
 font-size:15px;line-height:1.5}}
.wrap{{max-width:980px;margin:0 auto;padding:28px 16px 60px}}
h1{{font-size:1.5rem;margin:0 0 4px;letter-spacing:-.01em}}
.sub{{color:{_C['tenue']};font-size:.9rem;margin-bottom:22px}}
h2{{font-size:1.1rem;margin:34px 0 12px;padding-bottom:7px;
 border-bottom:1px solid {_C['borde']}}}
h3{{font-size:.95rem;margin:24px 0 8px;color:{_C['texto']}}}
.cuenta{{background:{_C['panel']};color:{_C['tenue']};border-radius:10px;
 padding:1px 8px;font-size:.78rem;font-weight:500;margin-left:5px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:11px}}
.kpi{{background:{_C['panel']};border:1px solid {_C['borde']};border-radius:9px;
 padding:14px 16px}}
.kpi .v{{font-size:1.7rem;font-weight:700;letter-spacing:-.02em}}
.kpi .l{{font-size:.82rem;color:{_C['tenue']};margin-top:2px}}
.kpi .c{{font-size:.74rem;color:{_C['mudo']};margin-top:4px}}
.mapa{{background:{_C['panel']};border:1px solid {_C['borde']};border-radius:9px;
 padding:14px;margin-top:14px}}
.leyenda{{display:flex;gap:20px;flex-wrap:wrap;margin-top:12px;font-size:.84rem;
 color:{_C['tenue']}}}
.leyenda i{{width:13px;height:13px;border-radius:3px;display:inline-block;
 vertical-align:-2px;margin-right:6px}}
table{{width:100%;border-collapse:collapse;font-size:.87rem;margin-bottom:6px}}
th{{text-align:left;color:{_C['mudo']};font-weight:600;font-size:.76rem;
 text-transform:uppercase;letter-spacing:.04em;padding:7px 9px;
 border-bottom:1px solid {_C['borde']}}}
td{{padding:7px 9px;border-bottom:1px solid rgba(255,255,255,.05)}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}
td.s,th.s{{color:{_C['mudo']};font-size:.82rem}}
.aviso{{background:rgba(232,163,61,.10);border:1px solid rgba(232,163,61,.35);
 border-left-width:3px;border-radius:7px;padding:13px 15px;margin:18px 0;
 font-size:.87rem}}
.quienes{{color:{_C['tenue']};font-size:.82rem}}
.nota{{color:{_C['mudo']};font-size:.82rem;margin:4px 0 8px}}
.pie{{color:{_C['mudo']};font-size:.78rem;margin-top:34px;
 border-top:1px solid {_C['borde']};padding-top:14px}}
path:hover{{fill-opacity:.95}}
</style></head><body><div class="wrap">
<h1>Cobertura del territorio</h1>
<div class="sub">Secciones {secs_txt} · generado {datetime.now():%d/%m/%Y %H:%M}</div>
<div class="kpis">{kpis_html}</div>
{aviso}
<h2>Dónde falta</h2>
<div class="mapa">{_svg(mz, visitas, refs_geom)}
<div class="leyenda">
 <span><i style="background:{_C['ambar']}"></i>Sin visita registrada</span>
 <span><i style="background:{_C['acero']};opacity:.5"></i>Con visita</span>
 <span><i style="background:transparent;border:1.5px solid {_C['acero']}"></i>Contorno de sección</span>
</div></div>
<h2>Por colonia</h2>
{_tabla(sin_tocar, "Sin tocar", "Ninguna manzana con visita registrada.")}
{_tabla(parciales, "A medias", "Empezadas pero incompletas.")}
{_tabla(completas, "Terminadas")}
<div class="pie">
{n_envios:,} visitas consultadas · {dentro_n:,} ubicadas dentro de una manzana ·
{snap_n:,} asignadas por cercanía (hasta {snap:.0f} m) · {fuera_n:,} sin manzana cerca ·
{len(sin_gps):,} sin GPS.<br>
Las manzanas del bloque reseccionado no tienen lista nominal asignada: sus
electores viven a nivel sección. Por eso aparecen como «s/d».<br>
PIE Atlixco · operativo de inducción 2026.
</div></div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--secciones", default="160,161,162",
                    help="separadas por coma; por default el territorio de la 160 vieja")
    ap.add_argument("--manzanas", default=MANZANAS)
    ap.add_argument("--contornos", default=CONTORNOS)
    ap.add_argument("--salida", default="manzanas_pendientes.kml")
    ap.add_argument("--html", default="cobertura_zona.html",
                    help="reporte HTML autocontenido; '' lo desactiva")
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
    rescatadas = 0
    for raw in envios:
        crudo = kc._get(raw, "gps")
        respaldo = raw.get("_geolocation")
        if isinstance(crudo, str) and not crudo.strip():
            crudo = None
            if isinstance(respaldo, (tuple, list)) and len(respaldo) >= 2 \
                    and respaldo[0] is not None:
                rescatadas += 1
        lat, lon, _p = kc._gps(crudo, respaldo)
        brig = str(raw.get("brigadista") or "?")
        if lat is None:
            sin_gps.append(brig)
        else:
            puntos.append((lat, lon, brig,
                           str(raw.get("inicio") or "")[:10]))
    print(f"Visitas: {len(envios)}  ·  con GPS {len(puntos)}  ·  sin GPS {len(sin_gps)}")
    if rescatadas:
        print(f"  ({rescatadas} recuperadas de _geolocation; el conector las "
              f"habria descartado)")

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

    # ── corte por colonia ───────────────────────────────────────────────────
    # Es como razona el coordinador: no manda brigadas a "la manzana 47", las
    # manda a una colonia. Una colonia puede abarcar varias secciones.
    col = defaultdict(lambda: {"mz": 0, "vis": 0, "ln": 0.0, "ln_vis": 0.0,
                               "secs": set(), "tipo": "", "visitas": 0})
    for f in mz:
        p = f["properties"]
        nombre = p.get("nav_nombre") or "sin colonia asignada"
        c = col[nombre]
        c["mz"] += 1
        c["ln"] += p.get("LN_manzana") or 0
        c["secs"].add(p["seccion"])
        c["tipo"] = p.get("nav_tipo") or ""
        vs = visitas.get(p["id_unidad"])
        if vs:
            c["vis"] += 1
            c["ln_vis"] += p.get("LN_manzana") or 0
            c["visitas"] += len(vs)

    sin_tocar = {k: v for k, v in col.items() if v["vis"] == 0}
    parciales = {k: v for k, v in col.items() if 0 < v["vis"] < v["mz"]}
    completas = {k: v for k, v in col.items() if v["vis"] == v["mz"]}

    print(f"\n{'='*62}")
    print(f"POR COLONIA — {len(col)} unidades de navegación")
    print(f"{'='*62}")

    def _bloque(titulo, grupo, mostrar_avance):
        if not grupo:
            return
        print(f"\n{titulo} ({len(grupo)})")
        anchos = f"{'colonia / localidad':<40}{'mz':>5}{'faltan':>8}{'LN pend.':>10}  secciones"
        print(f"  {anchos}")
        for n, c in sorted(grupo.items(), key=lambda kv: -(kv[1]["mz"] - kv[1]["vis"])):
            faltan = c["mz"] - c["vis"]
            ln_p = c["ln"] - c["ln_vis"]
            ln_txt = f"{ln_p:,.0f}" if c["ln"] else "s/d"
            print(f"  {n[:39]:<40}{c['mz']:>5}{faltan:>8}{ln_txt:>10}  "
                  f"{sorted(c['secs'])}")

    _bloque("SIN TOCAR — ninguna manzana con visita registrada", sin_tocar, False)
    _bloque("A MEDIAS — empezadas pero incompletas", parciales, True)
    if completas:
        print(f"\nTERMINADAS ({len(completas)})")
        for n, c in sorted(completas.items(), key=lambda kv: -kv[1]["mz"]):
            print(f"  {n[:39]:<40}{c['mz']:>5} manzanas · {c['visitas']} visitas")

    sin_ln = sum(1 for c in col.values() if not c["ln"])
    if sin_ln:
        print(f"\n  's/d' en {sin_ln} colonias: sus manzanas no tienen LN asignada.")
        print("  Son las del bloque 160R — sus electores viven a nivel sección,")
        print("  no de manzana, por la regla del reseccionamiento.")

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
    for f in sorted(pendientes, key=lambda x: (x["properties"].get("nav_nombre") or "",
                                               x["properties"]["manzana"])):
        p = f["properties"]
        ln = p.get("LN_manzana")
        # La colonia va primero: es como el coordinador lee el mapa, y hace
        # que las manzanas de una misma colonia queden juntas en la lista.
        etiqueta = f"{p.get('nav_nombre') or 'sin colonia'} · Mz {p['manzana']}"
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

    if args.html:
        refs_geom = []
        try:
            with open(args.contornos, encoding="utf-8") as fh:
                cont = json.load(fh)
            refs_geom = [f["geometry"] for f in cont["features"]
                         if f["properties"].get("seccion_geom") in secciones]
        except FileNotFoundError:
            pass
        html_doc = _reporte_html(mz, visitas, col, sin_tocar, parciales, completas,
                                 refs_geom, secciones, sin_gps, len(envios),
                                 dentro_n, snap_n, fuera_n, args.snap)
        Path(args.html).write_text(html_doc, encoding="utf-8")
        print(f"HTML escrito: {args.html} ({len(html_doc)/1024:.0f} KB)")
        print("Se abre en cualquier navegador y se puede compartir como archivo.")


if __name__ == "__main__":
    main()
