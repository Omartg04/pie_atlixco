"""
generar_reporte_cierre.py — PIE Atlixco

Reporte ejecutivo de cierre enfocado en las 16 secciones prioritarias
(15 IRE + sección 160 por urgencia operativa).

Estructura:
  1. Header — fecha/hora corte, días restantes
  2. KPIs globales — todo el operativo
  3. 16 secciones de cierre — tabla activa + pendientes
  4. Resultados mínimos — comparativa todas vs. 16 prioritarias

Uso:
    python generar_reporte_cierre.py

Salida:
    reportes/reporte_cierre_AAAAMMDD_HHMM.html
"""

import json
import os
import sys
from datetime import date, datetime, timezone

import pandas as pd

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bubble_connector import (
    _fetch_all_raw, _transform,
    ANCLA_OPERATIVO, HABITANTES_PROMEDIO_VIVIENDA,
    ahora_mexico,
)

# ── Rutas ────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
REPORTES_DIR = os.path.join(BASE_DIR, "reportes")

# ── Exclusiones ──────────────────────────────────────────────────────────────
NOMBRES_EXCLUIDOS = {"omar téllez", "omar tellez"}

# ── Fecha de cierre del operativo (último día de campo) ──────────────────────
FECHA_CIERRE_OPERATIVO = date(2026, 8, 31)   # ajustar si cambia

# ── Paleta ───────────────────────────────────────────────────────────────────
C = {
    "bg":          "#14181f",
    "bg_card":     "#1b212b",
    "bg_card2":    "#202836",
    "border":      "rgba(255,255,255,.08)",
    "text":        "#eef1f0",
    "text2":       "#8b95a8",
    "muted":       "#5e6779",
    "amber":       "#e8a33d",
    "green":       "#3f7a52",
    "red":         "#c4703f",
}

# ── 16 secciones prioritarias de cierre ──────────────────────────────────────
# prob: de cada 100 simulaciones IRE (julio 2026)
# ln:   Lista Nominal disponible según IRE CSV
# accion: REGRESO / NUEVA / URGENTE
# alerta: True = sección 160, reseccionada, alerta operativa
SECCIONES_CIERRE = {
    208: {"prob": 100, "accion": "REGRESO", "ln": 4_866, "alerta": False},
    174: {"prob":  97, "accion": "NUEVA",   "ln": 3_636, "alerta": False},
    201: {"prob":  93, "accion": "NUEVA",   "ln": 3_021, "alerta": False},
    164: {"prob":  92, "accion": "NUEVA",   "ln": 2_933, "alerta": False},
    212: {"prob":  90, "accion": "REGRESO", "ln": 2_759, "alerta": False},
    169: {"prob":  90, "accion": "REGRESO", "ln": 2_753, "alerta": False},
    186: {"prob":  86, "accion": "REGRESO", "ln": 2_464, "alerta": False},
    216: {"prob":  85, "accion": "NUEVA",   "ln": 2_380, "alerta": False},
    159: {"prob":  85, "accion": "NUEVA",   "ln": 2_335, "alerta": False},
    202: {"prob":  84, "accion": "REGRESO", "ln": 2_308, "alerta": False},
    154: {"prob":  84, "accion": "NUEVA",   "ln": 2_293, "alerta": False},
    170: {"prob":  82, "accion": "NUEVA",   "ln": 2_156, "alerta": False},
    207: {"prob":  82, "accion": "NUEVA",   "ln": 2_156, "alerta": False},
    185: {"prob":  82, "accion": "REGRESO", "ln": 2_137, "alerta": False},
    213: {"prob":  80, "accion": "NUEVA",   "ln": 2_067, "alerta": False},
    # Sección 160 — urgencia doble: alto LN + alerta operativa
    160: {"prob":  None, "accion": "URGENTE", "ln": 5_939, "alerta": True},
}

SECS_CIERRE_SET = set(SECCIONES_CIERRE.keys())


# ── Helpers HTML ─────────────────────────────────────────────────────────────

def kpi(valor: str, label: str, ctx: str = "") -> str:
    return f"""
    <div style="background:{C['bg_card']}; border:1px solid {C['border']};
                border-left:3px solid {C['amber']}; border-radius:0 8px 8px 0;
                padding:14px 16px;">
      <div style="font-family:monospace; font-size:26px; font-weight:700;
                  color:{C['text']};">{valor}</div>
      <div style="font-size:13px; font-weight:600; color:{C['text']};
                  margin-top:4px;">{label}</div>
      <div style="font-size:12px; color:{C['muted']}; margin-top:2px;">{ctx}</div>
    </div>"""


def semaforo(pct: float | None, encuestas: int) -> str:
    if encuestas == 0:
        return "🔴"
    if pct is None or pct < 25:
        return "🟡"
    return "🟢"


def badge_accion(accion: str) -> str:
    colores = {
        "REGRESO":  ("#e8a33d", "#14181f"),
        "NUEVA":    ("#5b7a9e", "#eef1f0"),
        "URGENTE":  ("#c4703f", "#eef1f0"),
    }
    bg, fg = colores.get(accion, ("#5e6779", "#eef1f0"))
    return (f'<span style="background:{bg}; color:{fg}; font-size:10px; '
            f'font-weight:700; padding:2px 7px; border-radius:4px; '
            f'letter-spacing:.05em;">{accion}</span>')


def pct_fmt(v: float | None) -> str:
    return f"{v:.1f}%" if v is not None else "—"


def barra_resultado(etiqueta: str, pct_todas: float, pct_cierre: float) -> str:
    def segmento(pct: float, color: str) -> str:
        return (f'<div style="background:{color}; height:100%; '
                f'width:{pct:.1f}%; border-radius:3px;"></div>')

    return f"""
    <tr>
      <td style="padding:8px 12px; color:{C['text2']}; font-size:13px;
                 border-bottom:1px solid {C['border']};">{etiqueta}</td>
      <td style="padding:8px 12px; border-bottom:1px solid {C['border']};">
        <div style="display:flex; align-items:center; gap:8px;">
          <div style="flex:1; background:{C['bg_card2']}; border-radius:3px;
                      height:8px; overflow:hidden;">
            {segmento(pct_todas, C['amber'])}
          </div>
          <span style="font-family:monospace; font-size:13px;
                       color:{C['text']}; min-width:40px;">{pct_todas:.1f}%</span>
        </div>
      </td>
      <td style="padding:8px 12px; border-bottom:1px solid {C['border']};">
        <div style="display:flex; align-items:center; gap:8px;">
          <div style="flex:1; background:{C['bg_card2']}; border-radius:3px;
                      height:8px; overflow:hidden;">
            {segmento(pct_cierre, C['green'])}
          </div>
          <span style="font-family:monospace; font-size:13px;
                       color:{C['text']}; min-width:40px;">{pct_cierre:.1f}%</span>
        </div>
      </td>
    </tr>"""



# ── Color del mapa (escala motivacional) ─────────────────────────────────────
# <5%/sin iniciar → rojo | 5–15% → terracota | 15–25% → ámbar | ≥25% → verde

def sem_color(pct, enc):
    if enc == 0 or pct is None or pct < 5:
        return "#c4423e"
    if pct < 15:
        return "#c4703f"
    if pct < 25:
        return "#e8a33d"
    return "#3f7a52"


def _cargar_geo():
    """Lee y proyecta el geojson de secciones UTM→WGS84. Devuelve (features, bbox) o (None, None)."""
    _candidatos = [
        os.path.join(BASE_DIR, "data", "atlixco_secciones_zonas.geojson"),
        os.path.join(BASE_DIR, "atlixco_secciones_zonas.geojson"),
        os.path.join(BASE_DIR, "Atlixco_Secciones_con_censo.geojson"),
    ]
    geo_path = next((r for r in _candidatos if os.path.exists(r)), None)
    if geo_path is None:
        print("⚠️  Geojson de secciones no encontrado — mapa omitido.")
        return None, None
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:32614", "EPSG:4326", always_xy=True)
    except ImportError:
        print("⚠️  pyproj no disponible — mapa omitido.")
        return None, None

    def _conv(coords):
        if isinstance(coords[0], (int, float)):
            lon, lat = transformer.transform(coords[0], coords[1])
            return (lon, lat)
        return [_conv(c) for c in coords]

    def _iter(coords):
        if isinstance(coords[0], (int, float)):
            yield coords
        else:
            for c in coords:
                yield from _iter(c)

    with open(geo_path, encoding="utf-8") as f:
        geo = json.load(f)

    features = []
    for feat in geo.get("features", []):
        props = feat.get("properties") or {}
        sec = (props.get("SECCION") or props.get("seccion")
               or props.get("SECCION_") or props.get("cve_sec"))
        if sec is None:
            continue
        geom = feat["geometry"]
        try:
            features.append({"sec": int(sec), "type": geom["type"],
                              "coords": _conv(geom["coordinates"])})
        except Exception as _e:
            pass

    all_lons, all_lats = [], []
    for f in features:
        for pt in _iter(f["coords"]):
            all_lons.append(pt[0]); all_lats.append(pt[1])

    if not all_lons:
        sample = (geo.get("features") or [{}])[0].get("properties") or {}
        print(f"⚠️  Ningún punto extraído. Campos disponibles: {list(sample.keys())[:8]}")
        return None, None

    bbox = {"min_lon": min(all_lons), "max_lon": max(all_lons),
            "min_lat": min(all_lats), "max_lat": max(all_lats)}
    return features, bbox


def bloque_mapa(conteo_dict):
    """Genera SVG puro del mapa de calor — sin D3, sin JS, sin CDN."""
    features, bbox = _cargar_geo()
    if features is None:
        return ""

    W, H, PAD = 860, 490, 14
    mn_lon = bbox["min_lon"]; mx_lon = bbox["max_lon"]
    mn_lat = bbox["min_lat"]; mx_lat = bbox["max_lat"]
    lon_sp = mx_lon - mn_lon; lat_sp = mx_lat - mn_lat

    def proj(pt):
        x = PAD + (pt[0] - mn_lon) / lon_sp * (W - 2 * PAD)
        y = PAD + (mx_lat - pt[1]) / lat_sp * (H - 2 * PAD)
        return (round(x, 1), round(y, 1))

    def ring_d(ring):
        pts = [proj(p) for p in ring]
        if not pts: return ""
        d = "M" + str(pts[0][0]) + "," + str(pts[0][1])
        for p in pts[1:]: d += "L" + str(p[0]) + "," + str(p[1])
        return d + "Z"

    def coords_d(coords, geom_type):
        if geom_type == "Polygon":
            return " ".join(ring_d(r) for r in coords)
        elif geom_type == "MultiPolygon":
            return " ".join(ring_d(r) for poly in coords for r in poly)
        return ""

    def centroid_ring(ring):
        pts = [proj(p) for p in ring]
        if not pts: return None
        return (round(sum(p[0] for p in pts) / len(pts), 1),
                round(sum(p[1] for p in pts) / len(pts), 1))

    def first_ring(coords, geom_type):
        if geom_type == "Polygon": return coords[0] if coords else []
        elif geom_type == "MultiPolygon":
            best = max(coords, key=lambda poly: len(poly[0]) if poly else 0)
            return best[0] if best else []
        return []

    paths_bg, paths_pri, labels = [], [], []
    for f in features:
        sec = f["sec"]; d = coords_d(f["coords"], f["type"])
        if not d: continue
        if sec in SECS_CIERRE_SET:
            cd = conteo_dict.get(sec, {"enc": 0, "pct": 0.0})
            fill = sem_color(cd["pct"], cd["enc"])
            paths_pri.append(f'<path d="{d}" fill="{fill}" fill-opacity="0.9" '
                             f'stroke="#14181f" stroke-width="1"/>')
            ring = first_ring(f["coords"], f["type"])
            if ring:
                cx, cy = centroid_ring(ring) or (0, 0)
                labels.append(f'<text x="{cx}" y="{cy}" text-anchor="middle" '
                               f'dominant-baseline="middle" font-size="9" '
                               f'font-weight="600" fill="#ffffff" '
                               f'font-family="sans-serif">{sec}</text>')
        else:
            paths_bg.append(f'<path d="{d}" fill="#2a3140" stroke="#3a4455" stroke-width="0.4"/>')

    svg_inner = "\n".join(paths_bg + paths_pri + labels)

    leyenda = [("#3f7a52","≥25% — objetivo"),("#e8a33d","15–24%"),
               ("#c4703f","5–14%"),("#c4423e","&lt;5% o sin iniciar"),
               ("#2a3140","Otras secciones")]
    leyenda_html = " ".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'font-size:11px;color:{C["text2"]};margin-right:10px;">'
        f'<span style="width:12px;height:12px;border-radius:3px;'
        f'background:{col};display:inline-block;flex-shrink:0;"></span>{label}</span>'
        for col, label in leyenda)

    return f"""
  <h2 style="color:{C['text']}; font-size:16px; margin:0 0 10px;
             text-transform:uppercase; letter-spacing:.05em; font-weight:700;">
    Mapa de cobertura — 16 secciones
  </h2>
  <div style="background:{C['bg_card']}; border:1px solid {C['border']};
              border-radius:8px; padding:16px 16px 12px; margin-bottom:20px;">
    <svg xmlns="http://www.w3.org/2000/svg"
         viewBox="0 0 {W} {H}" width="{W}" height="{H}"
         style="width:100%;height:auto;display:block;max-width:{W}px;">
      {svg_inner}
    </svg>
    <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:4px 0;">
      {leyenda_html}
    </div>
  </div>"""

# ── Carga de credenciales ─────────────────────────────────────────────────────

def leer_private_key() -> str:
    ruta = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    if not os.path.exists(ruta):
        sys.exit(f"❌ No se encontró {ruta}.")
    with open(ruta, "rb") as f:
        secrets = tomllib.load(f)
    key = secrets.get("bubble", {}).get("private_key")
    if not key:
        sys.exit("❌ No se encontró [bubble] private_key en secrets.toml.")
    return key


# ── Cálculo de métricas de resultado ─────────────────────────────────────────

def pct_si(serie: pd.Series, valor_positivo: str) -> float:
    validos = serie.dropna()
    if len(validos) == 0:
        return 0.0
    return (validos == valor_positivo).sum() / len(validos) * 100


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("→ Leyendo credenciales...")
    private_key = leer_private_key()

    print("→ Consultando Bubble API...")
    raw = _fetch_all_raw(private_key)
    df  = _transform(raw)

    print("→ Aplicando filtros del operativo...")
    df = df[
        (df["fecha_creacion"] >= ANCLA_OPERATIVO)
        & (~df["nombre_encuestador"].str.strip().str.lower().isin(NOMBRES_EXCLUIDOS))
    ].copy()

    if df.empty:
        sys.exit("❌ Sin encuestas en el operativo. No se generó reporte.")

    # Normalizar sección a entero
    df["sec_int"] = pd.to_numeric(df["seccion_electoral"], errors="coerce").astype("Int64")

    ahora    = ahora_mexico()
    hoy      = ahora.date()
    df["dia"] = df["fecha_creacion"].dt.date

    # ── Días restantes ────────────────────────────────────────────────────────
    dias_restantes = (FECHA_CIERRE_OPERATIVO - hoy).days
    dias_restantes = max(dias_restantes, 0)

    # ── KPIs globales (todo el operativo) ────────────────────────────────────
    total_enc       = len(df)
    enc_hoy         = (df["dia"] == hoy).sum()
    secs_cubiertas  = df["sec_int"].nunique()
    encuestadores   = df["nombre_encuestador"].nunique()

    # Sección con más encuestas hoy (para la KPI card)
    df_hoy = df[df["dia"] == hoy]
    if not df_hoy.empty:
        sec_hoy_counts = df_hoy.groupby("sec_int")["sec_int"].count()
        sec_hoy = int(sec_hoy_counts.idxmax())
        sec_hoy_ctx = f"Sec. {sec_hoy} · {hoy.strftime('%d/%m/%Y')}"
    else:
        sec_hoy_ctx = hoy.strftime("%d/%m/%Y")

    # Sección con más encuestas hoy (para mostrar en la KPI card)
    df_hoy = df[df["dia"] == hoy]
    if not df_hoy.empty:
        sec_hoy_counts = df_hoy.groupby("sec_int")["sec_int"].count()
        sec_hoy = int(sec_hoy_counts.idxmax())
        sec_hoy_ctx = f"Sec. {sec_hoy} · {hoy.strftime('%d/%m/%Y')}"
    else:
        sec_hoy_ctx = hoy.strftime("%d/%m/%Y")

    kpis_html = "".join([
        kpi(f"{total_enc:,}", "Encuestas capturadas",
            "Acumulado desde el 18 jul 2026"),
        kpi(f"{enc_hoy:,}", "Encuestas de hoy",
            sec_hoy_ctx),
        kpi(f"{secs_cubiertas}", "Secciones con cobertura",
            "Con al menos 1 encuesta"),
        kpi(f"{encuestadores}", "Encuestadores activos",
            "En todo el operativo"),
    ])

    # ── Conteo por sección ────────────────────────────────────────────────────
    conteo = df.groupby("sec_int").agg(
        encuestas=("sec_int", "count"),
        enc_hoy=("dia", lambda x: (x == hoy).sum()),
    ).reset_index()
    conteo.columns = ["sec_int", "encuestas", "enc_hoy"]

    # ── Mapa de calor ─────────────────────────────────────────────────────────
    print("→ Preparando datos del mapa...")
    conteo_dict = {}
    for sec, meta in SECCIONES_CIERRE.items():
        fila = conteo[conteo["sec_int"] == sec]
        if fila.empty:
            conteo_dict[sec] = {"enc": 0, "pct": 0.0}
        else:
            enc_sec = int(fila["encuestas"].iloc[0])
            ln_proy = enc_sec * HABITANTES_PROMEDIO_VIVIENDA
            pct_sec = (ln_proy / meta["ln"] * 100) if meta["ln"] > 0 else 0.0
            conteo_dict[sec] = {"enc": enc_sec, "pct": pct_sec}
    mapa_html = bloque_mapa(conteo_dict)

    # ── Tabla activa de las 16 secciones ─────────────────────────────────────
    filas_activas = []
    pendientes    = []

    # Orden: sección 160 primero (urgencia), luego por probabilidad desc
    orden = [160] + [s for s in sorted(
        SECCIONES_CIERRE, key=lambda s: SECCIONES_CIERRE[s]["prob"] or 0, reverse=True
    ) if s != 160]

    for sec in orden:
        meta = SECCIONES_CIERRE[sec]
        fila_conteo = conteo[conteo["sec_int"] == sec]

        if fila_conteo.empty:
            enc = 0
            delta = 0
        else:
            enc   = int(fila_conteo["encuestas"].iloc[0])
            delta = int(fila_conteo["enc_hoy"].iloc[0])

        if enc == 0:
            pendientes.append(sec)
            continue

        ln_disp = meta["ln"]
        ln_proy = round(enc * HABITANTES_PROMEDIO_VIVIENDA)
        pct     = (ln_proy / ln_disp * 100) if ln_disp > 0 else None
        sem     = semaforo(pct, enc)
        alerta  = " ⚠️" if meta["alerta"] else ""
        prob_txt = f"{meta['prob']}/100" if meta["prob"] is not None else "Urgente"

        delta_txt = (f'<span style="color:{C["amber"]}; font-weight:600;">+{delta}</span>'
                     if delta > 0 else "—")

        filas_activas.append(f"""
        <tr>
          <td style="padding:8px 12px; border-bottom:1px solid {C['border']};
                     color:{C['text']}; font-weight:600;">{sec}{alerta}</td>
          <td style="padding:8px 12px; border-bottom:1px solid {C['border']};
                     color:{C['text2']}; font-size:12px;">{prob_txt}</td>
          <td style="padding:8px 12px; border-bottom:1px solid {C['border']};">
            {badge_accion(meta['accion'])}</td>
          <td style="padding:8px 12px; border-bottom:1px solid {C['border']};
                     text-align:right; color:{C['text']};">{enc:,}</td>
          <td style="padding:8px 12px; border-bottom:1px solid {C['border']};
                     text-align:right; color:{C['text2']};">{ln_proy:,}</td>
          <td style="padding:8px 12px; border-bottom:1px solid {C['border']};
                     text-align:right; color:{C['text2']};">{ln_disp:,}</td>
          <td style="padding:8px 12px; border-bottom:1px solid {C['border']};
                     text-align:right; color:{C['text']}; font-weight:600;">{pct_fmt(pct)}</td>
          <td style="padding:8px 12px; border-bottom:1px solid {C['border']};
                     text-align:center;">{delta_txt}</td>
          <td style="padding:8px 12px; border-bottom:1px solid {C['border']};
                     text-align:center; font-size:18px;">{sem}</td>
        </tr>""")

    if filas_activas:
        tabla_activa_html = f"""
        <div style="overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; font-size:13px;">
          <thead>
            <tr style="font-size:11px; text-transform:uppercase;
                       color:{C['muted']}; text-align:left;">
              <th style="padding:8px 12px; border-bottom:2px solid {C['amber']};">Sección</th>
              <th style="padding:8px 12px; border-bottom:2px solid {C['amber']};">Prob.</th>
              <th style="padding:8px 12px; border-bottom:2px solid {C['amber']};">Acción</th>
              <th style="padding:8px 12px; border-bottom:2px solid {C['amber']};
                         text-align:right;">Encuestas</th>
              <th style="padding:8px 12px; border-bottom:2px solid {C['amber']};
                         text-align:right;">LN proy.</th>
              <th style="padding:8px 12px; border-bottom:2px solid {C['amber']};
                         text-align:right;">LN IRE</th>
              <th style="padding:8px 12px; border-bottom:2px solid {C['amber']};
                         text-align:right;">% LN</th>
              <th style="padding:8px 12px; border-bottom:2px solid {C['amber']};
                         text-align:center;">Δ hoy</th>
              <th style="padding:8px 12px; border-bottom:2px solid {C['amber']};
                         text-align:center;">Estado</th>
            </tr>
          </thead>
          <tbody>{''.join(filas_activas)}</tbody>
        </table>
        </div>"""
    else:
        tabla_activa_html = (f'<p style="font-size:13px; color:{C["muted"]}; padding:12px 0;">'
                             "Aún no hay encuestas capturadas en ninguna de las 16 secciones.</p>")

    # ── Lista de pendientes ───────────────────────────────────────────────────
    if pendientes:
        items_pend = " · ".join(
            f'<span style="color:{C["amber"]}; font-weight:600;">{s}</span>'
            for s in pendientes
        )
        pendientes_html = f"""
        <div style="margin-top:16px; padding:12px 16px;
                    background:{C['bg_card2']}; border-radius:8px;
                    border:1px solid {C['border']};">
          <span style="font-size:12px; text-transform:uppercase;
                       letter-spacing:.07em; color:{C['muted']};">
            Sin iniciar ({len(pendientes)})&nbsp;&nbsp;
          </span>
          {items_pend}
        </div>"""
    else:
        pendientes_html = (f'<div style="margin-top:12px; font-size:13px; '
                           f'color:{C["green"]}; font-weight:600;">'
                           "✅ Las 16 secciones tienen al menos una encuesta.</div>")

    # ── Resultados mínimos — comparativa ─────────────────────────────────────
    df_cierre = df[df["sec_int"].isin(SECS_CIERRE_SET)].copy()

    metricas = [
        ("Reconocimiento",       "conocimiento_arturo",    "Sí"),
        ("Buena candidatura",    "buena_candidatura_arturo", "Sí"),
        ("Disposición a votar",  "votar_o_no_arturo",      "Votaría"),
    ]

    filas_resultado = ""
    for etiqueta, campo, valor_pos in metricas:
        if campo not in df.columns:
            continue
        pct_todas  = pct_si(df[campo], valor_pos)
        pct_cierre = pct_si(df_cierre[campo], valor_pos) if not df_cierre.empty else 0.0
        filas_resultado += barra_resultado(etiqueta, pct_todas, pct_cierre)

    n_todas  = len(df)
    n_cierre = len(df_cierre)

    tabla_resultados_html = f"""
    <table style="width:100%; border-collapse:collapse;">
      <thead>
        <tr style="font-size:11px; text-transform:uppercase; color:{C['muted']};">
          <th style="padding:8px 12px; border-bottom:2px solid {C['border']};
                     text-align:left; width:200px;">Indicador</th>
          <th style="padding:8px 12px; border-bottom:2px solid {C['border']};">
            <span style="display:inline-block; width:8px; height:8px; border-radius:2px;
                         background:{C['amber']}; margin-right:6px;"></span>
            Todo el operativo (n={n_todas:,})
          </th>
          <th style="padding:8px 12px; border-bottom:2px solid {C['border']};">
            <span style="display:inline-block; width:8px; height:8px; border-radius:2px;
                         background:{C['green']}; margin-right:6px;"></span>
            16 secciones clave (n={n_cierre:,})
          </th>
        </tr>
      </thead>
      <tbody>{filas_resultado}</tbody>
    </table>"""

    # ── Leyenda días restantes ────────────────────────────────────────────────
    if dias_restantes == 0:
        dias_txt = '<span style="color:#c4703f; font-weight:700;">Último día de campo</span>'
    elif dias_restantes == 1:
        dias_txt = '<span style="color:#e8a33d; font-weight:700;">1 día restante</span>'
    else:
        dias_txt = (f'<span style="color:{C["text2"]};">'
                    f'<b style="color:{C["text"]};">{dias_restantes}</b> días restantes</span>')

    # ── HTML final ────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PIE Atlixco — Reporte de cierre</title>
<style>
  * {{ -webkit-print-color-adjust:exact !important; print-color-adjust:exact !important; }}
  @media print {{ body {{ background:{C['bg']} !important; }} }}
</style>
</head>
<body style="margin:0; background:{C['bg']};
             font-family:-apple-system,Segoe UI,Arial,sans-serif;">
<div style="max-width:920px; margin:0 auto; padding:36px 24px;">

  <!-- Header -->
  <div style="font-family:monospace; font-size:11px; font-weight:700;
              letter-spacing:.1em; text-transform:uppercase;
              color:{C['amber']}; margin-bottom:8px;">
    PIE Atlixco · Arturo Solano Escobedo
  </div>
  <h1 style="color:{C['text']}; font-size:26px; margin:0 0 8px;">
    Reporte de cierre — 16 secciones prioritarias
  </h1>
  <p style="color:{C['text2']}; font-size:13px; margin:0 0 28px;">
    Generado el {ahora.strftime('%d/%m/%Y a las %H:%M')} hora México ·
    {dias_txt} · cierre estimado {FECHA_CIERRE_OPERATIVO.strftime('%d/%m/%Y')}
  </p>

  <!-- KPIs globales -->
  <h2 style="color:{C['text']}; font-size:16px; margin:0 0 10px;
             text-transform:uppercase; letter-spacing:.05em; font-weight:700;">
    Operativo general
  </h2>
  <div style="display:grid; grid-template-columns:repeat(4,1fr);
              gap:10px; margin-bottom:32px;">
    {kpis_html}
  </div>

  <!-- Mapa de cobertura -->
  {mapa_html}

  <!-- 16 secciones de cierre -->
  <h2 style="color:{C['text']}; font-size:16px; margin:0 0 6px;
             text-transform:uppercase; letter-spacing:.05em; font-weight:700;">
    16 secciones de cierre
  </h2>
  <p style="color:{C['muted']}; font-size:12px; margin:0 0 12px;">
    Semáforo: 🟢 ≥25% LN cubierta · 🟡 en progreso · 🔴 sin iniciar.
    ⚠️ Sección 160: referencia geográfica, reseccionada en INE jul 2026.
    LN proy. = encuestas × {HABITANTES_PROMEDIO_VIVIENDA} hab./vivienda (censo Atlixco).
  </p>
  <div style="background:{C['bg_card']}; border:1px solid {C['border']};
              border-radius:8px; padding:6px 0; margin-bottom:6px;">
    {tabla_activa_html}
  </div>
  {pendientes_html}

  <!-- Resultados mínimos -->
  <h2 style="color:{C['text']}; font-size:16px; margin:32px 0 6px;
             text-transform:uppercase; letter-spacing:.05em; font-weight:700;">
    Resultados preliminares
  </h2>
  <p style="color:{C['muted']}; font-size:12px; margin:0 0 12px;">
    Datos de campo no ponderados — referencia interna, no comparable con encuesta externa.
  </p>
  <div style="background:{C['bg_card']}; border:1px solid {C['border']};
              border-radius:8px; padding:6px 0; margin-bottom:12px;">
    {tabla_resultados_html}
  </div>

  <!-- Footer -->
  <div style="margin-top:32px; padding-top:12px;
              border-top:1px solid {C['border']};
              font-family:monospace; font-size:11px;
              color:{C['muted']}; letter-spacing:.03em;">
    PIE ATLIXCO · ARTURO SOLANO ESCOBEDO · PROCESO INTERNO MORENA 2026 · CONFIDENCIAL
  </div>

</div>
</body>
</html>"""

    os.makedirs(REPORTES_DIR, exist_ok=True)
    nombre = f"reporte_cierre_{ahora.strftime('%Y%m%d_%H%M')}.html"
    ruta   = os.path.join(REPORTES_DIR, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Reporte generado: {ruta}")


if __name__ == "__main__":
    main()