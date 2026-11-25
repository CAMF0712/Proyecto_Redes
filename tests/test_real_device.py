"""Pruebas contra un DISPOSITIVO RESTCONF REAL.

Se OMITEN automáticamente si no se definen las variables de entorno:

    RESTCONF_HOST      dirección del dispositivo (obligatoria)
    RESTCONF_PORT      puerto (por defecto 443)
    RESTCONF_USER      usuario
    RESTCONF_PASS      contraseña
    RESTCONF_VERIFY    "true" (por defecto), "false" o ruta a un certificado CA
    RESTCONF_IFACE     interfaz a consultar (por defecto la primera de la lista)
    RESTCONF_ALLOW_WRITE  "1" para permitir la prueba de escritura (PATCH de la
                          descripción, que luego se restaura)

Ejemplo (PowerShell):
    $env:RESTCONF_HOST="10.10.20.48"; $env:RESTCONF_USER="developer"
    $env:RESTCONF_PASS="..."; $env:RESTCONF_VERIFY="false"
    python -m pytest tests/test_real_device.py -v
"""

import os

import pytest

from application.interface_manager import InterfaceManager
from application.restconf_client import MODE_REAL, RestconfClient

HOST = os.environ.get("RESTCONF_HOST")

pytestmark = pytest.mark.skipif(
    not HOST, reason="No hay dispositivo RESTCONF real configurado (RESTCONF_HOST).")


def _verify():
    value = os.environ.get("RESTCONF_VERIFY", "true")
    if value.lower() == "false":
        return False
    if value.lower() == "true":
        return True
    return value


@pytest.fixture(scope="module")
def real_client():
    c = RestconfClient(HOST, int(os.environ.get("RESTCONF_PORT", "443")),
                       os.environ.get("RESTCONF_USER", ""), os.environ.get("RESTCONF_PASS", ""),
                       use_https=True, verify=_verify(), timeout=20, mode=MODE_REAL)
    yield c
    c.close()


def test_real_descubrimiento(real_client):
    res = real_client.discover()
    assert res.ok, res.error
    assert not res.is_simulator, "La respuesta proviene del simulador, no de un dispositivo real"


def test_real_get_interfaces(real_client):
    out = InterfaceManager(real_client).fetch_all()
    assert out.ok, out.error
    assert out.interfaces


def test_real_get_interfaz_individual(real_client):
    manager = InterfaceManager(real_client)
    nombre = os.environ.get("RESTCONF_IFACE") or manager.fetch_all().interfaces[0].name
    info, cfg, _ = manager.fetch_one(nombre)
    assert cfg.ok, cfg.error
    assert info.name == nombre


def test_real_interfaz_inexistente(real_client):
    res = real_client.get_interface("NoExiste99/99")
    assert res.status in (400, 404)


@pytest.mark.skipif(os.environ.get("RESTCONF_ALLOW_WRITE") != "1",
                    reason="Escritura deshabilitada (RESTCONF_ALLOW_WRITE != 1).")
def test_real_patch_descripcion_y_restauracion(real_client):
    manager = InterfaceManager(real_client)
    nombre = os.environ.get("RESTCONF_IFACE")
    assert nombre, "Defina RESTCONF_IFACE para la prueba de escritura"
    original, _, _ = manager.fetch_one(nombre)
    try:
        out = manager.apply(manager.plan_description(nombre, "Prueba CE-5301 RESTCONF"))
        assert out.verified, out.apply_result.error or out.mismatches
    finally:
        manager.apply(manager.plan_description(nombre, original.description))
