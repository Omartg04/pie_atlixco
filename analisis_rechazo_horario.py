#!/usr/bin/env python3
"""Rechazo y casa sola por hora, por sección y por brigadista — PIE Atlixco.

Contesta tres preguntas que la tabla por brigadista no puede:

  1. ¿A qué hora se encuentra la gente en casa y a qué hora rechaza más?
  2. ¿Qué secciones son difíciles para todos?
  3. ¿El rechazo de un brigadista es suyo o es de la zona? Se compara a cada
     persona contra sus compañeros en la MISMA sección y el MISMO día. Esa es
     la comparación justa para una alerta de desempeño: quien trabaja una
     sección difícil no queda marcado por la sección.

Uso, desde cualquier carpeta:

    python3 analisis_rechazo_horario.py
    python3 analisis_rechazo_horario.py --desde 2026-11-04 --hasta 2026-11-09

Mismo procesamiento que el tablero (fecha recuperada de `start`, reglas de
correcciones_seccion.csv). Imprime nombres de brigadista: es para uso interno
de coordinación, no para reenviar tal cual.

Definiciones:
  casa sola %            casas solas / visitas
  rechazo entre contactos rechazos / (entrevistas + rechazos): de quienes
                         abrieron la puerta, cuántos no quisieron
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd  # noqa: E402

from reporte_brigadista import cargar_visitas  # noqa: E402  (mismo procesamiento)

MX = "America/Mexico_City"
MIN_FRANJA = 30        # visitas mínimas para leer una franja sin asterisco
MIN_SECCION = 30       # visitas mínimas para listar una sección
MIN_CONTACTOS = 20     # contactos mínimos para comparar a un brigadista
UMBRAL_PP = 10         # puntos sobre sus compañeros para marcar alerta
Z_ALERTA = 2.0         # ~95%: la diferencia difícilmente es azar


def pct(a, b):
    return a / b * 100 if b else float("nan")


def preparar(vis: pd.DataFrame, desde, hasta) -> pd.DataFrame:
    v = vis[vis["brigadista_codigo"] != ""].copy()
    t = pd.to_datetime(v["inicio"], errors="coerce", utc=True).dt.tz_convert(MX)
    v["hora"] = t.dt.hour
    v["fecha"] = pd.to_datetime(v["fecha_visita"], errors="coerce").dt.date
    v = v[v["fecha"].notna()]
    if desde:
        v = v[v["fecha"] >= desde]
    if hasta:
        v = v[v["fecha"] <= hasta]
    v["es_ent"] = v["resultado"].isin(("completa", "parcial")).astype(int)
    v["es_rech"] = (v["resultado"] == "rechazo").astype(int)
    v["es_cs"] = (v["resultado"] == "casa_sola").astype(int)
    v["nombre"] = v["brigadista"].where(v["brigadista"] != "", v["brigadista_codigo"])
    return v


def agregar(g: pd.DataFrame) -> pd.Series:
    vis, ent, rech, cs = len(g), g["es_ent"].sum(), g["es_rech"].sum(), g["es_cs"].sum()
    return pd.Series({"visitas": vis, "entrevistas": ent, "rechazos": rech,
                      "casas_solas": cs, "casa_sola_pct": pct(cs, vis),
                      "rechazo_contacto_pct": pct(rech, ent + rech)})


def por_hora(v: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("1. POR HORA DEL DÍA — todo el equipo")
    print("=" * 78)
    sin_hora = v["hora"].isna().sum()
    h = v[v["hora"].notna()].groupby("hora").apply(agregar, include_groups=False)
    print(f"{'hora':<14}{'visitas':>8}{'casa sola':>11}{'rechazo entre':>15}{'entrevistas':>13}")
    print(f"{'':<14}{'':>8}{'%':>11}{'contactos %':>15}{'':>13}")
    for hr, r in h.iterrows():
        marca = " *" if r["visitas"] < MIN_FRANJA else ""
        print(f"{int(hr):02d}:00–{int(hr):02d}:59 {int(r['visitas']):>8}"
              f"{r['casa_sola_pct']:>10.0f}%{r['rechazo_contacto_pct']:>14.0f}%"
              f"{int(r['entrevistas']):>13}{marca}")
    t = agregar(v)
    print(f"{'total':<14}{int(t['visitas']):>8}{t['casa_sola_pct']:>10.0f}%"
          f"{t['rechazo_contacto_pct']:>14.0f}%{int(t['entrevistas']):>13}")
    print(f"\n* menos de {MIN_FRANJA} visitas: leer con cautela.")
    if sin_hora:
        print(f"  {sin_hora} visitas sin hora legible quedaron fuera de esta tabla.")

    # Franjas amplias: lo que se puede convertir en una instrucción de horario.
    bandas = pd.cut(v["hora"], bins=[0, 11, 13, 15, 17, 24], right=False,
                    labels=["antes de 11", "11–13", "13–15", "15–17", "17 en adelante"])
    b = v.assign(banda=bandas).dropna(subset=["banda"]) \
         .groupby("banda", observed=True).apply(agregar, include_groups=False)
    print("\n   Por franja:")
    for banda, r in b.iterrows():
        print(f"   {banda:<16}{int(r['visitas']):>6} visitas   casa sola "
              f"{r['casa_sola_pct']:>3.0f}%   rechazo entre contactos "
              f"{r['rechazo_contacto_pct']:>3.0f}%   "
              f"{r['entrevistas'] / r['visitas'] * 100:>3.0f}% termina en entrevista")


def por_seccion(v: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print(f"2. POR SECCIÓN — con al menos {MIN_SECCION} visitas")
    print("=" * 78)
    s = v.groupby("seccion_operativa").apply(agregar, include_groups=False)
    s["brigadistas"] = v.groupby("seccion_operativa")["nombre"].nunique()
    s = s[s["visitas"] >= MIN_SECCION].sort_values("casa_sola_pct", ascending=False)
    print(f"{'sección':<10}{'visitas':>8}{'brigadistas':>13}{'casa sola':>11}{'rechazo entre':>15}")
    for sec, r in s.iterrows():
        print(f"{sec:<10}{int(r['visitas']):>8}{int(r['brigadistas']):>13}"
              f"{r['casa_sola_pct']:>10.0f}%{r['rechazo_contacto_pct']:>14.0f}%")


def por_brigadista(v: pd.DataFrame) -> pd.DataFrame:
    """Cada brigadista contra sus compañeros en la misma sección y día.

    Para cada sección-día se calcula la tasa de los DEMÁS (sin la persona) y se
    pondera por los contactos de la persona en esa celda. Si nadie más trabajó
    esa sección ese día, la celda no aporta: no hay contra qué comparar.
    """
    print("\n" + "=" * 78)
    print("3. POR BRIGADISTA — contra sus compañeros en la misma sección y día")
    print("=" * 78)
    celda = (v.groupby(["fecha", "seccion_operativa", "nombre"])
             [["es_ent", "es_rech", "es_cs"]].sum().reset_index())
    celda["contactos"] = celda["es_ent"] + celda["es_rech"]
    celda["visitas"] = celda["contactos"] + celda["es_cs"]
    tot = celda.groupby(["fecha", "seccion_operativa"])[
        ["es_rech", "contactos", "es_cs", "visitas"]].transform("sum")
    celda["otros_rech"] = tot["es_rech"] - celda["es_rech"]
    celda["otros_cont"] = tot["contactos"] - celda["contactos"]
    celda["otros_cs"] = tot["es_cs"] - celda["es_cs"]
    celda["otros_vis"] = tot["visitas"] - celda["visitas"]

    filas = []
    for nombre, g in celda.groupby("nombre"):
        comp = g[g["otros_cont"] > 0]
        cont_comp = comp["contactos"].sum()
        p_otros = comp["otros_rech"] / comp["otros_cont"]
        esperado = (comp["contactos"] * p_otros).sum()
        # Varianza del conteo esperado si la persona rechazara igual que sus
        # compañeros en cada celda. Con ella se separa una diferencia real de
        # una que cabe en el azar de pocos contactos.
        var = (comp["contactos"] * p_otros * (1 - p_otros)).sum()
        z = (comp["es_rech"].sum() - esperado) / var ** 0.5 if var > 0 else float("nan")
        comp_cs = g[g["otros_vis"] > 0]
        esp_cs = (comp_cs["visitas"] * comp_cs["otros_cs"] / comp_cs["otros_vis"]).sum()
        filas.append({
            "brigadista": nombre,
            "contactos": int(g["contactos"].sum()),
            "rechazo_pct": pct(g["es_rech"].sum(), g["contactos"].sum()),
            "contactos_comparables": int(cont_comp),
            "rechazo_propio_comp": pct(comp["es_rech"].sum(), cont_comp),
            "rechazo_companeros": pct(esperado, cont_comp),
            "z": z,
            "casa_sola_propia_comp": pct(comp_cs["es_cs"].sum(), comp_cs["visitas"].sum()),
            "casa_sola_companeros": pct(esp_cs, comp_cs["visitas"].sum()),
        })
    r = pd.DataFrame(filas)
    r["dif_rechazo_pp"] = r["rechazo_propio_comp"] - r["rechazo_companeros"]
    r["dif_casa_sola_pp"] = r["casa_sola_propia_comp"] - r["casa_sola_companeros"]
    r = r.sort_values("dif_rechazo_pp", ascending=False)

    print("Rechazo entre contactos, solo en sección-días donde trabajó con alguien más.")
    print(f"{'brigadista':<22}{'contactos':>10}{'comparables':>13}{'suyo':>7}"
          f"{'compañeros':>12}{'dif':>7}   {'casa sola suya / compañeros'}")
    for x in r.itertuples():
        if x.contactos_comparables < MIN_CONTACTOS:
            print(f"{x.brigadista[:21]:<22}{x.contactos:>10}{x.contactos_comparables:>13}"
                  f"{'—':>7}{'—':>12}{'—':>7}   pocos contactos comparables")
            continue
        marca = ""
        if x.dif_rechazo_pp >= UMBRAL_PP:
            marca = "  ◀ alerta" if x.z >= Z_ALERTA else "  ◁ observación"
        print(f"{x.brigadista[:21]:<22}{x.contactos:>10}{x.contactos_comparables:>13}"
              f"{x.rechazo_propio_comp:>6.0f}%{x.rechazo_companeros:>11.0f}%"
              f"{x.dif_rechazo_pp:>+6.0f}   "
              f"{x.casa_sola_propia_comp:>3.0f}% / {x.casa_sola_companeros:>3.0f}%{marca}")
    print(f"\n◀ alerta: rechaza {UMBRAL_PP} puntos o más por encima de sus compañeros en "
          f"las mismas secciones y días,\n  con al menos {MIN_CONTACTOS} contactos "
          f"comparables, y la diferencia difícilmente es azar (z ≥ {Z_ALERTA:.0f}).")
    print(f"◁ observación: misma diferencia, pero con tan pocos contactos que podría ser "
          f"azar.\n  Revisar de nuevo en unos días antes de concluir.")
    print("  Ninguna de las dos es una sanción: señala dónde acompañar.")
    return r


def por_brigadista_y_franja(v: pd.DataFrame, alertas: list[str]) -> None:
    if not alertas:
        return
    print("\n" + "=" * 78)
    print("4. ALERTA Y OBSERVACIÓN — rechazo entre contactos por franja")
    print("=" * 78)
    bandas = pd.cut(v["hora"], bins=[0, 11, 13, 15, 17, 24], right=False,
                    labels=["<11", "11–13", "13–15", "15–17", "17+"])
    v = v.assign(banda=bandas)
    cols = ["<11", "11–13", "13–15", "15–17", "17+"]
    print(f"{'':<22}" + "".join(f"{c:>12}" for c in cols))
    for quien in ["(equipo)"] + alertas:
        g = v if quien == "(equipo)" else v[v["nombre"] == quien]
        celdas = []
        for c in cols:
            gg = g[g["banda"] == c]
            cont = gg["es_ent"].sum() + gg["es_rech"].sum()
            celdas.append(f"{pct(gg['es_rech'].sum(), cont):.0f}% ({cont})" if cont else "—")
        print(f"{quien[:21]:<22}" + "".join(f"{c:>12}" for c in celdas))
    print("\nEntre paréntesis, los contactos en esa franja.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--desde", help="AAAA-MM-DD")
    ap.add_argument("--hasta", help="AAAA-MM-DD")
    args = ap.parse_args()
    from datetime import date
    desde = date.fromisoformat(args.desde) if args.desde else None
    hasta = date.fromisoformat(args.hasta) if args.hasta else None

    vis, _reglas = cargar_visitas()
    v = preparar(vis, desde, hasta)
    print(f"\nVisitas analizadas: {len(v):,} · {v['nombre'].nunique()} brigadistas · "
          f"{v['fecha'].nunique()} jornadas")
    por_hora(v)
    por_seccion(v)
    r = por_brigadista(v)
    alertas = r[(r["contactos_comparables"] >= MIN_CONTACTOS)
                & (r["dif_rechazo_pp"] >= UMBRAL_PP)]["brigadista"].tolist()
    # La tabla 4 incluye alerta y observación: a las dos les sirve ver la hora.
    por_brigadista_y_franja(v, alertas)


if __name__ == "__main__":
    main()
