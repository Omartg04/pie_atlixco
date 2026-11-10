#!/usr/bin/env python3
"""Reporte de desempeño de un brigadista — PIE Atlixco.

Genera un HTML autocontenido con el desempeño de un brigadista desde la
jornada 1 del operativo de inducción: resumen contra la mediana del equipo,
producción jornada por jornada y secciones trabajadas. Pensado para entregar
al cliente: se abre en cualquier navegador y se guarda como PDF desde ahí.

Uso, desde cualquier carpeta (el script se ubica solo en la raíz del repo):

    python3 reporte_brigadista.py --lista
    python3 reporte_brigadista.py --brigadista B14
    python3 reporte_brigadista.py --brigadista "Alejandra Morales"
    python3 reporte_brigadista.py --brigadista B14 --hasta 2026-11-09

`--brigadista` acepta el código (B14, b14, 14) o el nombre, completo o en
parte, con o sin acentos. Si el nombre coincide con más de una persona, el
script muestra las opciones y no genera nada: nunca escoge por su cuenta.

Salida: reportes/brigadistas/desempeno_B14_AAAAMMDD_HHMM.html

Los números salen del mismo procesamiento que el tablero: recuperación de la
fecha desde `start`, rescate de GPS y reglas de data/correcciones_seccion.csv,
con las funciones de app_utils. Si el reporte y M3 dieran cifras distintas, la
primera comparación del cliente le quitaría crédito a los dos.

Lo que NO incluye, por decisión del 9/11/2026: la calidad del registro (GPS,
duraciones, rachas, incidencias). Eso es supervisión interna. Tampoco incluye
coordenadas, domicilios ni respuestas del cuestionario, ni nombres de otros
brigadistas: el equipo aparece solo como mediana.
"""
import argparse
import hashlib
import html
import json
import logging
import os
import sys
import unicodedata
from datetime import date, datetime
from statistics import median

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)                       # secrets.toml y data/ son relativos
sys.path.insert(0, BASE_DIR)

import pandas as pd  # noqa: E402

SALIDA_DIR = os.path.join(BASE_DIR, "reportes", "brigadistas")
REFERENCIA = 25                          # = META_POR_BRIGADISTA de app_utils
QUE_CUENTAN = ("completa", "parcial")    # entrevista = contacto real

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Paleta clara: el reporte se imprime y se reenvía como PDF, y un fondo oscuro
# en papel gasta tinta y se pierde si el navegador no imprime fondos. El ámbar
# es el acento de marca del proyecto.
C = {
    "tinta": "#1b212b", "tinta_2": "#4a5363", "tenue": "#7a8394",
    "borde": "#e2e5ea", "fondo_2": "#f6f7f9", "ambar": "#e8a33d",
    "ambar_osc": "#a8681f",
}


# ════════════════════════════════════════════════════════════════════════════
# DATOS
# ════════════════════════════════════════════════════════════════════════════

def leer_secrets() -> dict:
    ruta = os.path.join(".streamlit", "secrets.toml")
    if not os.path.exists(ruta):
        sys.exit(f"No encuentro {ruta} en {BASE_DIR}.")
    try:
        import tomllib
        with open(ruta, "rb") as fh:
            return tomllib.load(fh).get("kobo", {})
    except ModuleNotFoundError:
        cfg, bloque = {}, False
        for linea in open(ruta, encoding="utf-8").read().splitlines():
            t = linea.strip()
            if t.startswith("["):
                bloque = t == "[kobo]"
                continue
            if bloque and "=" in t:
                k, v = t.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
        return cfg


def _silenciar_streamlit() -> None:
    """app_utils importa streamlit; fuera de la app, su caché avisa en cada
    llamada que no hay runtime. Es ruido: aquí no se necesita caché.

    El orden importa: al leer su configuración, streamlit fija el nivel de sus
    loggers en INFO. Se fuerza esa lectura primero y después se baja el nivel;
    al revés, la lectura lo vuelve a subir."""
    try:
        from streamlit import config, logger
        config.get_config_options()
        logger.set_log_level("error")
    except Exception:
        logging.getLogger("streamlit").setLevel(logging.ERROR)


def cargar_visitas() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Visitas ya procesadas como en el tablero, más las reglas de corrección.

    Agrega `seccion_declarada_original`: la sección que el brigadista capturó,
    antes de las correcciones. Se guarda aquí, sin tocar app_utils, para poder
    decir en el reporte qué visitas se reasignaron y por qué.
    """
    cfg = leer_secrets()
    faltan = [k for k in ("base_url", "asset_uid", "api_token") if not cfg.get(k)]
    if faltan:
        sys.exit("Faltan en [kobo] de secrets.toml: " + ", ".join(faltan))

    _silenciar_streamlit()
    import kobo_connector as kc
    import app_utils as au

    print("Consultando Kobo...", file=sys.stderr)
    envios = kc.fetch_all(cfg["base_url"], cfg["asset_uid"], cfg["api_token"])
    au.normalizar_campos_tiempo(envios)
    au.rescatar_gps(envios)

    original = {}
    for raw in envios:
        uid = kc._str(raw.get("_uuid")) or kc._str(raw.get("_id"))
        rid = hashlib.sha256(uid.encode("utf-8")).hexdigest()[:20]  # = transform()
        original[rid] = kc._section(kc._get(raw, "seccion_electoral")
                                    or kc._get(raw, "seccion_declarada"))

    reglas = au.load_correcciones_seccion()
    envios, _ = au.aplicar_correcciones(envios, reglas)
    with open(os.path.join(BASE_DIR, "schema_xlsform_v06.json"), encoding="utf-8") as fh:
        schema = json.load(fh)
    datos = kc.transform(envios, schema)

    vis = pd.DataFrame(datos.get("visitas_operativas", []))
    if vis.empty:
        sys.exit("Kobo no devolvió visitas.")
    for c in ("brigadista", "brigadista_codigo", "fecha_visita",
              "seccion_operativa", "resultado", "entrega_volante"):
        vis[c] = vis[c].fillna("").astype(str).str.strip()
    vis["seccion_declarada_original"] = vis["registro_id"].map(original).fillna("")
    vis["entrevista"] = vis["resultado"].isin(QUE_CUENTAN)
    return vis, reglas


# ════════════════════════════════════════════════════════════════════════════
# QUIÉN
# ════════════════════════════════════════════════════════════════════════════

def _norm(txt: str) -> str:
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def brigadistas_en(vis: pd.DataFrame) -> pd.DataFrame:
    """Una fila por persona: (código, nombre). B99 agrupa a varias personas
    con nombres distintos, por eso la llave es el par y no solo el código."""
    con_codigo = vis[vis["brigadista_codigo"] != ""]
    return (con_codigo.groupby(["brigadista_codigo", "brigadista"], as_index=False)
            .agg(visitas=("registro_id", "count"))
            .sort_values(["brigadista_codigo", "brigadista"]))


def resolver(consulta: str, lista: pd.DataFrame) -> list[tuple[str, str]]:
    q = consulta.strip()
    qn = _norm(q)
    # Código: B14, b14 o 14.
    cod = q.upper() if q.upper().startswith("B") else f"B{q.zfill(2)}" if q.isdigit() else ""
    if cod:
        hits = lista[lista["brigadista_codigo"] == cod]
        if not hits.empty:
            return list(hits[["brigadista_codigo", "brigadista"]].itertuples(index=False, name=None))
    exactos = lista[lista["brigadista"].map(_norm) == qn]
    if not exactos.empty:
        return list(exactos[["brigadista_codigo", "brigadista"]].itertuples(index=False, name=None))
    # Todas las palabras de la consulta deben aparecer en el nombre.
    palabras = qn.split()
    parciales = lista[lista["brigadista"].map(
        lambda n: all(p in _norm(n) for p in palabras))]
    return list(parciales[["brigadista_codigo", "brigadista"]].itertuples(index=False, name=None))


# ════════════════════════════════════════════════════════════════════════════
# CÁLCULO
# ════════════════════════════════════════════════════════════════════════════

def indicadores(g: pd.DataFrame) -> dict:
    """Indicadores de una persona en el periodo. `g` son sus visitas fechadas."""
    visitas = len(g)
    jornadas = g["fecha_visita"].nunique()
    entrevistas = int(g["entrevista"].sum())
    entrego = int((g["entrega_volante"] == "entrego").sum())
    no_entrego = int((g["entrega_volante"] == "no_entrego").sum())
    return {
        "visitas": visitas,
        "jornadas": jornadas,
        "entrevistas": entrevistas,
        "por_jornada": entrevistas / jornadas if jornadas else None,
        "pct_entrevista": entrevistas / visitas * 100 if visitas else None,
        "volantes": entrego,
        "pct_volante": entrego / (entrego + no_entrego) * 100
        if (entrego + no_entrego) else None,
    }


def mediana_equipo(por_persona: list[dict], clave: str):
    vals = [p[clave] for p in por_persona if p[clave] is not None]
    return median(vals) if vals else None


# ════════════════════════════════════════════════════════════════════════════
# HTML
# ════════════════════════════════════════════════════════════════════════════

def _f(d: date) -> str:
    return d.strftime("%d/%m")


def _f_larga(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _num(x, dec=0) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{x:,.{dec}f}"


def grafica_svg(jd: pd.DataFrame) -> str:
    """Barras por jornada con eje ordinal, una sola serie y la referencia de 25.

    Lleva el número sobre cada barra porque en papel no hay tooltip. La jornada
    sin captura conserva su lugar y lo dice en texto: un hueco mudo se lee
    como cero.
    """
    W, H = 760, 280
    ml, mr, mt, mb = 44, 16, 18, 42
    pw, ph = W - ml - mr, H - mt - mb
    n = len(jd)
    vmax = max([REFERENCIA * 1.25] + [v * 1.15 for v in jd["entrevistas"].dropna()])
    paso = 5 if vmax <= 40 else 10 if vmax <= 80 else 20
    vmax = (int(vmax // paso) + 1) * paso
    y = lambda v: mt + ph - v / vmax * ph  # noqa: E731
    slot = pw / n
    bw = min(56, slot * 0.68)
    rot = n > 14

    p = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
         f'aria-label="Entrevistas por jornada" xmlns="http://www.w3.org/2000/svg" '
         f'style="font-family:inherit">']
    for v in range(0, vmax + 1, paso):
        p.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y(v):.1f}" y2="{y(v):.1f}" '
                 f'stroke="{C["borde"]}" stroke-width="1"/>')
        p.append(f'<text x="{ml - 8}" y="{y(v) + 4:.1f}" text-anchor="end" '
                 f'font-size="11" fill="{C["tenue"]}">{v}</text>')
    for i, r in enumerate(jd.itertuples()):
        cx = ml + slot * (i + 0.5)
        if r.con_captura:
            v = r.entrevistas
            p.append(f'<rect x="{cx - bw / 2:.1f}" y="{y(v):.1f}" width="{bw:.1f}" '
                     f'height="{max(0.0, y(0) - y(v)):.1f}" rx="3" fill="{C["ambar"]}"/>')
            p.append(f'<text x="{cx:.1f}" y="{y(v) - 6:.1f}" text-anchor="middle" '
                     f'font-size="12" font-weight="600" fill="{C["tinta"]}">{int(v)}</text>')
        else:
            p.append(f'<text transform="translate({cx:.1f},{y(0) - 8:.1f}) rotate(-90)" '
                     f'font-size="11" fill="{C["tenue"]}" dominant-baseline="middle">'
                     f'sin captura</text>')
        etiqueta = _f(r.fecha)
        if rot:
            p.append(f'<text transform="translate({cx:.1f},{y(0) + 14:.1f}) rotate(-45)" '
                     f'text-anchor="end" font-size="11" fill="{C["tinta_2"]}">{etiqueta}</text>')
        else:
            p.append(f'<text x="{cx:.1f}" y="{y(0) + 18:.1f}" text-anchor="middle" '
                     f'font-size="11" fill="{C["tinta_2"]}">{etiqueta}</text>')
            p.append(f'<text x="{cx:.1f}" y="{y(0) + 32:.1f}" text-anchor="middle" '
                     f'font-size="10" fill="{C["tenue"]}">J{r.jornada}</text>')
    p.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y(REFERENCIA):.1f}" '
             f'y2="{y(REFERENCIA):.1f}" stroke="{C["tinta_2"]}" stroke-width="1.5" '
             f'stroke-dasharray="5 4"/>')
    p.append(f'<text x="{W - mr}" y="{y(REFERENCIA) - 6:.1f}" text-anchor="end" '
             f'font-size="11" fill="{C["tinta_2"]}">referencia {REFERENCIA}</text>')
    p.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y(0):.1f}" y2="{y(0):.1f}" '
             f'stroke="{C["tenue"]}" stroke-width="1"/>')
    p.append("</svg>")
    return "".join(p)


def kpi(valor: str, etiqueta: str, contexto: str) -> str:
    return (f'<div class="kpi"><div class="kv">{valor}</div>'
            f'<div class="kl">{etiqueta}</div><div class="kc">{contexto}</div></div>')


def tabla(cabeza: list[str], filas: list[list[str]], num_desde: int = 1) -> str:
    th = "".join(f'<th class="{"n" if i >= num_desde else ""}">{h}</th>'
                 for i, h in enumerate(cabeza))
    trs = []
    for f in filas:
        clase = ' class="sin"' if "sin captura" in f else ""
        tds = "".join(f'<td class="{"n" if i >= num_desde else ""}">{c}</td>'
                      for i, c in enumerate(f))
        trs.append(f"<tr{clase}>{tds}</tr>")
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


def armar_html(codigo: str, nombre: str, vis: pd.DataFrame, reglas: pd.DataFrame,
               hasta: date, generado: datetime) -> str:
    vis = vis.copy()
    vis["fecha"] = pd.to_datetime(vis["fecha_visita"], errors="coerce").dt.date
    suyas_todas = vis[(vis["brigadista_codigo"] == codigo) & (vis["brigadista"] == nombre)]
    sin_fecha = int(suyas_todas["fecha"].isna().sum())

    fechadas = vis[vis["fecha"].notna() & (vis["fecha"] <= hasta)]
    jornadas = sorted(fechadas["fecha"].unique())
    if not jornadas:
        sys.exit(f"No hay jornadas con captura hasta {hasta.isoformat()}.")
    num_jornada = {d: i + 1 for i, d in enumerate(jornadas)}
    equipo = fechadas[fechadas["brigadista_codigo"] != ""]
    suyas = equipo[(equipo["brigadista_codigo"] == codigo) & (equipo["brigadista"] == nombre)]
    if suyas.empty:
        sys.exit(f"{codigo} · {nombre} no tiene visitas fechadas hasta {hasta.isoformat()}.")

    # ── Resumen contra la mediana del equipo ────────────────────────────────
    por_persona = [indicadores(g) for _, g in
                   equipo.groupby(["brigadista_codigo", "brigadista"])]
    yo = indicadores(suyas)
    med = {k: mediana_equipo(por_persona, k) for k in yo}
    n_equipo = len(por_persona)

    kpis = "".join([
        kpi(_num(yo["entrevistas"]), "Entrevistas",
            f"en {_num(yo['visitas'])} visitas · mediana del equipo: {_num(med['entrevistas'])}"),
        kpi(_num(yo["por_jornada"], 1), "Entrevistas por jornada con captura",
            f"referencia {REFERENCIA} · mediana del equipo: {_num(med['por_jornada'], 1)}"),
        kpi(f"{yo['jornadas']} de {len(jornadas)}", "Jornadas con captura",
            f"mediana del equipo: {_num(med['jornadas'])}"),
        kpi(f"{_num(yo['pct_entrevista'])}%", "Visitas que terminaron en entrevista",
            f"mediana del equipo: {_num(med['pct_entrevista'])}%"),
        kpi(_num(yo["volantes"]), "Volantes entregados",
            (f"{_num(yo['pct_volante'])}% de las visitas con registro de volante · "
             f"mediana del equipo: {_num(med['pct_volante'])}%")
            if yo["pct_volante"] is not None else "sin registro de volante"),
    ])

    # ── Jornada por jornada ─────────────────────────────────────────────────
    dia_equipo = (equipo.groupby(["fecha", "brigadista_codigo", "brigadista"])["entrevista"]
                  .sum().groupby("fecha").median())
    filas_j, reg = [], []
    for d in jornadas:
        g = suyas[suyas["fecha"] == d]
        con = not g.empty
        res = g["resultado"]
        secs = sorted(g["seccion_operativa"].unique(),
                      key=lambda s: int(s) if s.isdigit() else 10**9)
        reg.append({"fecha": d, "jornada": num_jornada[d], "con_captura": con,
                    "entrevistas": int(g["entrevista"].sum()) if con else None})
        if con:
            filas_j.append([str(num_jornada[d]), _f(d),
                            _num(int(g["entrevista"].sum())),
                            _num(dia_equipo.get(d), 1 if dia_equipo.get(d, 0) % 1 else 0),
                            _num(len(g)), _num(int((res == "completa").sum())),
                            _num(int((res == "parcial").sum())),
                            _num(int((res == "rechazo").sum())),
                            _num(int((res == "casa_sola").sum())),
                            _num(int((g["entrega_volante"] == "entrego").sum())),
                            ", ".join(secs)])
        else:
            filas_j.append([str(num_jornada[d]), _f(d), "sin captura",
                            _num(dia_equipo.get(d), 1 if dia_equipo.get(d, 0) % 1 else 0),
                            "—", "—", "—", "—", "—", "—", "—"])
    jd = pd.DataFrame(reg)

    # ── Secciones ───────────────────────────────────────────────────────────
    filas_s = []
    for sec, g in sorted(suyas.groupby("seccion_operativa"),
                         key=lambda kv: -len(kv[1])):
        dias = ", ".join(_f(d) for d in sorted(g["fecha"].unique()))
        filas_s.append([html.escape(sec or "sin sección"), _num(len(g)),
                        _num(int(g["entrevista"].sum())), dias])

    movidas = suyas[(suyas["seccion_declarada_original"] != "")
                    & (suyas["seccion_declarada_original"] != suyas["seccion_operativa"])]
    notas_mov = []
    for (d, dec, asig), g in movidas.groupby(
            ["fecha", "seccion_declarada_original", "seccion_operativa"]):
        regla = reglas[(reglas["fecha"].astype(str) == d.isoformat())
                       & (reglas["seccion_declarada"].astype(int).astype(str) == dec)]
        por_gps = (not regla.empty
                   and str(regla.iloc[0]["seccion_corregida"]).startswith("gps"))
        motivo = ("su ubicación GPS cae dentro de esa sección. Se registró la "
                  "sección asignada, pero el recorrido cruzó una frontera que no "
                  "es visible en la calle" if por_gps else
                  "el catálogo del formulario no permitía elegir la sección "
                  "trabajada; la corrección se aplicó a todo el equipo ese día")
        notas_mov.append(f"<li><b>{len(g)} visita{'s' if len(g) != 1 else ''} del "
                         f"{_f(d)}</b> capturada{'s' if len(g) != 1 else ''} como "
                         f"{html.escape(dec)} se cuenta{'n' if len(g) != 1 else ''} "
                         f"en la {html.escape(asig)}: {motivo}.</li>")
    bloque_mov = (f'<p class="nota">Secciones ajustadas al territorio trabajado:</p>'
                  f'<ul class="nota">{"".join(notas_mov)}</ul>') if notas_mov else ""

    aviso_sin_fecha = (
        f'<p class="nota">Además, {sin_fecha} visita{"s" if sin_fecha != 1 else ""} '
        f'suya{"s" if sin_fecha != 1 else ""} llegó sin fecha y no se puede asignar '
        f'a una jornada; no se cuenta{"n" if sin_fecha != 1 else ""} arriba.</p>'
        if sin_fecha else "")

    titulo = f"{html.escape(codigo)} · {html.escape(nombre)}"
    periodo = (f"Del {_f_larga(jornadas[0])} (jornada 1) al {_f_larga(jornadas[-1])} "
               f"(jornada {len(jornadas)})")

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Desempeño · {titulo} · PIE Atlixco</title>
<style>
@page {{ size: letter; margin: 14mm 12mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #fff; color: {C['tinta']};
  font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 13px; line-height: 1.45; -webkit-print-color-adjust: exact;
  print-color-adjust: exact; }}
.hoja {{ max-width: 860px; margin: 0 auto; padding: 28px 28px 40px; }}
.cab {{ border-bottom: 3px solid {C['ambar']}; padding-bottom: 14px; margin-bottom: 20px; }}
.eyebrow {{ font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: {C['ambar_osc']}; }}
h1 {{ font-size: 26px; margin: 4px 0 2px; letter-spacing: -.01em; }}
.sub {{ color: {C['tinta_2']}; }}
h2 {{ font-size: 15px; margin: 26px 0 10px; text-transform: uppercase; letter-spacing: .04em; }}
.kpis {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }}
.kpi {{ border: 1px solid {C['borde']}; border-left: 3px solid {C['ambar']};
  border-radius: 0 6px 6px 0; padding: 10px 11px; break-inside: avoid; }}
.kv {{ font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }}
.kl {{ font-size: 11.5px; font-weight: 600; margin-top: 2px; }}
.kc {{ font-size: 10.5px; color: {C['tenue']}; margin-top: 3px; line-height: 1.3; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; break-inside: auto; }}
th {{ text-align: left; font-size: 10.5px; text-transform: uppercase; letter-spacing: .04em;
  color: {C['tinta_2']}; border-bottom: 1.5px solid {C['tinta_2']}; padding: 6px 6px; }}
td {{ padding: 6px; border-bottom: 1px solid {C['borde']}; }}
tr {{ break-inside: avoid; }}
.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
tr.sin td {{ color: {C['tenue']}; font-style: italic; }}
.nota {{ font-size: 11.5px; color: {C['tinta_2']}; margin: 8px 0; }}
ul.nota {{ padding-left: 18px; }}
.lectura {{ background: {C['fondo_2']}; border-radius: 6px; padding: 12px 16px; margin-top: 26px;
  break-inside: avoid; }}
.lectura h2 {{ margin-top: 0; }}
.lectura li {{ margin-bottom: 4px; font-size: 11.5px; color: {C['tinta_2']}; }}
.pie {{ margin-top: 18px; font-size: 10.5px; color: {C['tenue']}; }}
@media (max-width: 700px) {{ .kpis {{ grid-template-columns: repeat(2, 1fr); }} }}
</style></head>
<body><div class="hoja">

<div class="cab">
  <div class="eyebrow">PIE Atlixco · Operativo de inducción · Desempeño por brigadista</div>
  <h1>{titulo}</h1>
  <div class="sub">{periodo} · {len(jornadas)} jornadas del equipo</div>
</div>

<h2>Resumen</h2>
<div class="kpis">{kpis}</div>
<p class="nota">La mediana del equipo es el valor de en medio entre los {n_equipo}
brigadistas con captura en el periodo, incluido este.</p>

<h2>Jornada por jornada</h2>
{grafica_svg(jd)}
{tabla(["Jornada", "Día", "Entrevistas", "Mediana del equipo", "Visitas", "Completas",
        "Parciales", "Rechazos", "Casas solas", "Volantes", "Secciones"], filas_j, num_desde=2)}
<p class="nota">«Mediana del equipo» es la del día, entre quienes capturaron esa jornada.</p>
{aviso_sin_fecha}

<h2>Dónde trabajó</h2>
{tabla(["Sección", "Visitas", "Entrevistas", "Jornadas"], filas_s, num_desde=1)}
{bloque_mov}

<div class="lectura">
<h2>Cómo leer este reporte</h2>
<ul>
<li><b>Entrevista</b> es una visita con contacto real: completa o parcial. Un rechazo o una
casa sola cuentan como visita, no como entrevista.</li>
<li><b>La referencia de {REFERENCIA} entrevistas por jornada</b> es de planeación, no un umbral
de evaluación: una jornada en sección rural dispersa rinde menos que una en el centro, y
la sección asignada pesa tanto como el trabajo de la persona.</li>
<li><b>Sin captura</b> quiere decir que no hay envíos de esta persona sincronizados con esa
fecha. Puede ser un día no trabajado o un teléfono que todavía no envía.</li>
<li><b>Las jornadas</b> son los días en que el equipo capturó; los días sin operativo no
se cuentan.</li>
<li><b>La sección</b> es la del registro, ajustada solo por correcciones documentadas del
operativo.</li>
</ul>
</div>

<div class="pie">Fuente: KoboToolbox, envíos sincronizados al {generado:%d/%m/%Y %H:%M} hora de
México. Mismo procesamiento que el tablero de monitoreo (M3).</div>
</div></body></html>
"""


# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brigadista", help="código (B14) o nombre, completo o en parte")
    ap.add_argument("--hasta", help="AAAA-MM-DD; omitido = hoy")
    ap.add_argument("--lista", action="store_true", help="muestra los brigadistas disponibles")
    ap.add_argument("--salida", help="ruta del HTML; omitido = reportes/brigadistas/")
    args = ap.parse_args()
    if not args.lista and not args.brigadista:
        ap.error("indica --brigadista o usa --lista")

    from zoneinfo import ZoneInfo
    ahora = datetime.now(ZoneInfo("America/Mexico_City"))
    try:
        hasta = date.fromisoformat(args.hasta) if args.hasta else ahora.date()
    except ValueError:
        sys.exit("--hasta debe ir como AAAA-MM-DD")

    vis, reglas = cargar_visitas()
    lista = brigadistas_en(vis)

    if args.lista:
        print(f"\n{'código':<8}{'visitas':>8}   nombre")
        for r in lista.itertuples(index=False):
            print(f"{r.brigadista_codigo:<8}{r.visitas:>8}   {r.brigadista}")
        return

    hits = resolver(args.brigadista, lista)
    if not hits:
        print(f"Nadie coincide con «{args.brigadista}». Disponibles:")
        for r in lista.itertuples(index=False):
            print(f"    {r.brigadista_codigo}  {r.brigadista}")
        sys.exit(1)
    if len(hits) > 1:
        print(f"«{args.brigadista}» coincide con más de una persona. Indica cuál:")
        for c, n in hits:
            print(f'    python3 reporte_brigadista.py --brigadista "{c if c != "B99" else n}"')
        sys.exit(2)

    codigo, nombre = hits[0]
    doc = armar_html(codigo, nombre, vis, reglas, hasta, ahora)
    if args.salida:
        ruta = args.salida
    else:
        os.makedirs(SALIDA_DIR, exist_ok=True)
        ruta = os.path.join(SALIDA_DIR, f"desempeno_{codigo}_{ahora:%Y%m%d_%H%M}.html")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"Reporte de {codigo} · {nombre}: {ruta}")


if __name__ == "__main__":
    main()
