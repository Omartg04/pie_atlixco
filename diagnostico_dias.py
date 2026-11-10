#!/usr/bin/env python3
"""Por qué el tablero no muestra los días recientes — PIE Atlixco.

M3 arma el filtro de día y la tabla diaria a partir de `fecha_visita`, que el
conector deriva de los primeros 10 caracteres del campo `inicio` del
formulario. Si un día no aparece en el tablero, solo hay cuatro causas
posibles, y este script las separa:

  1. Los envíos de ese día todavía no llegan a Kobo (el teléfono no sincronizó).
  2. Llegaron, pero sin el campo `inicio`, así que no se pueden fechar.
  3. Llegaron con una versión nueva del formulario que cambió algún campo.
  4. Llegaron bien y el problema es el caché de Streamlit.

Uso, desde la raíz del repo:

    python3 diagnostico_dias.py
    python3 diagnostico_dias.py --dias 20

No imprime coordenadas ni respuestas: solo fechas, conteos y versiones.
"""
import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

MX = ZoneInfo("America/Mexico_City")


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


def fecha_recepcion(raw) -> str:
    """_submission_time viene en UTC; el tablero razona en hora de México."""
    s = str(raw.get("_submission_time") or "")
    if len(s) < 19:
        return ""
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=ZoneInfo("UTC"))
        return t.astimezone(MX).date().isoformat()
    except ValueError:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dias", type=int, default=12, help="cuántos días mostrar")
    args = ap.parse_args()

    import kobo_connector as kc

    cfg = leer_secrets()
    faltan = [k for k in ("base_url", "asset_uid", "api_token") if not cfg.get(k)]
    if faltan:
        sys.exit(f"Faltan en [kobo] de secrets.toml: {', '.join(faltan)}")

    hoy = datetime.now(MX).date()
    print(f"Hoy en México: {hoy.isoformat()}  ·  consultando Kobo...\n")
    envios = kc.fetch_all(cfg["base_url"], cfg["asset_uid"], cfg["api_token"])
    print(f"Envíos en Kobo: {len(envios)}\n")
    if not envios:
        sys.exit("Kobo no devolvió ningún envío. Revisa asset_uid y permisos del token.")

    por_visita = Counter()
    por_recepcion = Counter()
    sin_inicio = []
    recuperados = 0
    versiones_por_dia = defaultdict(Counter)
    ultimo = ""

    for raw in envios:
        ini = str(kc._get(raw, "inicio") or "")
        alias = str(raw.get("start") or "")
        if not ini.strip() and alias.strip():
            ini = alias
            recuperados += 1
        rec = fecha_recepcion(raw)
        ver = str(raw.get("__version__") or raw.get("_version") or "sin versión")
        f_vis = ini[:10] if len(ini) >= 10 else ""
        por_visita[f_vis] += 1
        por_recepcion[rec] += 1
        versiones_por_dia[f_vis or rec][ver] += 1
        if not f_vis:
            sin_inicio.append((rec, str(kc._get(raw, "brigadista") or "?"), ver))
        if rec > ultimo:
            ultimo = rec

    corte = (hoy - timedelta(days=args.dias)).isoformat()
    dias = sorted({d for d in list(por_visita) + list(por_recepcion) if d and d >= corte})

    print("Por día. 'Fecha de visita' es lo que usa el tablero; 'recibidos' es")
    print("cuándo llegaron a Kobo. Si un día tiene recibidos pero no visitas,")
    print("los envíos llegaron sin el campo `inicio`.\n")
    print(f"  {'día':<12} {'fecha de visita':>16} {'recibidos':>11}   versiones del formulario")
    print(f"  {'-'*12} {'-'*16} {'-'*11}   {'-'*32}")
    for d in dias:
        vers = versiones_por_dia.get(d, Counter())
        v_txt = ", ".join(f"{k} ({n})" for k, n in vers.most_common(3)) or "-"
        marca = "  <- hoy" if d == hoy.isoformat() else ""
        print(f"  {d:<12} {por_visita.get(d, 0):>16} {por_recepcion.get(d, 0):>11}   {v_txt}{marca}")

    if recuperados:
        print(f"\n✓ {recuperados} envíos traían la hora bajo `start` en vez de")
        print("  `inicio` (el formulario se republicó con los nombres por")
        print("  defecto de ODK). Ya están contados arriba: app_utils los")
        print("  recupera con normalizar_campos_tiempo().")

    print(f"\nÚltimo envío recibido en Kobo: {ultimo or 'ninguno'}")
    if ultimo and ultimo < hoy.isoformat():
        print(f"  Kobo no tiene nada de hoy ({hoy.isoformat()}). Los teléfonos")
        print("  todavía no sincronizan: no es un problema del tablero.")
    elif ultimo == hoy.isoformat():
        print("  Kobo sí tiene envíos de hoy.")

    if sin_inicio:
        print(f"\n⚠️  {len(sin_inicio)} envíos sin campo `inicio`: no se pueden fechar,")
        print("    así que no salen en el filtro por día ni en la tabla diaria.")
        print("    Sí cuentan en los totales de arriba del tablero.")
        c = Counter(b for _, b, _ in sin_inicio)
        print("    Por brigadista: " + " · ".join(f"{b}: {n}" for b, n in c.most_common(8)))
        cv = Counter(v for _, _, v in sin_inicio)
        print("    Por versión:    " + " · ".join(f"{v}: {n}" for v, n in cv.most_common(5)))

    todas = Counter()
    for vers in versiones_por_dia.values():
        todas.update(vers)
    if len(todas) > 1:
        print(f"\nVersiones del formulario en circulación: {len(todas)}")
        for v, n in todas.most_common():
            print(f"    {v}: {n} envíos")
        print("    Si una versión nueva renombró campos, sus envíos llegan")
        print("    incompletos. Compara contra schema_xlsform_v06.json.")

    hoy_s = hoy.isoformat()
    print("\nLectura:")
    if por_visita.get(hoy_s):
        print(f"  Hay {por_visita[hoy_s]} visitas fechadas hoy. Si el tablero no las")
        print("  muestra, es el caché: oprime 'Actualizar' arriba en M3.")
    elif por_recepcion.get(hoy_s):
        print(f"  Llegaron {por_recepcion[hoy_s]} envíos hoy pero ninguno trae fecha")
        print("  de visita utilizable. Revisa el campo `inicio` en el formulario.")
    else:
        print("  Kobo no tiene envíos de hoy todavía.")


if __name__ == "__main__":
    main()
