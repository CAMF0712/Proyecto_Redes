"""Genera evidencias REPRODUCIBLES contra el SIMULADOR RESTCONF.

Ejecuta los escenarios del plan de pruebas, guarda cada solicitud y respuesta
HTTP exactas, mide tiempos de respuesta y construye la colección de Postman
con ejemplos de respuesta reales del simulador.

Uso (desde la raíz del proyecto):
    python scripts/generar_evidencias.py

Todas las evidencias quedan marcadas como SIMULADAS: provienen del simulador
local, no de un router real ni de Packet Tracer.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from application.interface_manager import InterfaceManager  # noqa: E402
from application.operation_log import OperationLogger  # noqa: E402
from application.restconf_client import MODE_SIM, YANG_JSON, RestconfClient  # noqa: E402
from simulator.server import create_app  # noqa: E402

OUT = ROOT / "evidence" / "simulador"
POSTMAN = ROOT / "postman"
USER, PASS = "admin", "admin123"
IFACE = "GigabitEthernet0/0/1"
IFACE_ENC = "GigabitEthernet0%2F0%2F1"
AVISO = ("SIMULADO: generado contra el simulador RESTCONF local. No es comunicación "
         "con un router real ni con Packet Tracer.")


def start_simulator():
    app = create_app(enable_faults=True, user=USER, password=PASS)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return app, server, f"http://127.0.0.1:{server.server_port}"


def capture(base: str, n: int, slug: str, title: str, method: str, path: str,
            body=None, raw: str | None = None, auth=(USER, PASS)) -> dict:
    headers = {"Accept": YANG_JSON}
    data = None
    if body is not None or raw is not None:
        headers["Content-Type"] = YANG_JSON
        data = raw if raw is not None else json.dumps(body, ensure_ascii=False)
    start = time.perf_counter()
    resp = requests.request(method, base + path, headers=headers, data=data, auth=auth, timeout=10)
    elapsed = (time.perf_counter() - start) * 1000
    try:
        resp_body = resp.json() if resp.content else None
    except ValueError:
        resp_body = resp.text
    record = {
        "aviso": AVISO,
        "escenario": title,
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "solicitud": {
            "metodo": method,
            "url": "{{baseUrl}}" + path,
            "encabezados": {**headers, "Authorization": "Basic <omitido>"},
            "cuerpo": body if body is not None else raw,
        },
        "respuesta": {
            "codigo_http": resp.status_code,
            "encabezados": {k: v for k, v in resp.headers.items()
                            if k in ("Content-Type", "X-Simulator", "WWW-Authenticate", "Allow")},
            "cuerpo": resp_body,
        },
        "tiempo_ms": round(elapsed, 2),
    }
    (OUT / f"{n:02d}_{slug}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False)
                                              + "\n", encoding="utf-8")
    print(f"  {n:02d} {method:6} {resp.status_code}  {title}")
    return record


def scenarios(base: str, app) -> list[dict]:
    p_if = "/restconf/data/ietf-interfaces:interfaces"
    p_one = f"{p_if}/interface={IFACE_ENC}"
    nueva = "LAN1 - descripción modificada vía RESTCONF"
    recs = [
        capture(base, 1, "get_interfaces", "P02 Consulta GET de todas las interfaces", "GET", p_if),
        capture(base, 2, "get_interfaz_individual", "P03 Consulta de una interfaz individual",
                "GET", p_one),
        capture(base, 3, "get_estado_operativo", "Consulta del estado operativo (interfaces-state)",
                "GET", f"/restconf/data/ietf-interfaces:interfaces-state/interface={IFACE_ENC}"),
        capture(base, 4, "patch_descripcion", "P04 Modificación de la descripción mediante PATCH",
                "PATCH", p_one,
                body={"ietf-interfaces:interface": [{"name": IFACE, "description": nueva}]}),
        capture(base, 5, "get_verificacion", "P05 Consulta posterior para comprobar el cambio",
                "GET", p_one),
        capture(base, 6, "error_404_interfaz_inexistente", "P06 Interfaz inexistente", "GET",
                f"{p_if}/interface=GigabitEthernet9%2F9%2F9"),
        capture(base, 7, "error_401_credenciales", "P07 Autenticación incorrecta", "GET", p_if,
                auth=(USER, "clave-incorrecta")),
        capture(base, 8, "error_400_json_malformado", "P08 Solicitud inválida (JSON mal formado)",
                "PATCH", p_one, raw='{"ietf-interfaces:interface": [{"name": '),
        capture(base, 9, "error_400_no_cumple_modelo",
                "P08 Solicitud inválida (IP fuera del modelo, no se aplica)", "PATCH", p_one,
                body={"ietf-interfaces:interface": [{"name": IFACE, "ietf-ip:ipv4": {
                    "address": [{"ip": "300.1.1.1", "prefix-length": 24}]}}]}),
        capture(base, 10, "error_403_interfaz_protegida", "Interfaz protegida (403)", "PATCH",
                f"{p_if}/interface=GigabitEthernet0",
                body={"ietf-interfaces:interface": [{"name": "GigabitEthernet0",
                                                     "enabled": False}]}),
        capture(base, 11, "error_405_metodo", "Método no permitido (405)", "DELETE", p_one),
    ]
    app.config["FAULTS"].update({"kind": "error500", "count": 1})
    recs.append(capture(base, 12, "error_500_inyectado", "Error interno inyectado (500)", "GET",
                        p_if))
    recs.append(capture(base, 13, "put_cambio_ip", "Cambio de IP con PUT (entrada completa)", "PUT",
                        "/restconf/data/ietf-interfaces:interfaces/interface=GigabitEthernet0%2F0%2F2",
                        body={"ietf-interfaces:interface": [{
                            "name": "GigabitEthernet0/0/2", "description": "Sin uso",
                            "type": "iana-if-type:ethernetCsmacd", "enabled": False,
                            "ietf-ip:ipv4": {"address": [{"ip": "172.16.0.1",
                                                          "netmask": "255.255.255.0"}]}}]}))
    return recs


def client_flow(base_port: int) -> Path:
    """Flujo completo con el cliente de la aplicación (incluye el registro)."""
    log_file = OUT / "registro_operaciones.jsonl"
    log_file.unlink(missing_ok=True)
    logger = OperationLogger(log_file)
    client = RestconfClient("127.0.0.1", base_port, USER, PASS, use_https=False,
                            mode=MODE_SIM, logger=logger)
    manager = InterfaceManager(client)
    client.discover()
    manager.fetch_all()
    manager.apply(manager.plan_description(IFACE, "Cambio registrado por la aplicación"))
    manager.apply(manager.plan_enabled("GigabitEthernet0/0/2", True))
    client.get_interface("NoExiste")
    RestconfClient("127.0.0.1", base_port, USER, "incorrecta", use_https=False, mode=MODE_SIM,
                   logger=logger).get_interfaces()
    logger.export_csv(OUT / "registro_operaciones.csv")
    client.close()
    return log_file


def measure(base: str, port: int, app, n: int = 50) -> list[dict]:
    """Mide tiempos de respuesta (localhost; no representativo de un router real)."""
    app.config["STORE"].reset()
    s = requests.Session()
    s.auth = (USER, PASS)
    s.headers["Accept"] = YANG_JSON
    p_if = "/restconf/data/ietf-interfaces:interfaces"
    p_one = f"{p_if}/interface={IFACE_ENC}"

    def timed(fn):
        vals = []
        fn()  # calentamiento, no se mide
        for _ in range(n):
            t = time.perf_counter()
            r = fn()
            vals.append((time.perf_counter() - t) * 1000)
            assert r.status_code in (200, 204), r.status_code
        return vals

    body = json.dumps({"ietf-interfaces:interface": [{"name": IFACE, "description": "medicion"}]})
    manager = InterfaceManager(RestconfClient("127.0.0.1", port, USER, PASS, use_https=False))
    ops = {
        "GET interfaces": lambda: s.get(base + p_if),
        "GET interfaz individual": lambda: s.get(base + p_one),
        "PATCH descripción": lambda: s.patch(base + p_one, data=body,
                                             headers={"Content-Type": YANG_JSON}),
    }
    results = []
    for name, fn in ops.items():
        vals = timed(fn)
        results.append(_stats(name, vals))
    flow = []
    for i in range(n):
        t = time.perf_counter()
        out = manager.apply(manager.plan_description(IFACE, f"medicion {i}"))
        flow.append((time.perf_counter() - t) * 1000)
        assert out.verified
    results.append(_stats("Cambio completo (PATCH + GET de verificación)", flow))
    return results


def _stats(name: str, vals: list[float]) -> dict:
    ordered = sorted(vals)
    return {
        "operacion": name, "repeticiones": len(vals),
        "promedio_ms": round(statistics.mean(vals), 2),
        "mediana_ms": round(statistics.median(vals), 2),
        "desv_estandar_ms": round(statistics.stdev(vals), 2),
        "minimo_ms": round(ordered[0], 2),
        "p95_ms": round(ordered[int(0.95 * (len(ordered) - 1))], 2),
        "maximo_ms": round(ordered[-1], 2),
    }


# ------------------------------------------------------------------ Postman
def _url(path: str) -> dict:
    segs = [s for s in path.split("/") if s]
    return {"raw": "{{baseUrl}}/" + "/".join(segs), "host": ["{{baseUrl}}"], "path": segs}


def _item(name: str, desc: str, method: str, path: str, record: dict, tests: list[str],
          body=None, raw: str | None = None, auth_override: dict | None = None) -> dict:
    headers = [{"key": "Accept", "value": YANG_JSON}]
    req = {"method": method, "header": headers, "url": _url(path), "description": desc}
    if body is not None or raw is not None:
        headers.append({"key": "Content-Type", "value": YANG_JSON})
        req["body"] = {"mode": "raw",
                       "raw": raw if raw is not None else json.dumps(body, indent=2,
                                                                     ensure_ascii=False),
                       "options": {"raw": {"language": "json"}}}
    if auth_override:
        req["auth"] = auth_override
    resp = record["respuesta"]
    example = {
        "name": f"Ejemplo real del simulador - HTTP {resp['codigo_http']}",
        "originalRequest": {k: v for k, v in req.items() if k != "description"},
        "status": {200: "OK", 204: "No Content", 400: "Bad Request", 401: "Unauthorized",
                   404: "Not Found"}.get(resp["codigo_http"], ""),
        "code": resp["codigo_http"],
        "_postman_previewlanguage": "json",
        "header": [{"key": k, "value": v} for k, v in resp["encabezados"].items()],
        "body": json.dumps(resp["cuerpo"], indent=2, ensure_ascii=False) if resp["cuerpo"] else "",
    }
    return {"name": name,
            "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}],
            "request": req, "response": [example]}


def build_postman(recs: list[dict]) -> None:
    POSTMAN.mkdir(exist_ok=True)
    p_if = "/restconf/data/ietf-interfaces:interfaces"
    p_one = p_if + "/interface={{interfaceName}}"
    by = {r["escenario"][:3]: r for r in recs}
    nueva = "LAN1 - descripción modificada vía RESTCONF"
    flujo = [
        _item("1. GET interfaces", "Consulta todas las interfaces (modelo ietf-interfaces).",
              "GET", p_if, recs[0],
              ["pm.test('HTTP 200', () => pm.response.to.have.status(200));",
               "pm.test('Contiene ietf-interfaces:interfaces', () => {",
               "  pm.expect(pm.response.json()).to.have.property('ietf-interfaces:interfaces');",
               "});"]),
        _item("2. GET interfaz específica",
              "Consulta una interfaz. La '/' del nombre va codificada como %2F (RFC 8040 3.5.3).",
              "GET", p_one, recs[1],
              ["pm.test('HTTP 200', () => pm.response.to.have.status(200));",
               "const e = [].concat(pm.response.json()['ietf-interfaces:interface'])[0];",
               "pm.collectionVariables.set('descripcionOriginal', e.description || '');",
               "pm.test('Nombre correcto', () => pm.expect(e.name).to.eql("
               "decodeURIComponent(pm.variables.get('interfaceName'))));"]),
        _item("3. PATCH descripción",
              "Modifica solo la descripción (merge). Respuesta esperada: 204 No Content.",
              "PATCH", p_one, recs[3],
              ["pm.test('HTTP 204', () => pm.response.to.have.status(204));"],
              body={"ietf-interfaces:interface": [{"name": "{{interfaceNameDecoded}}",
                                                   "description": "{{nuevaDescripcion}}"}]}),
        _item("4. GET de verificación",
              "Vuelve a consultar la interfaz para comprobar que el cambio se aplicó.",
              "GET", p_one, recs[4],
              ["pm.test('HTTP 200', () => pm.response.to.have.status(200));",
               "const e = [].concat(pm.response.json()['ietf-interfaces:interface'])[0];",
               "pm.test('La descripción coincide con el cambio', () => {",
               "  pm.expect(e.description).to.eql(pm.variables.get('nuevaDescripcion'));",
               "});"]),
    ]
    errores = [
        _item("E1. Interfaz inexistente (404)", "Recurso que no existe.", "GET",
              p_if + "/interface=GigabitEthernet9%2F9%2F9", recs[5],
              ["pm.test('HTTP 404', () => pm.response.to.have.status(404));"]),
        _item("E2. Credenciales incorrectas (401)", "Autenticación básica con contraseña errónea.",
              "GET", p_if, recs[6],
              ["pm.test('HTTP 401', () => pm.response.to.have.status(401));"],
              auth_override={"type": "basic", "basic": [
                  {"key": "username", "value": "{{username}}", "type": "string"},
                  {"key": "password", "value": "clave-incorrecta", "type": "string"}]}),
        _item("E3. JSON mal formado (400)", "Cuerpo que no es JSON válido.", "PATCH", p_one,
              recs[7], ["pm.test('HTTP 400', () => pm.response.to.have.status(400));"],
              raw='{"ietf-interfaces:interface": [{"name": '),
    ]
    collection = {
        "info": {
            "_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "ce5301-restconf")),
            "name": "CE-5301 RESTCONF - ietf-interfaces",
            "description": (
                "Colección del proyecto CE-5301 (TEC). Funciona contra el simulador local "
                "(entorno 'Simulador RESTCONF local') o contra un dispositivo IOS XE con RESTCONF "
                "(entorno 'Dispositivo RESTCONF real'). Los ejemplos de respuesta se generaron con "
                "el SIMULADOR, no con un router real. Ejecute las solicitudes 1-4 en orden."),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {"type": "basic", "basic": [
            {"key": "username", "value": "{{username}}", "type": "string"},
            {"key": "password", "value": "{{password}}", "type": "string"}]},
        "variable": [
            {"key": "interfaceName", "value": "GigabitEthernet0%2F0%2F1"},
            {"key": "interfaceNameDecoded", "value": "GigabitEthernet0/0/1"},
            {"key": "nuevaDescripcion", "value": nueva},
        ],
        "item": [
            {"name": "Flujo principal", "item": flujo},
            {"name": "Manejo de errores", "item": errores},
        ],
    }
    (POSTMAN / "collection.json").write_text(json.dumps(collection, indent=2, ensure_ascii=False)
                                             + "\n", encoding="utf-8")
    envs = {
        "entorno_simulador.json": ("Simulador RESTCONF local", [
            ("baseUrl", "http://127.0.0.1:5000", "default"), ("username", "admin", "default"),
            ("password", "admin123", "secret")]),
        "entorno_dispositivo_real.json": ("Dispositivo RESTCONF real", [
            ("baseUrl", "https://DIRECCION_DEL_DISPOSITIVO:443", "default"),
            ("username", "", "default"), ("password", "", "secret")]),
    }
    for fname, (name, values) in envs.items():
        env = {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, fname)), "name": name,
               "values": [{"key": k, "value": v, "type": t, "enabled": True}
                          for k, v, t in values],
               "_postman_variable_scope": "environment"}
        (POSTMAN / fname).write_text(json.dumps(env, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    del by


def write_summary(recs: list[dict], stats: list[dict]) -> None:
    lines = [
        "# Evidencias del simulador RESTCONF",
        "",
        f"> **{AVISO}**",
        "",
        f"Generado: {datetime.now().astimezone().isoformat(timespec='seconds')} con "
        "`python scripts/generar_evidencias.py`.",
        "",
        "## Solicitudes y respuestas",
        "",
        "| # | Escenario | Método | Código HTTP | Tiempo (ms) | Archivo |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(recs, 1):
        files = sorted(OUT.glob(f"{i:02d}_*.json"))
        lines.append(f"| {i} | {r['escenario']} | {r['solicitud']['metodo']} | "
                     f"{r['respuesta']['codigo_http']} | {r['tiempo_ms']} | "
                     f"[`{files[0].name}`]({files[0].name}) |")
    lines += [
        "",
        "## Tiempos de respuesta",
        "",
        "Medidos contra el simulador en el mismo equipo (127.0.0.1), con una solicitud de "
        "calentamiento descartada. **No representan el tiempo de respuesta de un router real**, "
        "que incluye latencia de red, TLS y el procesamiento del dispositivo.",
        "",
        "| Operación | n | Promedio | Mediana | Desv. est. | Mín | P95 | Máx |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in stats:
        lines.append(f"| {s['operacion']} | {s['repeticiones']} | {s['promedio_ms']} | "
                     f"{s['mediana_ms']} | {s['desv_estandar_ms']} | {s['minimo_ms']} | "
                     f"{s['p95_ms']} | {s['maximo_ms']} |")
    lines += ["", "Valores en milisegundos. Datos crudos: [`tiempos_respuesta.csv`]"
              "(tiempos_respuesta.csv).", "",
              "## Registro de operaciones de la aplicación", "",
              "[`registro_operaciones.jsonl`](registro_operaciones.jsonl) y "
              "[`registro_operaciones.csv`](registro_operaciones.csv): flujo ejecutado con el "
              "cliente de la aplicación. Ninguno contiene contraseñas.", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("[0-9][0-9]_*.json"):
        old.unlink()
    app, server, base = start_simulator()
    port = server.server_port
    print(f"Simulador temporal en {base}\nEscenarios:")
    recs = scenarios(base, app)
    app.config["STORE"].reset()
    print("Flujo con el cliente de la aplicación ->", client_flow(port).name)
    print("Midiendo tiempos de respuesta ...")
    stats = measure(base, port, app)
    with (OUT / "tiempos_respuesta.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(stats[0]))
        writer.writeheader()
        writer.writerows(stats)
    for s in stats:
        print(f"  {s['operacion']:<48} promedio {s['promedio_ms']:>6} ms  p95 {s['p95_ms']:>6} ms")
    build_postman(recs)
    write_summary(recs, stats)
    server.shutdown()
    print(f"\nEvidencias en {OUT.relative_to(ROOT)} y colección en {POSTMAN.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
