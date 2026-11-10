#!/usr/bin/env python3
"""Qué cambió entre versiones del formulario — PIE Atlixco.

Cuando el XLSForm se vuelve a publicar, los envíos de la versión nueva pueden
llegar sin campos que el tablero da por hechos. Este script compara, versión
por versión, qué campos llegan y con qué frecuencia, para ver exactamente qué
se perdió y desde cuándo.

Uso, desde la raíz del repo:

    python3 diagnostico_campos.py
    python3 diagnostico_campos.py --todos   incluye campos poco frecuentes

Imprime NOMBRES de campo y porcentajes de llenado, nunca el contenido de las
respuestas. La única excepción son los códigos de sección, que son catálogo.
"""
import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

MX = ZoneInfo("America/Mexico_City")

# Lo que el tablero necesita para funcionar. Si uno de estos falta en una
# version, se nota de inmediato en M3 o en las correcciones por GPS.
CRITICOS = [
    ("inicio", "fecha del día de operativo"),
    ("fin", "duración de la entrevista"),
    ("gps", "ubicación, correcciones de sección y mapa"),
    ("seccion_electoral", "sección declarada"),
    ("seccion_declarada", "sección declarada (nombre alterno)"),
    ("brigadista", "productividad por brigadista"),
    ("contacto_inicial", "clasificación del resultado"),
    ("entrega_volante", "volantes entregados"),
    ("q01_reconocimiento", "señal de campo"),
]


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


def hojas(obj, prefijo=""):
    """Recorre el envío y devuelve (ruta_completa, nombre_corto, lleno)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            ruta = f"{prefijo}/{k}" if prefijo else k
            if isinstance(v, (dict, list)):
                yield from hojas(v, ruta)
            else:
                lleno = v is not None and str(v).strip() != ""
                yield ruta, k.split("/")[-1], lleno
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from hojas(v, f"{prefijo}[]")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--todos", action="store_true",
                    help="lista todos los campos, no solo los que cambiaron")
    args = ap.parse_args()

    import kobo_connector as kc

    cfg = leer_secrets()
    faltan = [k for k in ("base_url", "asset_uid", "api_token") if not cfg.get(k)]
    if faltan:
        sys.exit(f"Faltan en [kobo] de secrets.toml: {', '.join(faltan)}")

    print("Consultando Kobo...\n")
    envios = kc.fetch_all(cfg["base_url"], cfg["asset_uid"], cfg["api_token"])
    if not envios:
        sys.exit("Kobo no devolvió ningún envío.")

    por_ver = defaultdict(list)
    for raw in envios:
        ver = str(raw.get("__version__") or raw.get("_version") or "sin versión")
        por_ver[ver].append(raw)

    # Ordena las versiones por su primer envío, para leerlas como una línea
    # de tiempo en vez de por nombre.
    def primer_envio(rs):
        return min((str(r.get("_submission_time") or "~") for r in rs), default="~")
    versiones = sorted(por_ver, key=lambda v: primer_envio(por_ver[v]))

    print(f"Envíos: {len(envios)}  ·  versiones del formulario: {len(versiones)}\n")
    print("LÍNEA DE TIEMPO")
    for v in versiones:
        rs = por_ver[v]
        fechas = sorted(str(r.get("_submission_time") or "")[:10] for r in rs if r.get("_submission_time"))
        print(f"  {v}  {len(rs):>5} envíos   del {fechas[0] if fechas else '?'} "
              f"al {fechas[-1] if fechas else '?'}")

    # Llenado por version de cada campo corto.
    llenado = {}
    for v in versiones:
        rs = por_ver[v]
        cont = Counter()
        presente = Counter()
        for raw in rs:
            vistos = set()
            for _ruta, corto, lleno in hojas(raw):
                if corto.startswith("_") or corto.startswith("__"):
                    continue
                if corto not in vistos:
                    presente[corto] += 1
                    vistos.add(corto)
                if lleno:
                    cont[corto] += 1
        llenado[v] = {"n": len(rs), "lleno": cont, "presente": presente}

    print("\n" + "=" * 74)
    print("CAMPOS QUE EL TABLERO NECESITA")
    print("=" * 74)
    print("  % de envíos de esa versión que traen el campo con un valor.\n")
    anchos = [min(22, max(12, len(v))) for v in versiones]
    enc = "  " + f"{'campo':<22}" + "".join(f"{v[:a]:>{a+2}}" for v, a in zip(versiones, anchos))
    print(enc)
    print("  " + "-" * (22 + sum(a + 2 for a in anchos)))
    rotos = []
    for campo, para_que in CRITICOS:
        fila = "  " + f"{campo:<22}"
        pcts = []
        for v, a in zip(versiones, anchos):
            d = llenado[v]
            pct = 100.0 * d["lleno"].get(campo, 0) / d["n"] if d["n"] else 0.0
            pcts.append(pct)
            fila += f"{pct:>{a+1}.0f}%"
        print(fila)
        if pcts and max(pcts) >= 50 and min(pcts) < 50:
            rotos.append((campo, para_que, pcts))
    print(f"\n  {'(para qué sirve)':<22}")
    for campo, para_que in CRITICOS:
        print(f"  {campo:<22} {para_que}")

    if rotos:
        print("\n" + "=" * 74)
        print("SE ROMPIÓ ENTRE VERSIONES")
        print("=" * 74)
        for campo, para_que, pcts in rotos:
            print(f"\n  {campo}  —  {para_que}")
            for v, p in zip(versiones, pcts):
                estado = "llega" if p >= 50 else ("PARCIAL" if p > 0 else "NO LLEGA")
                print(f"      {v}  {p:>5.0f}%  {estado}")
    else:
        print("\n  Ningún campo crítico se perdió entre versiones.")

    # Campos que aparecen o desaparecen: delata un renombre.
    sets = {v: {c for c, n in llenado[v]["lleno"].items() if n} for v in versiones}
    if len(versiones) > 1:
        print("\n" + "=" * 74)
        print("CAMPOS QUE APARECEN O DESAPARECEN")
        print("=" * 74)
        print("  Un campo que desaparece junto con otro que aparece suele ser")
        print("  un renombre: ahí está la corrección.\n")
        for i in range(1, len(versiones)):
            ant, act = versiones[i - 1], versiones[i]
            ido = sorted(sets[ant] - sets[act])
            nuevo = sorted(sets[act] - sets[ant])
            print(f"  {ant}  ->  {act}")
            print(f"      dejaron de llegar: {', '.join(ido) if ido else '(ninguno)'}")
            print(f"      empezaron a llegar: {', '.join(nuevo) if nuevo else '(ninguno)'}")
            print()

    print("=" * 74)
    print("SECCIONES CAPTURADAS POR VERSIÓN")
    print("=" * 74)
    print("  Qué códigos de sección ELIGIÓ cada versión. Ojo: los envíos solo")
    print("  guardan la opción elegida, nunca el catálogo completo. Que una")
    print("  sección falte aquí no prueba que no estuviera disponible: puede")
    print("  ser que nadie la haya declarado, aunque sí se trabajara.\n")
    for v in versiones:
        secs = Counter()
        for raw in por_ver[v]:
            s = kc._get(raw, "seccion_electoral") or kc._get(raw, "seccion_declarada")
            if s is not None and str(s).strip():
                secs[str(s).strip()] += 1
        orden = sorted(secs.items(), key=lambda kv: (-kv[1], kv[0]))
        txt = " · ".join(f"{s} ({n})" for s, n in orden[:14]) or "(ninguna)"
        print(f"  {v}")
        print(f"      {txt}")
        if len(orden) > 14:
            print(f"      (+{len(orden) - 14} más)")

    if args.todos:
        print("\n" + "=" * 74)
        print("TODOS LOS CAMPOS")
        print("=" * 74)
        todos = sorted(set().union(*sets.values()))
        print("  " + f"{'campo':<30}" + "".join(f"{v[:10]:>13}" for v in versiones))
        for campo in todos:
            fila = "  " + f"{campo:<30}"
            for v in versiones:
                d = llenado[v]
                pct = 100.0 * d["lleno"].get(campo, 0) / d["n"] if d["n"] else 0.0
                fila += f"{pct:>12.0f}%"
            print(fila)


if __name__ == "__main__":
    main()
