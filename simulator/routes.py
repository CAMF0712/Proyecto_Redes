"""Rutas HTTP del SIMULADOR RESTCONF (subconjunto de RFC 8040).

Recursos implementados:
  GET            /.well-known/host-meta
  GET            /restconf
  GET            /restconf/data/ietf-interfaces:interfaces
  GET/PATCH/PUT  /restconf/data/ietf-interfaces:interfaces/interface=<nombre>
  GET            /restconf/data/ietf-interfaces:interfaces-state
  GET            /restconf/data/ietf-interfaces:interfaces-state/interface=<nombre>

Rutas propias del simulador (NO forman parte de RESTCONF):
  GET   /simulator/info    información del simulador
  POST  /simulator/reset   restaura los datos iniciales
  POST  /simulator/fault   inyecta fallos (500, demora, respuesta malformada);
                           solo si el servidor se inicio con fallos habilitados
"""

from __future__ import annotations

import base64
import hmac
import json
import time
from typing import Any

from flask import Blueprint, Response, current_app, request

from .data_store import InterfaceStore, StoreError

YANG_JSON = "application/yang-data+json"
SIMULATOR_HEADER = "RESTCONF-Simulator CE-5301 (no es un dispositivo real)"

bp = Blueprint("restconf_sim", __name__)


# ---------------------------------------------------------------- utilidades
def _store() -> InterfaceStore:
    return current_app.config["STORE"]


def _json(payload: Any, status: int = 200, content_type: str = YANG_JSON) -> Response:
    return Response(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    status=status, content_type=content_type)


def restconf_error(status: int, error_tag: str, message: str,
                   error_type: str = "application", path: str | None = None,
                   headers: dict | None = None) -> Response:
    """Construye un error con la estructura de RFC 8040, sección 7.1."""
    err: dict[str, Any] = {"error-type": error_type, "error-tag": error_tag}
    if path:
        err["error-path"] = f"/ietf-interfaces:interfaces/interface/{path}"
    err["error-message"] = message
    resp = _json({"ietf-restconf:errors": {"error": [err]}}, status)
    for key, value in (headers or {}).items():
        resp.headers[key] = value
    return resp


def _from_store_error(exc: StoreError) -> Response:
    return restconf_error(exc.status, exc.error_tag, exc.message, exc.error_type, exc.path)


def _check_auth() -> Response | None:
    expected_user = current_app.config["SIM_USER"]
    expected_pass = current_app.config["SIM_PASS"]
    header = request.headers.get("Authorization", "")
    ok = False
    if header.startswith("Basic "):
        try:
            user, _, pwd = base64.b64decode(header[6:]).decode("utf-8").partition(":")
            ok = (hmac.compare_digest(user, expected_user)
                  and hmac.compare_digest(pwd, expected_pass))
        except (ValueError, UnicodeDecodeError):
            ok = False
    if ok:
        return None
    return restconf_error(401, "access-denied",
                          "Autenticación requerida o credenciales incorrectas.",
                          error_type="protocol",
                          headers={"WWW-Authenticate": 'Basic realm="restconf-simulator"'})


def _check_accept() -> Response | None:
    accept = request.headers.get("Accept", "")
    if not accept:
        return None
    allowed = (YANG_JSON, "application/json", "*/*", "application/*")
    if any(a.strip().split(";")[0] in allowed for a in accept.split(",")):
        return None
    return restconf_error(406, "invalid-value",
                          f"El simulador solo produce '{YANG_JSON}'. Accept recibido: {accept}",
                          error_type="protocol")


def _parse_body() -> tuple[dict | None, Response | None]:
    ctype = request.headers.get("Content-Type", "").split(";")[0].strip()
    if ctype != YANG_JSON:
        return None, restconf_error(
            415, "invalid-value",
            f"Content-Type no soportado: '{ctype or 'ninguno'}'. Use '{YANG_JSON}'.",
            error_type="protocol")
    raw = request.get_data(as_text=True)
    if not raw.strip():
        return None, restconf_error(400, "malformed-message", "El cuerpo está vacío.",
                                    error_type="protocol")
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, restconf_error(400, "malformed-message",
                                    f"JSON mal formado: {exc.msg} (línea {exc.lineno}, "
                                    f"columna {exc.colno}).", error_type="protocol")


# ------------------------------------------------------- ganchos de solicitud
@bp.before_app_request
def _before() -> Response | None:
    path = request.path
    if path.startswith("/restconf") or path.startswith("/simulator"):
        auth_error = _check_auth()
        if auth_error is not None:
            return auth_error
    if path.startswith("/restconf"):
        faults = current_app.config["FAULTS"]
        if faults.get("count", 0) > 0:
            faults["count"] -= 1
            kind = faults.get("kind")
            if kind == "delay":
                time.sleep(float(faults.get("delay_seconds", 5)))
            elif kind == "error500":
                return restconf_error(500, "operation-failed",
                                      "Fallo interno inyectado en el simulador (prueba de "
                                      "manejo de errores).")
            elif kind == "malformed":
                return Response('{"ietf-interfaces:interfaces": {"interface": [',
                                status=200, content_type=YANG_JSON)
        accept_error = _check_accept()
        if accept_error is not None:
            return accept_error
    return None


@bp.after_app_request
def _after(resp: Response) -> Response:
    resp.headers["X-Simulator"] = SIMULATOR_HEADER
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ------------------------------------------------------------ descubrimiento
@bp.get("/.well-known/host-meta")
def host_meta() -> Response:
    xml = ("<XRD xmlns='http://docs.oasis-open.org/ns/xri/xrd-1.0'>\n"
           "  <Link rel='restconf' href='/restconf'/>\n</XRD>\n")
    return Response(xml, content_type="application/xrd+xml")


@bp.get("/restconf")
@bp.get("/restconf/")
def restconf_root() -> Response:
    return _json({"ietf-restconf:restconf": {
        "data": {}, "operations": {}, "yang-library-versión": "2019-01-04"}})


# ---------------------------------------------------------------- interfaces
@bp.get("/restconf/data/ietf-interfaces:interfaces")
def get_interfaces() -> Response:
    return _json({"ietf-interfaces:interfaces": {"interface": _store().list_config()}})


@bp.get("/restconf/data/ietf-interfaces:interfaces/interface=<path:name>")
def get_interface(name: str) -> Response:
    try:
        return _json({"ietf-interfaces:interface": [_store().get_config(name)]})
    except StoreError as exc:
        return _from_store_error(exc)


@bp.patch("/restconf/data/ietf-interfaces:interfaces/interface=<path:name>")
def patch_interface(name: str) -> Response:
    body, error = _parse_body()
    if error is not None:
        return error
    try:
        _store().merge(name, body)
    except StoreError as exc:
        return _from_store_error(exc)
    return Response(status=204)


@bp.put("/restconf/data/ietf-interfaces:interfaces/interface=<path:name>")
def put_interface(name: str) -> Response:
    body, error = _parse_body()
    if error is not None:
        return error
    try:
        _store().replace(name, body)
    except StoreError as exc:
        return _from_store_error(exc)
    return Response(status=204)


@bp.get("/restconf/data/ietf-interfaces:interfaces-state")
def get_interfaces_state() -> Response:
    return _json({"ietf-interfaces:interfaces-state": {"interface": _store().list_state()}})


@bp.get("/restconf/data/ietf-interfaces:interfaces-state/interface=<path:name>")
def get_interface_state(name: str) -> Response:
    try:
        return _json({"ietf-interfaces:interface": [_store().get_state(name)]})
    except StoreError as exc:
        return _from_store_error(exc)


# ------------------------------------------------ rutas propias del simulador
@bp.get("/simulator/info")
def simulator_info() -> Response:
    return _json({
        "simulador": True,
        "aviso": "Servidor de pruebas local. Los datos NO provienen de un router real "
                 "ni de Packet Tracer.",
        "dispositivo_simulado": _store().device,
        "fallos_habilitados": current_app.config["ENABLE_FAULTS"],
    }, content_type="application/json")


@bp.post("/simulator/reset")
def simulator_reset() -> Response:
    _store().reset()
    current_app.config["FAULTS"].clear()
    return _json({"resultado": "datos restaurados"}, content_type="application/json")


@bp.post("/simulator/fault")
def simulator_fault() -> Response:
    if not current_app.config["ENABLE_FAULTS"]:
        return _json({"error": "La inyección de fallos está deshabilitada. Inicie el "
                               "simulador con --enable-faults."}, 403, "application/json")
    data = request.get_json(silent=True) or {}
    kind = data.get("kind")
    if kind not in ("delay", "error500", "malformed"):
        return _json({"error": "kind debe ser 'delay', 'error500' o 'malformed'."}, 400,
                     "application/json")
    current_app.config["FAULTS"].update({
        "kind": kind,
        "count": int(data.get("count", 1)),
        "delay_seconds": float(data.get("delay_seconds", 5)),
    })
    return _json({"resultado": "fallo programado", **current_app.config["FAULTS"]},
                 content_type="application/json")


# --------------------------------------------- 404 y 405 con formato RESTCONF
def register_error_handlers(app) -> None:
    @app.errorhandler(404)
    def _not_found(_exc):  # noqa: ANN001
        return restconf_error(404, "invalid-value",
                              f"Recurso no encontrado: {request.path}", error_type="protocol")

    @app.errorhandler(405)
    def _not_allowed(exc):  # noqa: ANN001
        allowed = ", ".join(sorted(getattr(exc, "valid_methods", None) or []))
        return restconf_error(405, "operation-not-supported",
                              f"Método {request.method} no soportado en {request.path}. "
                              f"Permitidos: {allowed}.", error_type="protocol",
                              headers={"Allow": allowed})
