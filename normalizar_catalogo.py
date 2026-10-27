#!/usr/bin/env python3
"""Convierte las URLs de My Maps del catálogo a la forma /viewer.

    python3 normalizar_catalogo.py data/mapas_catalogo.csv

Reescribe el archivo en sitio y deja un respaldo .bak. El 'mid' es el mismo
identificador del mapa en las dos formas: solo cambia la ruta y se descartan
los parámetros de sesión (u/0) y de compartido (usp=sharing), que son los que
anclan el enlace a la cuenta de Google del dispositivo y lo abren en edición.

OJO: esto arregla la FORMA del enlace, no el permiso. Un mapa compartido como
"puede editar" sigue siendo editable aunque el enlace sea /viewer. El permiso
se cambia en My Maps o en Drive.
"""
import csv, re, shutil, sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

VIEWER = "https://www.google.com/maps/d/viewer?mid={}"
RE_MID = re.compile(r"[?&]mid=([A-Za-z0-9_-]+)")


def normalizar(url: str) -> tuple[str, str]:
    """Devuelve (url_normalizada, motivo). motivo vacío = no se tocó."""
    u = (url or "").strip()
    if not u:
        return "", ""
    if "/maps/d/" not in u:
        return u, "no parece un enlace de My Maps — revisar a mano"
    m = RE_MID.search(u)
    if not m:
        return u, "sin parámetro mid — revisar a mano"
    mid = m.group(1)
    nueva = VIEWER.format(mid)
    if nueva == u:
        return u, ""
    quitados = []
    if "/edit" in u:
        quitados.append("modo edición")
    if re.search(r"/d/u/\d+/", u):
        quitados.append("ancla de cuenta (u/N)")
    if "usp=" in parse_qs(urlparse(u).query) or "usp=" in u:
        quitados.append("usp=sharing")
    return nueva, "convertida" + (f" · se quitó {', '.join(quitados)}" if quitados else "")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__); return 2
    ruta = Path(sys.argv[1])
    if not ruta.exists():
        print(f"No existe: {ruta}"); return 1

    with ruta.open(encoding="utf-8", newline="") as fh:
        filas = list(csv.DictReader(fh))
        campos = list(filas[0].keys()) if filas else []

    if "url_my_maps_viewer" not in campos:
        print("El CSV no tiene la columna 'url_my_maps_viewer'."); return 1

    convertidas, revisar, intactas = [], [], 0
    for f in filas:
        nueva, motivo = normalizar(f["url_my_maps_viewer"])
        if motivo == "":
            intactas += 1
        elif motivo.startswith("convertida"):
            convertidas.append((f.get("seccion", "?"), motivo))
            f["url_my_maps_viewer"] = nueva
        else:
            revisar.append((f.get("seccion", "?"), motivo, f["url_my_maps_viewer"]))

    shutil.copy(ruta, ruta.with_suffix(ruta.suffix + ".bak"))
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos); w.writeheader(); w.writerows(filas)

    print(f"{ruta.name}: {len(convertidas)} convertidas · {intactas} sin cambio "
          f"(vacías o ya en /viewer) · {len(revisar)} para revisar a mano")
    print(f"Respaldo en {ruta.name}.bak")
    if convertidas:
        print("\nConvertidas:")
        for sec, motivo in convertidas:
            print(f"  sección {sec:>5} — {motivo}")
    if revisar:
        print("\nRevisar a mano:")
        for sec, motivo, url in revisar:
            print(f"  sección {sec:>5} — {motivo}\n           {url}")
    print("\nFalta el permiso: en My Maps cada mapa debe estar compartido como")
    print("'cualquier persona con el enlace' con rol de LECTOR, no de editor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
