"""
generar_reporte_m3.py — PIE Atlixco

Genera un reporte HTML autónomo (sin login, sin depender de la app corriendo)
con el avance del operativo de inducción — pensado para enviar a stakeholders
por correo o WhatsApp.

Contenido: KPIs principales + ranking de encuestadores + las 3 preguntas
clave sobre Arturo Solano (reconocimiento, buena candidatura, disposición a
votar), con barras simples de HTML/CSS.

No depende de Streamlit en tiempo de ejecución (no usa st.cache_data ni
st.session_state) — lee las credenciales directo de .streamlit/secrets.toml
y llama a la Data API de Bubble una sola vez por corrida.

Uso (desde la raíz del proyecto, junto a Home.py / app_utils.py):
    python generar_reporte_m3.py

Salida:
    reportes/reporte_m3_AAAAMMDD_HHMM.html
"""
import os
import sys
import json
from datetime import datetime

import pandas as pd

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # pip install tomli, para Python < 3.11

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bubble_connector import (
    _fetch_all_raw, _transform, ANCLA_OPERATIVO,
    HABITANTES_PROMEDIO_VIVIENDA, META_ENCUESTAS_DIARIAS, calcular_alertas,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTES_DIR = os.path.join(BASE_DIR, "reportes")

NOMBRES_EXCLUIDOS = {"omar téllez", "omar tellez"}

COLOR = {
    "bg_base": "#14181f", "bg_raised": "#1b212b", "bg_raised_2": "#202836",
    "border_subtle": "rgba(255,255,255,.08)", "text_primary": "#eef1f0",
    "text_secondary": "#8b95a8", "text_muted": "#5e6779", "amber": "#e8a33d",
}


def leer_private_key() -> str:
    ruta_secrets = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    if not os.path.exists(ruta_secrets):
        sys.exit(
            f"❌ No se encontró {ruta_secrets}. Este script necesita el mismo "
            "archivo de secrets que usa la app (bloque [bubble])."
        )
    with open(ruta_secrets, "rb") as f:
        secrets = tomllib.load(f)
    key = secrets.get("bubble", {}).get("private_key")
    if not key:
        sys.exit("❌ No se encontró [bubble] private_key en secrets.toml.")
    return key


def cargar_ln_corte500() -> pd.DataFrame:
    """Misma lógica que M3: LN corte 500 real por sección, derivada del
    geojson de manzanas. Independiente de app_utils para no requerir
    contexto de Streamlit."""
    path = os.path.join(DATA_DIR, "atlixco_unificado_web_capas.geojson")
    with open(path, encoding="utf-8") as f:
        manzanas = json.load(f)
    rows = [f["properties"] for f in manzanas["features"]]
    df_mz = pd.DataFrame(rows)
    df_mz["seleccionada_500"] = df_mz["seleccionada_500"].astype(str) == "True"

    agg = (
        df_mz[df_mz["seleccionada_500"]]
        .groupby("seccion")["LN_estimada_manzana"]
        .sum()
        .reset_index()
        .rename(columns={"LN_estimada_manzana": "ln_meta_500"})
    )

    path_spt = os.path.join(DATA_DIR, "SPT_indice_secciones_enriquecido.csv")
    df_spt = pd.read_csv(path_spt)
    df_spt["seccion"] = df_spt["seccion"].astype(int)

    todas = pd.DataFrame({"seccion": df_spt["seccion"].unique()})
    resultado = todas.merge(agg, on="seccion", how="left")
    resultado["ln_meta_500"] = resultado["ln_meta_500"].fillna(0).round(0).astype(int)
    return resultado


def barra_html(opcion: str, pct: float) -> str:
    return f"""
    <div style="margin-bottom:8px;">
      <div style="display:flex; justify-content:space-between; font-size:13px; color:{COLOR['text_secondary']};">
        <span>{opcion}</span><span style="font-family:monospace;">{pct:.1f}%</span>
      </div>
      <div style="background:{COLOR['bg_raised_2']}; border-radius:4px; height:8px; overflow:hidden;">
        <div style="width:{pct:.1f}%; background:{COLOR['amber']}; height:100%;"></div>
      </div>
    </div>
    """


def card_pregunta_html(titulo: str, serie: pd.Series, orden: list[str]) -> str:
    n_base = serie.notna().sum()
    n_total = len(serie)
    conteo = serie.value_counts(normalize=True).reindex(orden).fillna(0) * 100
    barras = "".join(barra_html(op, conteo.get(op, 0)) for op in orden)
    return f"""
    <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']};
                border-radius:8px; padding:18px 20px;">
      <div style="font-weight:700; color:{COLOR['text_primary']}; margin-bottom:4px;">{titulo}</div>
      <div style="font-size:12px; color:{COLOR['text_muted']}; margin-bottom:10px;">
        Base: {n_base} de {n_total} encuestas respondieron esta pregunta.
      </div>
      {barras}
    </div>
    """


def kpi_html(valor: str, label: str, ctx: str) -> str:
    return f"""
    <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']};
                border-left:3px solid {COLOR['amber']}; border-radius:0 8px 8px 0; padding:14px 16px;">
      <div style="font-family:monospace; font-size:26px; font-weight:700; color:{COLOR['text_primary']};">{valor}</div>
      <div style="font-size:13px; font-weight:600; color:{COLOR['text_primary']}; margin-top:4px;">{label}</div>
      <div style="font-size:12px; color:{COLOR['text_muted']}; margin-top:2px;">{ctx}</div>
    </div>
    """


def main():
    print("→ Leyendo credenciales de Bubble desde .streamlit/secrets.toml...")
    private_key = leer_private_key()

    print("→ Consultando Data API de Bubble...")
    raw = _fetch_all_raw(private_key)
    df = _transform(raw)
    total_bruto = len(df)

    print("→ Aplicando corte del operativo (18 jul 2026, 9:00 AM) y exclusiones...")
    df = df[
        (df["fecha_creacion"] >= ANCLA_OPERATIVO)
        & (~df["nombre_encuestador"].str.strip().str.lower().isin(NOMBRES_EXCLUIDOS))
    ].copy()
    total_filtrado = len(df)

    if df.empty:
        sys.exit("❌ No hay encuestas dentro del operativo real todavía. No se generó reporte.")

    hoy = datetime.now().date()
    df_hoy = df[df["fecha_creacion"].dt.date == hoy].copy()

    DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    dias_unicos = sorted(df["fecha_creacion"].dt.date.unique())
    dias_operativo_txt = ", ".join(
        f"{DIAS_ES[d.weekday()]} {d.day} de {MESES_ES[d.month - 1]}" for d in dias_unicos
    )
    n_dias_operativo = len(dias_unicos)

    print("→ Cargando LN corte 500 por sección...")
    df_ln500 = cargar_ln_corte500()

    conteo_seccion = (
        df.groupby("seccion_electoral").agg(encuestas=("id_unico", "count")).reset_index()
        .rename(columns={"seccion_electoral": "seccion"})
    )
    resumen = df_ln500.merge(conteo_seccion, on="seccion", how="left")
    resumen["encuestas"] = resumen["encuestas"].fillna(0).astype(int)
    # Proyección: 1 encuesta = 1 vivienda, se proyecta la LN tocada usando el
    # promedio de habitantes por vivienda del censo de Atlixco. No se trata
    # de visitar a cada persona de la LN (imposible, no es el objetivo).
    resumen["ln_proyectada_cubierta"] = (resumen["encuestas"] * HABITANTES_PROMEDIO_VIVIENDA).round(0).astype(int)
    resumen["pct_ln_cubierta"] = resumen.apply(
        lambda r: (r["ln_proyectada_cubierta"] / r["ln_meta_500"] * 100) if r["ln_meta_500"] > 0 else None, axis=1
    )

    pct_ln_total = resumen["ln_proyectada_cubierta"].sum() / resumen["ln_meta_500"].sum() * 100
    ln_proyectada_total = int(resumen["ln_proyectada_cubierta"].sum())
    secciones_cubiertas = int((resumen["encuestas"] > 0).sum())
    total_secciones = len(resumen)
    encuestadores_activos = df["nombre_encuestador"].nunique()
    tiempo_prom = df["duracion_min"].mean()

    kpis_html = "".join([
        kpi_html(f"{total_filtrado:,}", "Encuestas capturadas", "Acumulado, 1 encuesta = 1 vivienda"),
        kpi_html(f"{ln_proyectada_total:,}", "LN proyectada cubierta",
                 f"Encuestas × {HABITANTES_PROMEDIO_VIVIENDA} hab./vivienda (censo Atlixco)"),
        kpi_html(f"{pct_ln_total:.1f}%", "% LN cubierta (proyectada)", "LN proyectada / LN elegible, universo 500"),
        kpi_html(f"{secciones_cubiertas} de {total_secciones}", "Secciones cubiertas", "Con al menos 1 encuesta"),
        kpi_html(f"{tiempo_prom:.1f} min", "Duración promedio", "Duración de la entrevista, acumulado"),
    ])

    kpis_hoy_html = "".join([
        kpi_html(f"{len(df_hoy):,}", "Encuestas capturadas hoy", hoy.strftime("%d/%m/%Y")),
        kpi_html(f"{df_hoy['seccion_electoral'].nunique()}", "Secciones tocadas hoy", hoy.strftime("%d/%m/%Y")),
        kpi_html(f"{df_hoy['nombre_encuestador'].nunique()}", "Encuestadores activos hoy", hoy.strftime("%d/%m/%Y")),
        kpi_html(
            f"{df_hoy['duracion_min'].mean():.1f} min" if len(df_hoy) else "—",
            "Tiempo promedio hoy", hoy.strftime("%d/%m/%Y"),
        ),
    ]) if len(df_hoy) else None

    ranking_enc = (
        df.groupby("nombre_encuestador")
        .agg(total_encuestas=("id_unico", "count"), secciones_cubiertas=("seccion_electoral", "nunique"),
             duracion_prom=("duracion_min", "mean"))
        .reset_index().sort_values("total_encuestas", ascending=False)
    )
    ranking_enc["duracion_prom"] = ranking_enc["duracion_prom"].round(1)

    def tabla_encuestadores_html(df_base: pd.DataFrame, con_meta: bool = False) -> str:
        rk = (
            df_base.groupby("nombre_encuestador")
            .agg(total_encuestas=("id_unico", "count"), secciones_cubiertas=("seccion_electoral", "nunique"),
                 duracion_prom=("duracion_min", "mean"))
            .reset_index().sort_values("total_encuestas", ascending=False)
        )
        rk["duracion_prom"] = rk["duracion_prom"].round(1)
        col_meta_th = (
            f'<th style="padding:8px 12px; border-bottom:2px solid {COLOR["amber"]}; text-align:right;">Meta (20)</th>'
            if con_meta else ""
        )
        filas = "".join(
            f"""<tr>
                  <td style="padding:8px 12px; border-bottom:1px solid {COLOR['border_subtle']};">{r.nombre_encuestador}</td>
                  <td style="padding:8px 12px; border-bottom:1px solid {COLOR['border_subtle']}; text-align:right;">{r.total_encuestas}</td>
                  <td style="padding:8px 12px; border-bottom:1px solid {COLOR['border_subtle']}; text-align:right;">{r.secciones_cubiertas}</td>
                  <td style="padding:8px 12px; border-bottom:1px solid {COLOR['border_subtle']}; text-align:right;">{r.duracion_prom}</td>
                  {f'<td style="padding:8px 12px; border-bottom:1px solid {COLOR["border_subtle"]}; text-align:right;">{"✅" if r.total_encuestas >= META_ENCUESTAS_DIARIAS else "—"}</td>' if con_meta else ""}
                </tr>"""
            for r in rk.itertuples()
        )
        return f"""
        <table style="width:100%; border-collapse:collapse; font-size:13px; color:{COLOR['text_secondary']};">
          <thead>
            <tr style="text-align:left; font-size:12px; text-transform:uppercase; color:{COLOR['text_muted']};">
              <th style="padding:8px 12px; border-bottom:2px solid {COLOR['amber']};">Encuestador</th>
              <th style="padding:8px 12px; border-bottom:2px solid {COLOR['amber']}; text-align:right;">Total encuestas</th>
              <th style="padding:8px 12px; border-bottom:2px solid {COLOR['amber']}; text-align:right;">Secciones</th>
              <th style="padding:8px 12px; border-bottom:2px solid {COLOR['amber']}; text-align:right;">Duración prom. (min)</th>
              {col_meta_th}
            </tr>
          </thead>
          <tbody>{filas}</tbody>
        </table>
        """

    tabla_html = tabla_encuestadores_html(df)
    tabla_hoy_html = tabla_encuestadores_html(df_hoy, con_meta=True) if len(df_hoy) else None

    # ── Alertas de hoy ───────────────────────────────────────────────────────
    alertas_todas = calcular_alertas(df)
    alertas_hoy = alertas_todas[alertas_todas["dia"] == hoy] if not alertas_todas.empty else alertas_todas

    if alertas_hoy.empty:
        alertas_html = f"""<p style="font-size:13px; color:{COLOR['text_secondary']};">
          Sin alertas para hoy: nadie por debajo de la meta diaria, sin rachas de capturas rápidas.
        </p>"""
    else:
        filas_alertas = "".join(
            f"""<tr>
                  <td style="padding:6px 10px; border-bottom:1px solid {COLOR['border_subtle']};">{r.tipo}</td>
                  <td style="padding:6px 10px; border-bottom:1px solid {COLOR['border_subtle']};">{r.encuestador}</td>
                  <td style="padding:6px 10px; border-bottom:1px solid {COLOR['border_subtle']};">{r.detalle}</td>
                </tr>"""
            for r in alertas_hoy.itertuples()
        )
        alertas_html = f"""
        <table style="width:100%; border-collapse:collapse; font-size:13px; color:{COLOR['text_secondary']};">
          <thead>
            <tr style="text-align:left; font-size:12px; text-transform:uppercase; color:{COLOR['text_muted']};">
              <th style="padding:6px 10px; border-bottom:2px solid {COLOR['amber']};">Tipo</th>
              <th style="padding:6px 10px; border-bottom:2px solid {COLOR['amber']};">Encuestador</th>
              <th style="padding:6px 10px; border-bottom:2px solid {COLOR['amber']};">Detalle</th>
            </tr>
          </thead>
          <tbody>{filas_alertas}</tbody>
        </table>
        """

    # ── Desempeño diario vs. meta (pivote encuestador × día) ────────────────
    df_diario = df.copy()
    df_diario["dia"] = df_diario["fecha_creacion"].dt.date
    pivote = df_diario.groupby(["nombre_encuestador", "dia"]).size().unstack(fill_value=0).sort_index(axis=1)
    dias_cols = list(pivote.columns)
    pivote["Promedio/día"] = pivote.mean(axis=1).round(1)
    pivote = pivote.sort_values("Promedio/día", ascending=False)

    def _celda_dia(v: int) -> str:
        color = COLOR["amber"] if v >= META_ENCUESTAS_DIARIAS else COLOR["text_secondary"]
        peso = "700" if v >= META_ENCUESTAS_DIARIAS else "400"
        return f'<td style="padding:6px 10px; border-bottom:1px solid {COLOR["border_subtle"]}; text-align:right; color:{color}; font-weight:{peso};">{v}</td>'

    filas_pivote = "".join(
        f"""<tr>
              <td style="padding:6px 10px; border-bottom:1px solid {COLOR['border_subtle']};">{enc}</td>
              {''.join(_celda_dia(int(row[d])) for d in dias_cols)}
              <td style="padding:6px 10px; border-bottom:1px solid {COLOR['border_subtle']}; text-align:right; font-weight:700;">{row['Promedio/día']}</td>
            </tr>"""
        for enc, row in pivote.iterrows()
    )
    header_dias = "".join(
        f'<th style="padding:6px 10px; border-bottom:2px solid {COLOR["amber"]}; text-align:right;">{d.strftime("%d-%b")}</th>'
        for d in dias_cols
    )
    tabla_diario_html = f"""
    <table style="width:100%; border-collapse:collapse; font-size:12px; color:{COLOR['text_secondary']};">
      <thead>
        <tr style="text-align:left; font-size:11px; text-transform:uppercase; color:{COLOR['text_muted']};">
          <th style="padding:6px 10px; border-bottom:2px solid {COLOR['amber']};">Encuestador</th>
          {header_dias}
          <th style="padding:6px 10px; border-bottom:2px solid {COLOR['amber']}; text-align:right;">Promedio/día</th>
        </tr>
      </thead>
      <tbody>{filas_pivote}</tbody>
    </table>
    <p style="font-size:11px; color:{COLOR['text_muted']}; margin-top:8px;">
      Celda en ámbar y negrita = cumplió la meta diaria de {META_ENCUESTAS_DIARIAS} encuestas ese día.
    </p>
    """

    resumen_ordenado = resumen[resumen["encuestas"] > 0].sort_values(
        "pct_ln_cubierta", ascending=False, na_position="last"
    )
    filas_secciones = "".join(
        f"""<tr>
              <td style="padding:6px 12px; border-bottom:1px solid {COLOR['border_subtle']};">{int(r.seccion)}</td>
              <td style="padding:6px 12px; border-bottom:1px solid {COLOR['border_subtle']}; text-align:right;">{int(r.encuestas)}</td>
              <td style="padding:6px 12px; border-bottom:1px solid {COLOR['border_subtle']}; text-align:right;">{int(r.ln_proyectada_cubierta):,}</td>
              <td style="padding:6px 12px; border-bottom:1px solid {COLOR['border_subtle']}; text-align:right;">{int(r.ln_meta_500)}</td>
              <td style="padding:6px 12px; border-bottom:1px solid {COLOR['border_subtle']}; text-align:right;">{f'{r.pct_ln_cubierta:.1f}%' if pd.notna(r.pct_ln_cubierta) else '—'}</td>
            </tr>"""
        for r in resumen_ordenado.itertuples()
    )
    tabla_secciones_html = f"""
    <table style="width:100%; border-collapse:collapse; font-size:13px; color:{COLOR['text_secondary']};">
      <thead>
        <tr style="text-align:left; font-size:12px; text-transform:uppercase; color:{COLOR['text_muted']};">
          <th style="padding:6px 12px; border-bottom:2px solid {COLOR['amber']};">Sección</th>
          <th style="padding:6px 12px; border-bottom:2px solid {COLOR['amber']}; text-align:right;">Encuestas</th>
          <th style="padding:6px 12px; border-bottom:2px solid {COLOR['amber']}; text-align:right;">LN proyectada</th>
          <th style="padding:6px 12px; border-bottom:2px solid {COLOR['amber']}; text-align:right;">LN corte 500</th>
          <th style="padding:6px 12px; border-bottom:2px solid {COLOR['amber']}; text-align:right;">% LN cubierta</th>
        </tr>
      </thead>
      <tbody>{filas_secciones}</tbody>
    </table>
    """

    cards_arturo = "".join([
        card_pregunta_html("Reconocimiento", df["conocimiento_arturo"], ["Sí", "No", "No respondió"]),
        card_pregunta_html("Buena candidatura", df["buena_candidatura_arturo"],
                            ["Sí", "No", "No sabe (NO LEER)"]),
        card_pregunta_html("Disposición a votar", df["votar_o_no_arturo"],
                            ["Votaría", "Nunca votaría", "No sabe (NO LEER)"]),
    ])

    cards_programas = "".join([
        card_pregunta_html("Conocimiento del Programa Amor Puebla", df["amor_puebla"], ["Sí", "No"]),
        card_pregunta_html("Nivel de percepción de inseguridad", df["percepcion_inseguridad"],
                            ["Mucho", "Algo", "Poco"]),
        card_pregunta_html("Aceptación de comités de vigilancia", df["comite_vigilancia"],
                            ["Sí", "No", "No sabe (NO LEER)"]),
        card_pregunta_html("Valoración de las alarmas vecinales", df["alarma_vecinal"],
                            ["Mucho", "Algo", "Nada"]),
    ])

    ahora = datetime.now()
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>PIE Atlixco — Avance del operativo de inducción</title>
<style>
  * {{
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
    color-adjust: exact !important;
  }}
  @media print {{
    body {{ background: {COLOR['bg_base']} !important; }}
  }}
</style>
</head>
<body style="margin:0; background:{COLOR['bg_base']}; font-family:-apple-system,Segoe UI,Arial,sans-serif;">
  <div style="max-width:900px; margin:0 auto; padding:32px 24px;">

    <div style="font-family:monospace; font-size:11px; font-weight:700; letter-spacing:.1em;
                text-transform:uppercase; color:{COLOR['amber']}; margin-bottom:8px;">
      PIE Atlixco · Arturo Solano Escobedo
    </div>
    <h1 style="color:{COLOR['text_primary']}; font-size:28px; margin:0 0 6px;">
      Avance del operativo de inducción
    </h1>
    <p style="color:{COLOR['text_secondary']}; font-size:14px; margin:0 0 4px;">
      Reporte generado el {ahora.strftime('%d/%m/%Y a las %H:%M')} ·
      {total_bruto} registros totales en Bubble, {total_bruto - total_filtrado} descartados
      por ser anteriores al arranque real del operativo (18 jul 2026, 9:00 AM) ·
      <b style="color:{COLOR['text_primary']};">{total_filtrado} dentro del operativo real</b>.
    </p>
    <p style="color:{COLOR['text_secondary']}; font-size:14px; margin:0 0 28px;">
      📅 <b style="color:{COLOR['text_primary']};">{n_dias_operativo} día{'s' if n_dias_operativo != 1 else ''} de operativo:</b> {dias_operativo_txt}.
    </p>

    <h2 style="color:{COLOR['text_primary']}; font-size:18px; margin:0 0 12px;">
      Hoy — {hoy.strftime('%d/%m/%Y')}
    </h2>
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px;">
      {kpis_hoy_html if kpis_hoy_html else f'<p style="color:{COLOR["text_muted"]}; font-size:13px; grid-column:1/-1;">Sin encuestas capturadas hoy todavía.</p>'}
    </div>
    {f'''<div style="font-size:13px; font-weight:600; color:{COLOR['text_primary']}; margin-bottom:8px;">
      Desempeño de encuestadores — hoy
    </div>
    <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']}; border-radius:8px;
                padding:6px 0; margin-bottom:20px;">
      {tabla_hoy_html}
    </div>''' if tabla_hoy_html else ''}

    <div style="font-size:13px; font-weight:600; color:{COLOR['text_primary']}; margin-bottom:8px;">
      ⚠️ Alertas de hoy — {len(alertas_hoy)}
    </div>
    <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']}; border-radius:8px;
                padding:10px 6px; margin-bottom:28px;">
      {alertas_html}
    </div>

    <h2 style="color:{COLOR['text_primary']}; font-size:18px; margin:0 0 12px;">Acumulado del operativo</h2>
    <div style="display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-bottom:28px;">
      {kpis_html}
    </div>

    <h2 style="color:{COLOR['text_primary']}; font-size:18px; margin:0 0 12px;">Ranking de encuestadores — acumulado</h2>
    <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']}; border-radius:8px;
                padding:6px 0; margin-bottom:28px;">
      {tabla_html}
    </div>

    <h2 style="color:{COLOR['text_primary']}; font-size:18px; margin:0 0 12px;">
      Desempeño diario vs. meta ({META_ENCUESTAS_DIARIAS} encuestas/día)
    </h2>
    <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']}; border-radius:8px;
                padding:10px; margin-bottom:28px; overflow-x:auto;">
      {tabla_diario_html}
    </div>

    <h2 style="color:{COLOR['text_primary']}; font-size:18px; margin:0 0 12px;">
      Secciones con encuestas capturadas ({len(resumen_ordenado)} de {total_secciones})
    </h2>
    <div style="background:{COLOR['bg_raised']}; border:1px solid {COLOR['border_subtle']}; border-radius:8px;
                padding:6px 0; margin-bottom:28px; max-height:480px; overflow-y:auto;">
      {tabla_secciones_html}
    </div>

    <h2 style="color:{COLOR['text_primary']}; font-size:18px; margin:0 0 12px;">
      Resultados preliminares — Arturo Solano Escobedo
    </h2>
    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:20px;">
      {cards_arturo}
    </div>
    <p style="font-size:12px; color:{COLOR['text_muted']}; margin-bottom:28px;">
      Resultado preliminar de campo, no ponderado — no comparable directamente con la
      encuesta de referencia, que sí usa PESO_CAL.
    </p>

    <h2 style="color:{COLOR['text_primary']}; font-size:18px; margin:0 0 12px;">Programas</h2>
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px;">
      {cards_programas}
    </div>

    <div style="margin-top:32px; padding-top:14px; border-top:1px solid {COLOR['border_subtle']};
                font-family:monospace; font-size:11px; color:{COLOR['text_muted']}; letter-spacing:.03em;">
      PIE ATLIXCO · ARTURO SOLANO ESCOBEDO · PROCESO INTERNO MORENA 2026 · CONFIDENCIAL
    </div>
  </div>
</body>
</html>
"""

    os.makedirs(REPORTES_DIR, exist_ok=True)
    nombre_archivo = f"reporte_m3_{ahora.strftime('%Y%m%d_%H%M')}.html"
    ruta_salida = os.path.join(REPORTES_DIR, nombre_archivo)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Reporte generado: {ruta_salida}")


if __name__ == "__main__":
    main()