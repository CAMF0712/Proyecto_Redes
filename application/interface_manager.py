"""Lógica de administracion de interfaces sobre el cliente RESTCONF.

Responsabilidades:
* Combinar la configuración (``ietf-interfaces:interfaces``) con el estado
  operativo (``ietf-interfaces:interfaces-state``), como los expone IOS XE.
* Preparar cada cambio como un ``ChangePlan`` (método, endpoint y cuerpo
  exactos) para que el usuario lo confirme antes de enviarlo.
* Aplicar el cambio y verificarlo con un GET posterior.

Decisión PATCH / PUT:
* Descripción y habilitación -> PATCH (merge): solo se envian las hojas que
  cambian.
* Dirección IPv4 -> PUT (reemplazo de la entrada completa): se lee la
  configuración actual, se sustituye la dirección y se envia la entrada
  completa. Así se evita que un merge agregue una segunda dirección en lugar
  de reemplazar la anterior.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from . import validators as v
from .restconf_client import RestconfClient, RestconfResult, interface_path

IP_KEY = "ietf-ip:ipv4"
UNKNOWN = "desconocido"


class MalformedDataError(ValueError):
    """La respuesta no tiene la estructura esperada del modelo YANG."""


@dataclass
class InterfaceInfo:
    name: str
    description: str = ""
    type: str = ""
    ip: str = ""
    prefix: int | None = None
    enabled: bool | None = None
    admin_status: str = UNKNOWN
    oper_status: str = UNKNOWN

    @property
    def ip_cidr(self) -> str:
        return f"{self.ip}/{self.prefix}" if self.ip and self.prefix is not None else ""


@dataclass
class ChangePlan:
    """Solicitud lista para enviarse; se muestra al usuario para confirmarla."""

    interface: str
    action: str
    method: str
    endpoint: str
    body: dict
    expected: dict  # hojas que deben verificarse después del cambio


@dataclass
class ChangeOutcome:
    plan: ChangePlan
    apply_result: RestconfResult
    verify_result: RestconfResult | None = None
    verified: bool = False
    after: InterfaceInfo | None = None
    mismatches: list[str] = field(default_factory=list)


@dataclass
class FetchOutcome:
    interfaces: list[InterfaceInfo]
    config_result: RestconfResult
    state_result: RestconfResult | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


# --------------------------------------------------------------- análisis JSON
def _entries(data: Any, container: str) -> list[dict]:
    """Extrae la lista 'interface' de un contenedor o de una entrada individual."""
    if not isinstance(data, dict):
        raise MalformedDataError("La respuesta no es un objeto JSON.")
    if container in data:
        inner = data[container]
        if not isinstance(inner, dict):
            raise MalformedDataError(f"'{container}' no es un objeto.")
        items = inner.get("interface", [])
    elif "ietf-interfaces:interface" in data:
        items = data["ietf-interfaces:interface"]
    else:
        raise MalformedDataError(
            f"No se encontro '{container}' ni 'ietf-interfaces:interface' en la respuesta.")
    if isinstance(items, dict):  # IOS XE devuelve un objeto para una sola entrada
        items = [items]
    if not isinstance(items, list) or not all(isinstance(i, dict) and "name" in i for i in items):
        raise MalformedDataError("La lista de interfaces no tiene la estructura esperada.")
    return items


def _parse_ipv4(entry: dict) -> tuple[str, int | None]:
    ipv4 = entry.get(IP_KEY) or {}
    addresses = ipv4.get("address") or []
    if isinstance(addresses, dict):
        addresses = [addresses]
    if not addresses:
        return "", None
    first = addresses[0]
    ip = str(first.get("ip", ""))
    if "prefix-length" in first:
        return ip, int(first["prefix-length"])
    if "netmask" in first:
        try:
            return ip, v.netmask_to_prefix(first["netmask"])
        except v.ValidationError:
            return ip, None
    return ip, None


def parse_config(data: Any, container: str = "ietf-interfaces:interfaces") -> list[InterfaceInfo]:
    result = []
    for entry in _entries(data, container):
        ip, prefix = _parse_ipv4(entry)
        enabled = entry.get("enabled", True)
        result.append(InterfaceInfo(
            name=entry["name"],
            description=entry.get("description", ""),
            type=entry.get("type", ""),
            ip=ip,
            prefix=prefix,
            enabled=enabled if isinstance(enabled, bool) else None,
            admin_status="up" if enabled is True else "down" if enabled is False else UNKNOWN,
        ))
    return result


def merge_state(interfaces: list[InterfaceInfo], state_data: Any) -> None:
    state = {e["name"]: e for e in _entries(state_data, "ietf-interfaces:interfaces-state")}
    for info in interfaces:
        st = state.get(info.name)
        if st:
            info.admin_status = st.get("admin-status", info.admin_status)
            info.oper_status = st.get("oper-status", UNKNOWN)


def summarize(interfaces: list[InterfaceInfo]) -> dict:
    return {
        "total": len(interfaces),
        "activas": sum(1 for i in interfaces if i.enabled is True),
        "desactivadas": sum(1 for i in interfaces if i.enabled is False),
        "operativas": sum(1 for i in interfaces if i.oper_status == "up"),
    }


# --------------------------------------------------------------------- gestor
class InterfaceManager:
    def __init__(self, client: RestconfClient):
        self.client = client

    # ----------------------------------------------------------------- lectura
    def fetch_all(self) -> FetchOutcome:
        cfg = self.client.get_interfaces()
        if not cfg.ok:
            return FetchOutcome([], cfg, None, cfg.error)
        try:
            interfaces = parse_config(cfg.data)
        except (MalformedDataError, TypeError, ValueError) as exc:
            return FetchOutcome([], cfg, None, f"Respuesta malformada: {exc}")
        state = self.client.get_interfaces_state()
        if state.ok:
            try:
                merge_state(interfaces, state.data)
            except (MalformedDataError, TypeError, ValueError):
                pass  # se conservan los datos de configuración
        return FetchOutcome(interfaces, cfg, state)

    def fetch_one(self, name: str) -> tuple[InterfaceInfo | None, RestconfResult, RestconfResult | None]:
        cfg = self.client.get_interface(name)
        if not cfg.ok:
            return None, cfg, None
        try:
            info = parse_config(cfg.data)[0]
        except (MalformedDataError, IndexError, TypeError, ValueError) as exc:
            cfg.ok = False
            cfg.error_kind = "malformed"
            cfg.error = f"Respuesta malformada: {exc}"
            return None, cfg, None
        state = self.client.get_interface_state(name)
        if state.ok:
            try:
                merge_state([info], state.data)
            except (MalformedDataError, TypeError, ValueError):
                pass
        return info, cfg, state

    # ------------------------------------------------------------ preparacion
    @staticmethod
    def _patch_body(name: str, leaves: dict) -> dict:
        return {"ietf-interfaces:interface": [{"name": name, **leaves}]}

    def plan_description(self, name: str, description: str) -> ChangePlan:
        name = v.validate_interface_name(name)
        description = v.validate_description(description)
        return ChangePlan(name, f"Cambiar descripción a '{description}'", "PATCH",
                          interface_path(name),
                          self._patch_body(name, {"description": description}),
                          {"description": description})

    def plan_enabled(self, name: str, enabled: bool) -> ChangePlan:
        name = v.validate_interface_name(name)
        action = "Habilitar interfaz (no shutdown)" if enabled else "Deshabilitar interfaz (shutdown)"
        return ChangePlan(name, action, "PATCH", interface_path(name),
                          self._patch_body(name, {"enabled": bool(enabled)}),
                          {"enabled": bool(enabled)})

    def plan_ipv4(self, name: str, ip: str, prefix: str | int) -> tuple[ChangePlan | None, RestconfResult]:
        """Lee la configuración actual y prepara un PUT con la entrada completa."""
        name = v.validate_interface_name(name)
        ip, prefix = v.validate_ipv4_host(ip, prefix)
        current = self.client.get_interface(name)
        if not current.ok:
            return None, current
        try:
            entry = _entries(current.data, "ietf-interfaces:interfaces")[0]
        except (MalformedDataError, IndexError) as exc:
            current.ok = False
            current.error_kind = "malformed"
            current.error = f"Respuesta malformada: {exc}"
            return None, current
        new_entry = copy.deepcopy(entry)
        ipv4 = dict(new_entry.get(IP_KEY) or {})
        # Se usa 'netmask', como lo representa IOS XE.
        ipv4["address"] = [{"ip": ip, "netmask": v.prefix_to_netmask(prefix)}]
        new_entry[IP_KEY] = ipv4
        body = {"ietf-interfaces:interface": [new_entry]}
        plan = ChangePlan(name, f"Cambiar dirección IPv4 a {ip}/{prefix}", "PUT",
                          interface_path(name), body, {"ip": ip, "prefix": prefix})
        return plan, current

    # -------------------------------------------------------------- aplicación
    def apply(self, plan: ChangePlan) -> ChangeOutcome:
        if plan.method == "PATCH":
            res = self.client.patch_interface(plan.interface, plan.body,
                                              operation=f"{plan.action} en {plan.interface}")
        elif plan.method == "PUT":
            res = self.client.put_interface(plan.interface, plan.body,
                                            operation=f"{plan.action} en {plan.interface}")
        else:  # pragma: no cover - planes construidos solo por este módulo
            raise ValueError(f"Método no soportado: {plan.method}")
        outcome = ChangeOutcome(plan, res)
        if not res.ok:
            return outcome
        # Verificación: GET posterior sobre la misma interfaz.
        verify = self.client.request("GET", interface_path(plan.interface),
                                     operation=f"Verificar cambio en {plan.interface} (GET)")
        outcome.verify_result = verify
        if not verify.ok:
            return outcome
        try:
            after = parse_config(verify.data)[0]
        except (MalformedDataError, IndexError, TypeError, ValueError) as exc:
            outcome.mismatches.append(f"No se pudo interpretar la verificación: {exc}")
            return outcome
        outcome.after = after
        for key, expected in plan.expected.items():
            actual = getattr(after, key)
            if actual != expected:
                outcome.mismatches.append(f"{key}: esperado {expected!r}, obtenido {actual!r}")
        outcome.verified = not outcome.mismatches
        return outcome
