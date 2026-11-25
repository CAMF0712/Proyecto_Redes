"""Almacen de datos en memoria del SIMULADOR RESTCONF.

Mantiene la configuración de interfaces siguiendo los modelos YANG
``ietf-interfaces`` (RFC 8343) e ``ietf-ip`` (RFC 8344) y calcula el estado
operativo simulado (``interfaces-state``).

IMPORTANTE: todos los datos de este módulo son simulados. No provienen de
Packet Tracer ni de un router real.
"""

from __future__ import annotations

import copy
import ipaddress
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DATA_FILE = Path(__file__).with_name("initial_data.json")

# Nombres de los módulos YANG usados como prefijo en JSON (RFC 7951).
IF_PREFIX = "ietf-interfaces"
IP_KEY = "ietf-ip:ipv4"

# Hojas de configuración aceptadas en una entrada de interfaz.
CONFIG_LEAVES = {"name", "description", "type", "enabled", IP_KEY}
# Hojas de solo lectura (config false). No pueden escribirse.
READ_ONLY_LEAVES = {
    "admin-status", "oper-status", "last-change", "if-index", "phys-address",
    "higher-layer-if", "lower-layer-if", "speed", "statistics",
}
IPV4_LEAVES = {"address", "enabled", "forwarding", "mtu"}
KNOWN_TYPES = {
    "iana-if-type:ethernetCsmacd",
    "iana-if-type:softwareLoopback",
    "iana-if-type:other",
}
# Limite de longitud de la descripción, igual que en Cisco IOS / IOS XE.
MAX_DESCRIPTION = 200


class StoreError(Exception):
    """Error que se traduce a una respuesta RESTCONF (RFC 8040, sección 7)."""

    def __init__(self, status: int, error_tag: str, message: str,
                 error_type: str = "application", path: str | None = None):
        super().__init__(message)
        self.status = status
        self.error_tag = error_tag
        self.error_type = error_type
        self.message = message
        self.path = path


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _netmask_from_prefix(prefix: int) -> str:
    return str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask)


def _prefix_from_netmask(netmask: str) -> int:
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
    except (ValueError, ipaddress.NetmaskValueError) as exc:
        raise StoreError(400, "invalid-value",
                         f"Máscara inválida o no contigua: {netmask!r}") from exc


class InterfaceStore:
    """Datastore simulado, seguro para hilos."""

    def __init__(self, data_file: Path | str | None = None):
        self._lock = threading.RLock()
        self._data_file = Path(data_file) if data_file else DEFAULT_DATA_FILE
        self.reset()

    # ------------------------------------------------------------------ carga
    def reset(self) -> None:
        with self._lock:
            raw = json.loads(self._data_file.read_text(encoding="utf-8"))
            self.device = raw.get("dispositivo_simulado", {})
            self.protected = set(self.device.get("interfaces_protegidas", []))
            self._config: dict[str, dict] = {}
            for entry in raw["config"]:
                self._config[entry["name"]] = entry
            self._phys: dict[str, dict] = raw.get("estado_fisico_simulado", {})
            self._last_change = {name: _now() for name in self._config}
            self._counters = {name: 0 for name in self._config}

    # ---------------------------------------------------------------- lectura
    def list_config(self) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(e) for e in self._config.values()]

    def get_config(self, name: str) -> dict:
        with self._lock:
            if name not in self._config:
                raise StoreError(404, "invalid-value",
                                 f"La interfaz '{name}' no existe en el dispositivo simulado.")
            return copy.deepcopy(self._config[name])

    def _state_for(self, name: str) -> dict:
        cfg = self._config[name]
        phys = self._phys.get(name, {})
        enabled = cfg.get("enabled", True)
        link = phys.get("enlace", False)
        self._counters[name] += 1
        n = self._counters[name]
        up = enabled and link
        return {
            "name": name,
            "type": cfg["type"],
            "admin-status": "up" if enabled else "down",
            "oper-status": "up" if up else "down",
            "last-change": self._last_change[name],
            "phys-address": phys.get("phys-address", "00:00:00:00:00:00"),
            "speed": str(phys.get("speed", 0)),
            "statistics": {
                "discontinuity-time": self._last_change[name],
                "in-octets": str(1500 * n if up else 0),
                "out-octets": str(1200 * n if up else 0),
                "in-errors": 0,
                "out-errors": 0,
            },
        }

    def list_state(self) -> list[dict]:
        with self._lock:
            return [self._state_for(name) for name in self._config]

    def get_state(self, name: str) -> dict:
        with self._lock:
            if name not in self._config:
                raise StoreError(404, "invalid-value",
                                 f"La interfaz '{name}' no existe en el dispositivo simulado.")
            return self._state_for(name)

    # -------------------------------------------------------------- escritura
    def _check_writable(self, name: str) -> None:
        if name not in self._config:
            raise StoreError(
                404, "invalid-value",
                f"La interfaz '{name}' no existe. El simulador no permite crear "
                "interfaces nuevas.")
        if name in self.protected:
            raise StoreError(
                403, "access-denied",
                f"La interfaz '{name}' está protegida en el simulador (gestión "
                "fuera de banda); no se permite modificarla.", error_type="protocol")

    def merge(self, name: str, body: dict) -> None:
        """Semantica PATCH (merge) de RFC 8040, sección 4.6.1."""
        with self._lock:
            self._check_writable(name)
            entry = self._validate_entry(name, body, require_type=False)
            current = self._config[name]
            if "type" in entry and entry["type"] != current["type"]:
                raise StoreError(400, "invalid-value",
                                 "No se puede cambiar el tipo de una interfaz existente.",
                                 path="type")
            new = copy.deepcopy(current)
            for key in ("description", "enabled", "type"):
                if key in entry:
                    new[key] = entry[key]
            if IP_KEY in entry:
                ipv4 = dict(new.get(IP_KEY, {}))
                for key, value in entry[IP_KEY].items():
                    # El simulador, igual que IOS, maneja una única dirección
                    # primaria: una nueva dirección reemplaza a la anterior.
                    ipv4[key] = value
                new[IP_KEY] = ipv4
            self._check_overlap(name, new)
            self._commit(name, current, new)

    def replace(self, name: str, body: dict) -> None:
        """Semantica PUT (reemplazo completo) de RFC 8040, sección 4.5."""
        with self._lock:
            self._check_writable(name)
            entry = self._validate_entry(name, body, require_type=True)
            current = self._config[name]
            if entry["type"] != current["type"]:
                raise StoreError(400, "invalid-value",
                                 "No se puede cambiar el tipo de una interfaz existente.",
                                 path="type")
            new = {"name": name, "type": entry["type"],
                   "enabled": entry.get("enabled", True)}
            if "description" in entry:
                new["description"] = entry["description"]
            new[IP_KEY] = entry.get(IP_KEY, {})
            self._check_overlap(name, new)
            self._commit(name, current, new)

    def _commit(self, name: str, old: dict, new: dict) -> None:
        if old.get("enabled", True) != new.get("enabled", True):
            self._last_change[name] = _now()
        self._config[name] = new

    # ------------------------------------------------------------ validación
    def _validate_entry(self, name: str, body: Any, require_type: bool) -> dict:
        """Valida el cuerpo contra la estructura del modelo YANG.

        Acepta tanto la forma de RFC 7951 para una entrada de lista
        (``{"ietf-interfaces:interface": [ {...} ]}``) como la forma de objeto
        que usa IOS XE (``{"ietf-interfaces:interface": {...}}``).
        """
        if not isinstance(body, dict) or len(body) != 1:
            raise StoreError(400, "malformed-message",
                             "El cuerpo debe ser un objeto JSON con la clave "
                             "'ietf-interfaces:interface'.", error_type="protocol")
        key, value = next(iter(body.items()))
        if key not in (f"{IF_PREFIX}:interface", "interface"):
            raise StoreError(400, "unknown-element",
                             f"Elemento raíz inesperado: '{key}'. Se esperaba "
                             "'ietf-interfaces:interface'.")
        if isinstance(value, list):
            if len(value) != 1:
                raise StoreError(400, "invalid-value",
                                 "La lista debe contener exactamente una interfaz.")
            value = value[0]
        if not isinstance(value, dict):
            raise StoreError(400, "invalid-value", "La interfaz debe ser un objeto JSON.")

        for leaf in value:
            if leaf in READ_ONLY_LEAVES:
                raise StoreError(400, "invalid-value",
                                 f"La hoja '{leaf}' es de solo lectura (config false) "
                                 "y no puede modificarse.", path=leaf)
            if leaf not in CONFIG_LEAVES:
                raise StoreError(400, "unknown-element",
                                 f"Elemento desconocido para el modelo: '{leaf}'.", path=leaf)

        if "name" in value and value["name"] != name:
            raise StoreError(400, "invalid-value",
                             "La clave 'name' del cuerpo no coincide con la de la URI "
                             f"('{value['name']}' != '{name}').", path="name")
        if require_type and "type" not in value:
            raise StoreError(400, "missing-element",
                             "PUT reemplaza la entrada completa: la hoja obligatoria "
                             "'type' es requerida.", path="type")
        if "type" in value and value["type"] not in KNOWN_TYPES:
            raise StoreError(400, "invalid-value",
                             f"Tipo de interfaz no soportado: {value['type']!r}.", path="type")
        if "description" in value:
            desc = value["description"]
            if not isinstance(desc, str):
                raise StoreError(400, "invalid-value",
                                 "'description' debe ser una cadena de texto.", path="description")
            if len(desc) > MAX_DESCRIPTION:
                raise StoreError(400, "invalid-value",
                                 f"'description' excede {MAX_DESCRIPTION} caracteres.",
                                 path="description")
            if any(ord(c) < 32 for c in desc):
                raise StoreError(400, "invalid-value",
                                 "'description' contiene caracteres de control.",
                                 path="description")
        if "enabled" in value and not isinstance(value["enabled"], bool):
            raise StoreError(400, "invalid-value",
                             "'enabled' debe ser booleano (true/false).", path="enabled")

        result = dict(value)
        result["name"] = name
        if IP_KEY in value:
            result[IP_KEY] = self._validate_ipv4(value[IP_KEY])
        return result

    def _validate_ipv4(self, ipv4: Any) -> dict:
        if not isinstance(ipv4, dict):
            raise StoreError(400, "invalid-value", "'ietf-ip:ipv4' debe ser un objeto.",
                             path=IP_KEY)
        for leaf in ipv4:
            if leaf not in IPV4_LEAVES:
                raise StoreError(400, "unknown-element",
                                 f"Elemento desconocido en ietf-ip:ipv4: '{leaf}'.",
                                 path=f"{IP_KEY}/{leaf}")
        out = {k: v for k, v in ipv4.items() if k != "address"}
        if "address" not in ipv4:
            return out
        addresses = ipv4["address"]
        if not isinstance(addresses, list):
            raise StoreError(400, "invalid-value", "'address' debe ser una lista.",
                             path=f"{IP_KEY}/address")
        if len(addresses) > 1:
            raise StoreError(400, "invalid-value",
                             "El simulador admite una sola dirección IPv4 primaria por interfaz.",
                             path=f"{IP_KEY}/address")
        normalized = []
        for item in addresses:
            normalized.append(self._validate_address(item))
        out["address"] = normalized
        return out

    def _validate_address(self, item: Any) -> dict:
        path = f"{IP_KEY}/address"
        if not isinstance(item, dict) or "ip" not in item:
            raise StoreError(400, "missing-element",
                             "Cada dirección requiere la clave 'ip'.", path=path)
        extra = set(item) - {"ip", "prefix-length", "netmask"}
        if extra:
            raise StoreError(400, "unknown-element",
                             f"Elementos desconocidos en la dirección: {sorted(extra)}.",
                             path=path)
        has_prefix = "prefix-length" in item
        has_mask = "netmask" in item
        if has_prefix == has_mask:
            raise StoreError(400, "invalid-value",
                             "Debe indicarse exactamente uno de 'prefix-length' o 'netmask' "
                             "(choice 'subnet' del modelo ietf-ip).", path=path)
        try:
            ip = ipaddress.IPv4Address(str(item["ip"]))
        except ValueError as exc:
            raise StoreError(400, "invalid-value",
                             f"Dirección IPv4 inválida: {item['ip']!r}.", path=path) from exc
        if has_prefix:
            prefix = item["prefix-length"]
            if isinstance(prefix, bool) or not isinstance(prefix, int) or not 0 <= prefix <= 32:
                raise StoreError(400, "invalid-value",
                                 "'prefix-length' debe ser un entero entre 0 y 32.", path=path)
        else:
            if not isinstance(item["netmask"], str):
                raise StoreError(400, "invalid-value", "'netmask' debe ser texto.", path=path)
            prefix = _prefix_from_netmask(item["netmask"])
        if prefix == 0:
            raise StoreError(400, "invalid-value", "Un prefijo /0 no es válido para una interfaz.",
                             path=path)
        if ip.is_multicast or ip.is_unspecified or ip.is_loopback:
            raise StoreError(400, "invalid-value",
                             f"{ip} no es una dirección de host válida para una interfaz.",
                             path=path)
        network = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
        if prefix <= 30 and ip in (network.network_address, network.broadcast_address):
            raise StoreError(400, "invalid-value",
                             f"{ip}/{prefix} corresponde a la dirección de red o de broadcast.",
                             path=path)
        # Se almacena con 'netmask', como lo reporta IOS XE.
        return {"ip": str(ip), "netmask": _netmask_from_prefix(prefix)}

    def _check_overlap(self, name: str, new: dict) -> None:
        mine = _networks(new)
        if not mine:
            return
        for other_name, other in self._config.items():
            if other_name == name:
                continue
            for net in _networks(other):
                for own in mine:
                    if own.overlaps(net):
                        raise StoreError(
                            400, "invalid-value",
                            f"La red {own} se superpone con {net} de la interfaz "
                            f"{other_name}.", path=f"{IP_KEY}/address")


def _networks(entry: dict) -> list[ipaddress.IPv4Network]:
    nets = []
    for addr in entry.get(IP_KEY, {}).get("address", []):
        nets.append(ipaddress.IPv4Network(f"{addr['ip']}/{addr['netmask']}", strict=False))
    return nets
