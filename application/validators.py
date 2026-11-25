"""Validaciones del lado del cliente.

Se ejecutan ANTES de enviar una solicitud para evitar cambios inválidos. El
servidor (dispositivo real o simulador) vuelve a validar: estas funciones no
reemplazan la validación del dispositivo.
"""

from __future__ import annotations

import ipaddress
import re

MAX_DESCRIPTION = 200  # limite de Cisco IOS / IOS XE para 'description'
_HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
                          r"(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
_IFNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9/.:\- ]{0,63}$")


class ValidationError(ValueError):
    """Dato ingresado por el usuario que no cumple las reglas."""


def validate_host(host: str) -> str:
    host = (host or "").strip()
    if not host:
        raise ValidationError("Debe indicar la dirección IP o el nombre del servidor.")
    try:
        ipaddress.ip_address(host.strip("[]"))
        return host.strip("[]")
    except ValueError:
        pass
    if not _HOSTNAME_RE.match(host):
        raise ValidationError(f"'{host}' no es una dirección IP ni un nombre de host válido.")
    return host


def validate_port(port: str | int) -> int:
    try:
        value = int(str(port).strip())
    except ValueError as exc:
        raise ValidationError("El puerto debe ser un número entero.") from exc
    if not 1 <= value <= 65535:
        raise ValidationError("El puerto debe estar entre 1 y 65535.")
    return value


def validate_timeout(timeout: str | float) -> float:
    try:
        value = float(str(timeout).strip())
    except ValueError as exc:
        raise ValidationError("El tiempo de espera debe ser numérico (segundos).") from exc
    if not 0.5 <= value <= 120:
        raise ValidationError("El tiempo de espera debe estar entre 0.5 y 120 segundos.")
    return value


def validate_credentials(username: str, password: str) -> None:
    if not (username or "").strip():
        raise ValidationError("Debe indicar el usuario.")
    if not password:
        raise ValidationError("Debe indicar la contraseña.")


def validate_interface_name(name: str) -> str:
    name = (name or "").strip()
    if not _IFNAME_RE.match(name):
        raise ValidationError(f"Nombre de interfaz inválido: '{name}'.")
    return name


def validate_description(text: str) -> str:
    if text is None:
        raise ValidationError("La descripción no puede ser nula.")
    text = text.strip()
    if len(text) > MAX_DESCRIPTION:
        raise ValidationError(
            f"La descripción tiene {len(text)} caracteres; el máximo es {MAX_DESCRIPTION}.")
    if any(ord(c) < 32 for c in text):
        raise ValidationError("La descripción contiene caracteres de control no permitidos.")
    return text


def validate_prefix(prefix: str | int) -> int:
    try:
        value = int(str(prefix).strip().lstrip("/"))
    except ValueError as exc:
        raise ValidationError("El prefijo debe ser un número entero (por ejemplo 24).") from exc
    if not 1 <= value <= 32:
        raise ValidationError("El prefijo debe estar entre 1 y 32.")
    return value


def validate_ipv4_host(ip: str, prefix: str | int) -> tuple[str, int]:
    """Valida que ``ip/prefix`` sea una dirección de host utilizable."""
    pfx = validate_prefix(prefix)
    try:
        addr = ipaddress.IPv4Address((ip or "").strip())
    except ValueError as exc:
        raise ValidationError(f"'{ip}' no es una dirección IPv4 válida.") from exc
    if addr.is_multicast or addr.is_unspecified or addr.is_loopback or addr.is_reserved:
        raise ValidationError(f"{addr} no es una dirección de host válida para una interfaz.")
    net = ipaddress.IPv4Network(f"{addr}/{pfx}", strict=False)
    if pfx <= 30 and addr in (net.network_address, net.broadcast_address):
        raise ValidationError(f"{addr}/{pfx} es la dirección de red o de broadcast de {net}.")
    return str(addr), pfx


def prefix_to_netmask(prefix: int) -> str:
    return str(ipaddress.IPv4Network(f"0.0.0.0/{validate_prefix(prefix)}").netmask)


def netmask_to_prefix(netmask: str) -> int:
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
    except ValueError as exc:
        raise ValidationError(f"Máscara inválida o no contigua: '{netmask}'.") from exc
