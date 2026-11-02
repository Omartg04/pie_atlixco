#!/usr/bin/env python3
"""Kobo API v2 -> archivos de operaciones sin datos de contacto.

No escribe el cuerpo JSON crudo ni los teléfonos. Su salida principal es independiente
 del framework de visualización. Opcionalmente produce GPS para supervisión privada.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

QUESTION_FIELDS = (
    "q01_reconocimiento", "q02_bienestar", "q03_comites_120",
    "q04_honestidad", "q05_coordinacion", "q06_problema",
    "q07_participacion", "q08_rango_edad",
)
RESULTS = ("completa", "parcial", "rechazo", "casa_sola")
AGE_CODES = ("18_29", "30_44", "45_59", "60_mas", "pno")
VOLANTE_CODES = ("entrego", "no_entrego")
VOLANTE_REQUIRED_VERSIONS = {"2026103005", "2026110206"}  # Formulario v0.5 y v0.6


def _get(record: dict, name: str) -> Any:
    """Tolera prefijos de grupo Enketo/Kobo, sin recuperar campos ambiguos."""
    if name in record:
        return record[name]
    matched = [v for k, v in record.items() if k.endswith("/" + name)]
    return matched[0] if len(matched) == 1 else None


def _str(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _section(v: Any) -> str:
    text = _str(v)
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return str(int(float(text)))
    return text


def _gps(value: Any, fallback: Any = None) -> tuple[float | None, float | None, float | None]:
    """Geopoint estándar: 'lat lon alt accuracy'; no se publica de forma predeterminada."""
    try:
        if isinstance(value, str):
            parts = value.replace(",", " ").split()
        elif isinstance(value, (tuple, list)):
            parts = value
        elif isinstance(fallback, (tuple, list)):
            parts = fallback
        else:
            parts = []
        if len(parts) < 2:
            return None, None, None
        lat, lon = float(parts[0]), float(parts[1])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None, None, None
        accuracy = float(parts[3]) if len(parts) > 3 and str(parts[3]) != "" else None
        return lat, lon, accuracy
    except (ValueError, TypeError):
        return None, None, None


def _name(record: dict, names: dict[str, str]) -> str:
    """Normaliza etiquetas de catálogo por código estable, incluso entre versiones.

    B08 era 'Alejandra' en v0.5 y pasó a 'Alejandra Salazar' en v0.6.
    Para B99 se respeta el nombre introducido por el brigadista.
    """
    code = _str(_get(record, "brigadista"))
    stored = _str(_get(record, "brigadista_nombre"))
    if code == "B99":
        return _str(_get(record, "brigadista_otro")) or stored or "Otro (sin nombre)"
    if code in names:
        return names[code]
    return stored or "Sin identificar"


def _outcome(record: dict) -> str:
    start = _str(_get(record, "contacto_inicial"))
    if start in {"rechazo", "casa_sola"}:
        return start
    if start == "acepta":
        final = _str(_get(record, "estado_entrevista"))
        if final in ("completa", "parcial"):
            return final
    explicit = _str(_get(record, "resultado"))
    return explicit if explicit in RESULTS else "sin_clasificar"


def _volante(v: Any) -> str:
    """Distingue no-entrega, ausencia de registro y códigos inesperados."""
    val = _str(v)
    if val in VOLANTE_CODES:
        return val
    return "sin_dato" if not val else "codigo_invalido"


def _volante_counts(rows: list[dict]) -> dict[str, Any]:
    n = Counter(x["entrega_volante"] for x in rows)
    con_dato = n["entrego"] + n["no_entrego"]
    return {
        "volantes_entregados": n["entrego"],
        "volantes_no_entregados": n["no_entrego"],
        "volantes_sin_dato": n["sin_dato"],
        "volantes_codigo_invalido": n["codigo_invalido"],
        "registros_volante_con_dato": con_dato,
        "tasa_entrega_pct": round(100 * n["entrego"] / con_dato, 1) if con_dato else "",
    }


def transform(submissions: list[dict], schema: dict) -> dict[str, Any]:
    names = {item["code"]: item["label"] for item in schema["choices"]["brigadistas"]}
    catalog = {item["code"] for item in schema["choices"]["secciones"]}
    ops = []
    gps_private = []
    seen = set()
    duplicate_count = 0
    unique_records = []
    for raw in submissions:
        uid = _str(raw.get("_uuid")) or _str(raw.get("_id"))
        if not uid:
            raise ValueError("Un envío no tiene _uuid ni _id; evitar pérdida de trazabilidad")
        if uid in seen:
            duplicate_count += 1
            continue
        seen.add(uid)
        unique_records.append(raw)
        record_id = hashlib.sha256(uid.encode("utf-8")).hexdigest()[:20]
        geo = _gps(_get(raw, "gps"), raw.get("_geolocation"))
        section = _section(_get(raw, "seccion_electoral") or _get(raw, "seccion_declarada"))
        ini = _str(_get(raw, "inicio"))
        accepted = _str(_get(raw, "contacto_inicial")) == "acepta"
        outcome = _outcome(raw)
        volante = _volante(_get(raw, "entrega_volante"))
        version = _str(raw.get("__version__") or raw.get("_version"))
        anomalies = []
        if volante == "codigo_invalido":
            anomalies.append("volante_codigo_invalido")
        if volante == "sin_dato" and version in VOLANTE_REQUIRED_VERSIONS:
            anomalies.append("volante_sin_dato_version_con_campo")
        code_brigadista = _str(_get(raw, "brigadista"))
        if code_brigadista and code_brigadista not in names:
            anomalies.append("brigadista_codigo_fuera_catalogo")
        if section not in catalog:
            anomalies.append("seccion_fuera_catalogo")
        if geo[0] is None:
            anomalies.append("gps_ausente")
        if outcome == "sin_clasificar":
            anomalies.append("resultado_no_clasificado")
        if accepted and not _str(_get(raw, "q01_reconocimiento")):
            anomalies.append("sin_pregunta_reconocimiento")
        ops.append({
            "registro_id": record_id,
            "version_formulario": version,
            "entrega_volante": volante,
            "fecha_visita": ini[:10] if len(ini) >= 10 else "",
            "inicio": ini,
            "fin": _str(_get(raw, "fin")),
            "fecha_recepcion_kobo": _str(raw.get("_submission_time")),
            "brigadista": _name(raw, names),
            "brigadista_codigo": code_brigadista,
            "seccion_operativa": section,
            "seccion_160_agrupada": "si" if section == "160" else "no",
            "contacto_inicial": _str(_get(raw, "contacto_inicial")),
            "resultado": outcome,
            "gps_registrado": "si" if geo[0] is not None else "no",
            "gps_precision_m": geo[2] if geo[2] is not None else "",
            "incidencias": ";".join(anomalies),
        })
        if geo[0] is not None:
            gps_private.append({
                "registro_id": record_id, "fecha_visita": ops[-1]["fecha_visita"],
                "brigadista": ops[-1]["brigadista"], "seccion_operativa": section,
                "latitud": geo[0], "longitud": geo[1], "precision_m": geo[2] if geo[2] is not None else "",
            })
    ops.sort(key=lambda x: (x["fecha_visita"], x["inicio"], x["registro_id"]))

    daily = defaultdict(list)
    by_brig = defaultdict(list)
    by_section = defaultdict(list)
    for row in ops:
        daily[row["fecha_visita"]].append(row)
        by_brig[(row["fecha_visita"], row["brigadista_codigo"], row["brigadista"])].append(row)
        by_section[row["seccion_operativa"]].append(row)

    def count_by_result(rows: list[dict]) -> dict[str, Any]:
        cnt = Counter(x["resultado"] for x in rows)
        return {"visitas":len(rows), "completas":cnt["completa"], "parciales":cnt["parcial"],
                "rechazos":cnt["rechazo"], "casas_solas":cnt["casa_sola"],
                "sin_clasificar":cnt["sin_clasificar"], **_volante_counts(rows)}

    days = []
    for day, rows in sorted(daily.items()):
        days.append({"fecha_visita":day, **count_by_result(rows),
                     "brigadistas_activos":len({(x["brigadista_codigo"],x["brigadista"]) for x in rows}),
                     "secciones_visitadas":len({x["seccion_operativa"] for x in rows if x["seccion_operativa"] in catalog}),
                     "visitas_con_gps":sum(x["gps_registrado"] == "si" for x in rows)})

    brig = [{"fecha_visita":day,"brigadista":name,"brigadista_codigo":code,
             **count_by_result(rows)}
            for (day,code,name),rows in sorted(by_brig.items())]
    sections = [{"seccion_operativa":c,"incluye_secciones_nuevas":"si" if c=="160" else "no",
                 **count_by_result(by_section[c])} for c in sorted(catalog,key=int)]

    # Sólo distribuciones globales, no cruces por GPS / sección / teléfono.
    questions = []
    field_choices = {field["name"]: field["type"].split()[1]
                     for field in schema["campos"] if field["name"] in QUESTION_FIELDS
                     and field["type"].startswith("select_one ")}
    allowed = {q: {choice["code"] for choice in schema["choices"].get(field_choices[q], [])}
               for q in field_choices}
    for q in QUESTION_FIELDS:
        observed = []
        for raw in unique_records:
            if _str(_get(raw, "contacto_inicial")) != "acepta":
                continue
            code = _str(_get(raw, q))
            if code:
                observed.append(code if code in allowed.get(q, set()) else "fuera_catalogo")
        values = Counter(observed)
        for code, n in sorted(values.items()):
            questions.append({"variable":q,"codigo":code,"n":n,
                              "n_respondieron":len(observed)})

    status = {
        "generado_utc":datetime.now(timezone.utc).isoformat(),
        "registros_unicos":len(ops), "duplicados_identificador":duplicate_count,
        "visitas_sin_gps":sum(x["gps_registrado"]=="no" for x in ops),
        "registros_sin_clasificar":sum(x["resultado"]=="sin_clasificar" for x in ops),
        "volantes_entregados":sum(x["entrega_volante"]=="entrego" for x in ops),
        "volantes_no_entregados":sum(x["entrega_volante"]=="no_entrego" for x in ops),
        "volantes_sin_dato":sum(x["entrega_volante"]=="sin_dato" for x in ops),
        "volantes_codigo_invalido":sum(x["entrega_volante"]=="codigo_invalido" for x in ops),
        "observacion":"Datos sólo de envíos sincronizados. Sin teléfonos ni respuestas individuales en el extracto operativo.",
    }
    return {"visitas_operativas":ops, "resumen_diario":days, "productividad_brigadista":brig,
            "cobertura_seccion":sections, "respuestas_agregadas":questions,
            "supervision_gps_privado":gps_private, "estado":status}


def fetch_all(base: str, asset_uid: str, token: str) -> list[dict]:
    if not re.fullmatch(r"[A-Za-z0-9]+", asset_uid):
        raise ValueError("El UID de Kobo debe ser alfanumérico")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.path not in {"", "/"}:
        raise ValueError("KOBO_BASE_URL debe ser una URL HTTPS de servidor sin ruta ni usuario")
    retries = Retry(total=3, connect=3, read=3, backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET"], respect_retry_after_header=True)
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({"Authorization":f"Token {token}","Accept":"application/json"})
    url = base.rstrip("/") + f"/api/v2/assets/{asset_uid}/data/"
    records: list[dict] = []
    visited = set()
    while url:
        clean = urlsplit(urljoin(base,url))
        # Impide enviar el token a un host distinto por un valor next manipulado.
        if clean.scheme != "https" or clean.netloc != parsed.netloc or not clean.path.startswith(f"/api/v2/assets/{asset_uid}/data/"):
            raise RuntimeError("Enlace de paginación fuera de ruta/host esperado")
        canonical = clean.geturl()
        if canonical in visited:
            raise RuntimeError("Bucle de paginación detectado")
        visited.add(canonical)
        response = session.get(canonical, timeout=(10, 45), allow_redirects=False)
        response.raise_for_status()
        if 300 <= response.status_code < 400:
            raise RuntimeError("Redirección inesperada de API")
        page = response.json()
        if not isinstance(page,dict) or not isinstance(page.get("results"),list):
            raise ValueError("Respuesta API sin lista results; verificar endpoint y permisos")
        records.extend(page["results"])
        url = page.get("next")
    return records


OUTPUT_COLS = {
    "visitas_operativas":["registro_id","version_formulario","entrega_volante","fecha_visita","inicio","fin","fecha_recepcion_kobo",
                          "brigadista","brigadista_codigo","seccion_operativa","seccion_160_agrupada","contacto_inicial",
                          "resultado","gps_registrado","gps_precision_m","incidencias"],
    "resumen_diario":["fecha_visita","visitas","completas","parciales","rechazos","casas_solas",
                      "sin_clasificar","volantes_entregados","volantes_no_entregados","volantes_sin_dato",
                      "volantes_codigo_invalido","registros_volante_con_dato","tasa_entrega_pct",
                      "brigadistas_activos","secciones_visitadas","visitas_con_gps"],
    "productividad_brigadista":["fecha_visita","brigadista","brigadista_codigo","visitas","completas","parciales",
                               "rechazos","casas_solas","sin_clasificar","volantes_entregados",
                               "volantes_no_entregados","volantes_sin_dato","volantes_codigo_invalido",
                               "registros_volante_con_dato","tasa_entrega_pct"],
    "cobertura_seccion":["seccion_operativa","incluye_secciones_nuevas","visitas","completas",
                         "parciales","rechazos","casas_solas","sin_clasificar","volantes_entregados",
                               "volantes_no_entregados","volantes_sin_dato","volantes_codigo_invalido",
                               "registros_volante_con_dato","tasa_entrega_pct"],
    "respuestas_agregadas":["variable","codigo","n","n_respondieron"],
    "supervision_gps_privado":["registro_id","fecha_visita","brigadista","seccion_operativa",
                              "latitud","longitud","precision_m"],
}


def write_csv(path: Path, rows: list[dict], cols: list[str], private: bool = False) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    if private:
        os.chmod(tmp,0o600)
    os.replace(tmp,path)


def run(records: list[dict], schema: dict, folder: Path, include_gps_private: bool) -> dict:
    result = transform(records,schema)
    folder.mkdir(parents=True,exist_ok=True)
    for key,cols in OUTPUT_COLS.items():
        if key == "supervision_gps_privado" and not include_gps_private:
            continue
        write_csv(folder/(key+".csv"),result[key],cols,private=key=="supervision_gps_privado")
    status_path=folder/"estado.json"
    tmp=status_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result["estado"],ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,status_path)
    return result["estado"]


def main() -> None:
    arg=argparse.ArgumentParser(description="Kobo v0.6 Atlixco: conector de lectura para tablero")
    mode=arg.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo",action="store_true",help="Usa ejemplo ficticio, no consulta Kobo")
    mode.add_argument("--live",action="store_true",help="Consulta API Kobo v2 con variables de entorno")
    arg.add_argument("--output",default="salida",help="Carpeta para los CSV")
    arg.add_argument("--include-private-gps",action="store_true",
                     help="Exporta lat/lon por visita, exclusivamente para un tablero privado")
    args=arg.parse_args()
    folder=Path(__file__).resolve().parent
    schema=json.loads((folder/"schema_xlsform_v06.json").read_text(encoding="utf-8"))
    if args.include_private_gps and os.getenv("ALLOW_PRIVATE_GPS") != "true":
        raise SystemExit("Para habilitar GPS detallado configure ALLOW_PRIVATE_GPS=true en servidor privado")
    if args.demo:
        data=json.loads((folder/"ejemplo_ficticio.json").read_text(encoding="utf-8"))
    else:
        base=os.getenv("KOBO_BASE_URL","").strip()
        uid=os.getenv("KOBO_ASSET_UID","").strip()
        token=os.getenv("KOBO_API_TOKEN","").strip()
        if not base or not uid or not token:
            raise SystemExit("Faltan KOBO_BASE_URL, KOBO_ASSET_UID o KOBO_API_TOKEN (configuración local)")
        data=fetch_all(base,uid,token)
    status=run(data,schema,Path(args.output),args.include_private_gps)
    print("Conector ejecutado:",json.dumps(status,ensure_ascii=False))


if __name__ == "__main__":
    main()
