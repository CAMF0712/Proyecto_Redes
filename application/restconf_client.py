"""Cliente RESTCONF (RFC 8040) basado en ``requests``.

Funciona igual contra un dispositivo real compatible (por ejemplo Cisco IOS XE
con ``restconf`` habilitado) y contra el simulador local. El modo solo cambia
la etiqueta que se registra y se muestra; las solicitudes HTTP son las mismas.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests
import urllib3

from .operation_log import OperationLogger

YANG_JSON = "application/yang-data+json"
MODE_REAL = "RESTCONF real"
MODE_SIM = "Simulador local"

IF_PATH = "/restconf/data/ietf-interfaces:interfaces"
IF_STATE_PATH = "/restconf/data/ietf-interfaces:interfaces-state"

HTTP_MESSAGES = {
    400: "Solicitud inválida: el cuerpo o los datos no cumplen el modelo YANG.",
    401: "No autorizado: usuario o contraseña incorrectos.",
    403: "Prohibido: el usuario no tiene permiso para esta operación.",
    404: "No encontrado: el recurso o la interfaz no existe en el dispositivo.",
    405: "Método no permitido para este recurso.",
    406: "El dispositivo no puede responder en el formato solicitado.",
    409: "Conflicto: el recurso ya existe o está bloqueado.",
    415: "Tipo de contenido no soportado por el dispositivo.",
    500: "Error interno en el dispositivo o servidor.",
    503: "Servicio no disponible.",
}


@dataclass
class RestconfResult:
    """Resultado normalizado de una solicitud."""

    ok: bool
    method: str
    endpoint: str
    status: int | None
    elapsed_ms: float
    data: Any = None
    error: str | None = None
    error_kind: str | None = None  # http | timeout | connection | tls | malformed
    headers: dict = field(default_factory=dict)

    @property
    def is_simulator(self) -> bool:
        return "X-Simulator" in self.headers


def interface_path(name: str, state: bool = False) -> str:
    """Ruta de una entrada de lista; la clave se codifica (RFC 8040, 3.5.3).

    Ejemplo: 'GigabitEthernet0/0/1' -> 'interface=GigabitEthernet0%2F0%2F1'.
    """
    base = IF_STATE_PATH if state else IF_PATH
    return f"{base}/interface={quote(name, safe='')}"


def _restconf_error_message(response: requests.Response) -> str | None:
    """Extrae 'error-message' de un cuerpo ietf-restconf:errors, si existe."""
    try:
        body = response.json()
    except ValueError:
        return None
    errors = (body or {}).get("ietf-restconf:errors", {}).get("error", [])
    if isinstance(errors, dict):
        errors = [errors]
    messages = [e.get("error-message") or e.get("error-tag") for e in errors if isinstance(e, dict)]
    messages = [m for m in messages if m]
    return "; ".join(messages) if messages else None


class RestconfClient:
    def __init__(self, host: str, port: int, username: str, password: str, *,
                 use_https: bool = True, verify: bool | str = True, timeout: float = 10.0,
                 mode: str = MODE_REAL, logger: OperationLogger | None = None):
        self.host = host
        self.port = port
        self.use_https = use_https
        self.verify = verify if use_https else True
        self.timeout = timeout
        self.mode = mode
        self.logger = logger
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._session.headers.update({"Accept": YANG_JSON})
        if use_https and verify is False:
            # El usuario desactivo explicitamente la verificación TLS (laboratorio).
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ----------------------------------------------------------------- básico
    @property
    def base_url(self) -> str:
        scheme = "https" if self.use_https else "http"
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{scheme}://{host}:{self.port}"

    def close(self) -> None:
        self._session.close()

    def request(self, method: str, path: str, body: Any = None,
                operation: str | None = None, raw_body: str | None = None,
                content_type: str = YANG_JSON) -> RestconfResult:
        """Ejecuta una solicitud y devuelve siempre un ``RestconfResult``.

        Nunca lanza excepciones de red: los errores se clasifican en
        ``error_kind`` para que la interfaz gráfica pueda mostrarlos.
        """
        url = self.base_url + path
        headers = {}
        data = None
        if body is not None or raw_body is not None:
            headers["Content-Type"] = content_type
            data = raw_body if raw_body is not None else json.dumps(body)
        start = time.perf_counter()
        result: RestconfResult
        try:
            resp = self._session.request(method, url, data=data, headers=headers,
                                         timeout=self.timeout, verify=self.verify)
            elapsed = (time.perf_counter() - start) * 1000
            result = self._build_result(method, path, resp, elapsed)
        except requests.exceptions.SSLError as exc:
            result = self._failure(method, path, start, "tls",
                                   f"Error TLS: no se pudo validar el certificado ({exc.__class__.__name__}).")
        except requests.exceptions.Timeout:
            result = self._failure(method, path, start, "timeout",
                                   f"Tiempo de espera agotado ({self.timeout:g} s) sin respuesta del servidor.")
        except requests.exceptions.ConnectionError:
            result = self._failure(method, path, start, "connection",
                                   f"No se pudo conectar con {self.base_url}. Verifique la dirección, "
                                   "el puerto, que el servicio este activo y la conectividad.")
        except requests.exceptions.RequestException as exc:
            result = self._failure(method, path, start, "connection",
                                   f"Error de comunicación: {exc.__class__.__name__}.")
        self._log(operation or f"{method} {path}", result)
        return result

    def _build_result(self, method: str, path: str, resp: requests.Response,
                      elapsed: float) -> RestconfResult:
        headers = {k: v for k, v in resp.headers.items() if k.lower() != "set-cookie"}
        if 200 <= resp.status_code < 300:
            data = None
            if resp.content:
                try:
                    data = resp.json()
                except ValueError:
                    return RestconfResult(False, method, path, resp.status_code, elapsed, None,
                                          "Respuesta malformada: el cuerpo no es JSON válido.",
                                          "malformed", headers)
            return RestconfResult(True, method, path, resp.status_code, elapsed, data,
                                  headers=headers)
        detail = _restconf_error_message(resp)
        base = HTTP_MESSAGES.get(resp.status_code, f"Error HTTP {resp.status_code}.")
        message = f"{base} Detalle: {detail}" if detail else base
        return RestconfResult(False, method, path, resp.status_code, elapsed, None, message,
                              "http", headers)

    @staticmethod
    def _failure(method: str, path: str, start: float, kind: str, message: str) -> RestconfResult:
        return RestconfResult(False, method, path, None, (time.perf_counter() - start) * 1000,
                              None, message, kind)

    def _log(self, operation: str, result: RestconfResult) -> None:
        if not self.logger:
            return
        outcome = "OK" if result.ok else f"ERROR ({result.error_kind}): {result.error}"
        self.logger.record(self.mode, operation, result.method, self.base_url + result.endpoint,
                           result.status, outcome, result.elapsed_ms)

    # ------------------------------------------------------ recursos RESTCONF
    def discover(self) -> RestconfResult:
        """GET /restconf: comprueba conectividad, credenciales y soporte RESTCONF."""
        return self.request("GET", "/restconf", operation="Verificar conexión (GET /restconf)")

    def get_interfaces(self) -> RestconfResult:
        return self.request("GET", IF_PATH, operation="Consultar interfaces")

    def get_interface(self, name: str) -> RestconfResult:
        return self.request("GET", interface_path(name), operation=f"Consultar interfaz {name}")

    def get_interfaces_state(self) -> RestconfResult:
        return self.request("GET", IF_STATE_PATH, operation="Consultar estado de interfaces")

    def get_interface_state(self, name: str) -> RestconfResult:
        return self.request("GET", interface_path(name, state=True),
                            operation=f"Consultar estado de {name}")

    def patch_interface(self, name: str, body: dict, operation: str | None = None) -> RestconfResult:
        return self.request("PATCH", interface_path(name), body,
                            operation=operation or f"Modificar {name} (PATCH)")

    def put_interface(self, name: str, body: dict, operation: str | None = None) -> RestconfResult:
        return self.request("PUT", interface_path(name), body,
                            operation=operation or f"Reemplazar {name} (PUT)")
