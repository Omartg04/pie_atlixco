"""Geometría de secciones sin dependencias — PIE Atlixco.

Punto en polígono por ray casting. Se usa desde app_utils (para la regla de
corrección por GPS) y desde verificar_secciones.py (para auditarla). Vive
aparte para no duplicar el algoritmo y para no arrastrar streamlit al script
de línea de comandos.

No requiere shapely ni geopandas: son 40 líneas y evitan sumar una dependencia
pesada a un despliegue que ya es frágil.
"""
from __future__ import annotations

import json


def anillos(geom: dict) -> list:
    """Anillos exteriores de un Polygon o MultiPolygon."""
    if geom.get("type") == "Polygon":
        return [geom["coordinates"][0]]
    if geom.get("type") == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []


def bbox(rings: list) -> tuple:
    xs = [x for a in rings for x, _ in a]
    ys = [y for a in rings for _, y in a]
    return min(xs), min(ys), max(xs), max(ys)


def area(rings: list) -> float:
    """Área por la fórmula del cordón, en grados cuadrados. Sirve para comparar
    tamaños relativos entre polígonos, no para medir superficie real."""
    total = 0.0
    for a in rings:
        s = 0.0
        for i in range(len(a)):
            x1, y1 = a[i][0], a[i][1]
            x2, y2 = a[(i + 1) % len(a)][0], a[(i + 1) % len(a)][1]
            s += x1 * y2 - x2 * y1
        total += abs(s) / 2
    return total


def dentro(lon: float, lat: float, ring: list) -> bool:
    """Ray casting sobre un anillo de [(lon, lat), ...]."""
    adentro = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            corte = xi + (lat - yi) * (xj - xi) / (yj - yi)
            if lon < corte:
                adentro = not adentro
        j = i
    return adentro


def cargar_poligonos(ruta: str) -> dict:
    """{sección: (bbox, anillos, área)} ordenado de MENOR a MAYOR área.

    El orden es la parte que importa. Los contornos vienen de la cartografía
    anterior al reseccionamiento, y el polígono de la 160 contiene por completo
    a la 161 y a la 162: un punto en la 162 cae también dentro de la 160. La
    búsqueda tiene que devolver el polígono más específico, no el primero.

    Verificado: 161 y 162 no se traslapan entre sí, y con este orden cada una
    resuelve a sí misma en 300 de 300 puntos interiores de prueba.
    """
    with open(ruta, encoding="utf-8") as fh:
        gj = json.load(fh)
    out = {}
    for f in gj.get("features", []):
        sec = f.get("properties", {}).get("seccion_geom")
        rings = anillos(f.get("geometry") or {})
        if sec is None or not rings:
            continue
        out[int(sec)] = (bbox(rings), rings, area(rings))
    return dict(sorted(out.items(), key=lambda kv: kv[1][2]))


def seccion_de_punto(lat, lon, polis: dict):
    """Sección más específica que contiene el punto, o None si ninguna."""
    if lat is None or lon is None:
        return None
    for sec, (bb, rings, _a) in polis.items():
        if not (bb[0] <= lon <= bb[2] and bb[1] <= lat <= bb[3]):
            continue
        if any(dentro(lon, lat, r) for r in rings):
            return sec
    return None


def contenedores_de_punto(lat, lon, polis: dict) -> list:
    """Todas las secciones que contienen el punto, de menor a mayor área.
    Para auditar los casos ambiguos."""
    if lat is None or lon is None:
        return []
    out = []
    for sec, (bb, rings, _a) in polis.items():
        if not (bb[0] <= lon <= bb[2] and bb[1] <= lat <= bb[3]):
            continue
        if any(dentro(lon, lat, r) for r in rings):
            out.append(sec)
    return out


# ── Distancia al borde, para distinguir ruido de frontera ───────────────────
# Un punto declarado en la 162 que resuelve a la 160 puede ser una visita real
# al territorio del bloque 160R, o un punto a 15 m del borde con una precisión
# de GPS de 12 m. La diferencia importa: reasignarlo mueve cobertura de una
# sección a otra. Esto mide cuánto se alejó del polígono que declaró.

_M_POR_GRADO_LAT = 111_320.0


def _dist_a_segmento_m(lat, lon, p1, p2) -> float:
    """Distancia en metros de un punto a un segmento, en proyección plana
    local. A escala de una sección electoral el error de la aproximación es
    despreciable frente a la precisión del GPS."""
    import math
    k = math.cos(math.radians(lat))
    px, py = lon * k * _M_POR_GRADO_LAT, lat * _M_POR_GRADO_LAT
    ax, ay = p1[0] * k * _M_POR_GRADO_LAT, p1[1] * _M_POR_GRADO_LAT
    bx, by = p2[0] * k * _M_POR_GRADO_LAT, p2[1] * _M_POR_GRADO_LAT
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distancia_al_borde_m(lat, lon, sec: int, polis: dict) -> float | None:
    """Metros del punto al borde del polígono de `sec`. None si no existe."""
    if lat is None or lon is None or sec not in polis:
        return None
    _bb, rings, _a = polis[sec]
    mejor = None
    for r in rings:
        for i in range(len(r)):
            d = _dist_a_segmento_m(lat, lon, r[i], r[(i + 1) % len(r)])
            if mejor is None or d < mejor:
                mejor = d
    return mejor
