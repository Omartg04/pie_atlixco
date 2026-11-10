#!/usr/bin/env python3
"""Verifica la sección declarada contra la ubicación real — PIE Atlixco.

Cuando una brigada se pasa a la sección de al lado y sigue capturando la
anterior, el GPS lo delata: el punto cae dentro del polígono de la sección en
la que de verdad estuvo.

Uso, desde la raíz del repo:

    python3 verificar_secciones.py                     todo el operativo
    python3 verificar_secciones.py --fecha 2026-11-04  un día
    python3 verificar_secciones.py --fecha 2026-11-04 --seccion 162

No imprime coordenadas: solo conteos, secciones y códigos de brigadista.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CONTORNOS = "data/m1_contornos.geojson"


from geo_secciones import (cargar_poligonos, contenedores_de_punto,
                           distancia_al_borde_m, seccion_de_punto)

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
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fecha", help="AAAA-MM-DD; omitido = todo el operativo")
    ap.add_argument("--seccion", type=int, help="solo las visitas declaradas así")
    args = ap.parse_args()

    import kobo_connector as kc

    cfg = leer_secrets()
    faltan = [k for k in ("base_url", "asset_uid", "api_token") if not cfg.get(k)]
    if faltan:
        sys.exit("Faltan en [kobo]: " + ", ".join(faltan))

    polis = cargar_poligonos(CONTORNOS)
    print(f"Polígonos cargados: {len(polis)} secciones")
    print("Consultando Kobo...")
    envios = kc.fetch_all(cfg["base_url"], cfg["asset_uid"], cfg["api_token"])

    filas = []
    for raw in envios:
        fecha = str(raw.get("inicio") or raw.get("start")
                    or raw.get("_submission_time") or "")[:10]
        if args.fecha and fecha != args.fecha:
            continue
        try:
            dec = int(float(str(kc._get(raw, "seccion_electoral")
                                or kc._get(raw, "seccion_declarada") or "")))
        except (TypeError, ValueError):
            continue
        if args.seccion is not None and dec != args.seccion:
            continue
        lat, lon, prec = kc._gps(kc._get(raw, "gps"), raw.get("_geolocation"))
        real = seccion_de_punto(lat, lon, polis)
        dist = (distancia_al_borde_m(lat, lon, dec, polis)
                if lat is not None and real is not None and real != dec else None)
        filas.append({"uuid": str(raw.get("_uuid") or raw.get("_id")),
                      "fecha": fecha, "declarada": dec, "real": real,
                      "brigadista": str(raw.get("brigadista") or "?"),
                      "con_gps": lat is not None, "precision": prec,
                      "dist_borde_m": dist})

    if not filas:
        print("\nNo hay visitas con esos filtros.")
        return

    ambito = (f"fecha {args.fecha}" if args.fecha else "todo el operativo")
    if args.seccion is not None:
        ambito += f", declaradas como {args.seccion}"
    print(f"\n{'='*66}\nVISITAS EN {ambito.upper()}: {len(filas)}\n{'='*66}")

    sin_gps = [f for f in filas if not f["con_gps"]]
    con_gps = [f for f in filas if f["con_gps"]]
    print(f"\ncon GPS {len(con_gps)}   ·   sin GPS {len(sin_gps)} "
          f"(no se pueden verificar)")

    # ── por sección declarada ───────────────────────────────────────────────
    print(f"\n{'declarada':>10}{'visitas':>9}{'coincide':>10}{'otra sección':>14}"
          f"{'fuera de todas':>16}{'sin GPS':>9}")
    por_dec = defaultdict(list)
    for f in filas:
        por_dec[f["declarada"]].append(f)
    discrepancias = defaultdict(Counter)
    for dec in sorted(por_dec):
        g = por_dec[dec]
        cg = [x for x in g if x["con_gps"]]
        coincide = sum(1 for x in cg if x["real"] == dec)
        fuera = sum(1 for x in cg if x["real"] is None)
        otra = len(cg) - coincide - fuera
        print(f"{dec:>10}{len(g):>9}{coincide:>10}{otra:>14}{fuera:>16}"
              f"{len(g)-len(cg):>9}")
        for x in cg:
            if x["real"] is not None and x["real"] != dec:
                discrepancias[dec][x["real"]] += 1

    # ── a dónde se fueron ───────────────────────────────────────────────────
    if discrepancias:
        print("\nA DÓNDE CAEN LAS QUE NO COINCIDEN")
        for dec in sorted(discrepancias):
            for real, n in discrepancias[dec].most_common():
                print(f"    declarada {dec}  →  realmente en {real}: {n} visitas")

        print("\n¿RUIDO DE FRONTERA O DESPLAZAMIENTO REAL?")
        print("    Distancia del punto al borde de la sección que declaró.")
        print("    Cerca del borde + precisión del GPS = puede ser ruido.")
        print(f"\n{'declarada':>10}{'real':>7}{'visitas':>9}{'<25 m':>8}"
              f"{'25-100 m':>10}{'>100 m':>8}{'mediana':>10}")
        agrup = defaultdict(list)
        for f in filas:
            if f["dist_borde_m"] is not None:
                agrup[(f["declarada"], f["real"])].append(f["dist_borde_m"])
        for (d, r), ds in sorted(agrup.items(), key=lambda kv: -len(kv[1])):
            ds_o = sorted(ds)
            med = ds_o[len(ds_o)//2]
            cerca = sum(1 for x in ds if x < 25)
            medio = sum(1 for x in ds if 25 <= x <= 100)
            lejos = sum(1 for x in ds if x > 100)
            print(f"{d:>10}{r:>7}{len(ds):>9}{cerca:>8}{medio:>10}{lejos:>8}"
                  f"{med:>9.0f} m")
        print("\n    Precisión reportada por el GPS en esas visitas: "
              f"mediana {sorted(x['precision'] for x in filas if x['precision'])[len([x for x in filas if x['precision']])//2]:.0f} m"
              if any(x["precision"] for x in filas) else "")

        print("\nPOR BRIGADISTA (solo las que no coinciden)")
        por_brig = defaultdict(Counter)
        for f in filas:
            if f["con_gps"] and f["real"] is not None and f["real"] != f["declarada"]:
                por_brig[f["brigadista"]][(f["declarada"], f["real"])] += 1
        for b in sorted(por_brig):
            detalle = "; ".join(f"{d}→{r}: {n}" for (d, r), n in por_brig[b].most_common())
            total_b = sum(1 for f in filas if f["brigadista"] == b)
            print(f"    {b}  {detalle}   (de {total_b} visitas suyas)")
    else:
        print("\nTodas las visitas con GPS caen dentro de la sección declarada.")

    if sin_gps:
        print("\nSIN GPS, POR BRIGADISTA — estas no se pueden verificar ni corregir")
        c = Counter(f["brigadista"] for f in sin_gps)
        for b, n in c.most_common():
            print(f"    {b}: {n}")

    print(f"\n{'='*66}")
    print("Para corregir por GPS, agrega a data/correcciones_seccion.csv:")
    for dec in sorted(discrepancias):
        f = args.fecha or ""
        print(f"    {f},{dec},gps,,reasignacion por ubicacion real")
    print("La palabra 'gps' en seccion_corregida reasigna cada visita al polígono")
    print("que la contiene. Las visitas sin GPS se quedan como fueron declaradas")
    print("y el módulo las reporta.")


if __name__ == "__main__":
    main()
