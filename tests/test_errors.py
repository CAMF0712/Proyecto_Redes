"""Pruebas de manejo de errores. Requisitos 5, 6 y 7 del plan de pruebas,
además de 403, 405, 415, 500, timeout, falta de conectividad y respuestas
malformadas. Se ejecutan contra el SIMULADOR.
"""

import socket

import pytest

from application import validators as v
from application.interface_manager import InterfaceManager
from application.restconf_client import MODE_SIM, RestconfClient, interface_path

IFACE = "GigabitEthernet0/0/1"


def test_interfaz_inexistente_404(client, manager):
    """P06."""
    res = client.get_interface("GigabitEthernet9/9/9")
    assert not res.ok and res.status == 404 and res.error_kind == "http"
    assert "no existe" in res.error
    info, cfg, _ = manager.fetch_one("GigabitEthernet9/9/9")
    assert info is None and cfg.status == 404


def test_credenciales_incorrectas_401(sim_server, op_logger):
    """P07."""
    c = RestconfClient(sim_server["host"], sim_server["port"], "admin", "clave-incorrecta",
                       use_https=False, mode=MODE_SIM, logger=op_logger)
    res = c.get_interfaces()
    assert res.status == 401 and not res.ok
    assert "contraseña" in res.error
    assert "clave-incorrecta" not in op_logger.log_file.read_text(encoding="utf-8")


def test_json_mal_formado_400(client):
    """P08 (solicitud inválida): cuerpo que no es JSON."""
    res = client.request("PATCH", interface_path(IFACE),
                         raw_body='{"ietf-interfaces:interface": [{"name": ')
    assert res.status == 400
    assert "JSON mal formado" in res.error


def test_cuerpo_que_no_cumple_el_modelo_400_y_no_aplica_cambios(client):
    antes = client.get_interface(IFACE).data
    cuerpo = {"ietf-interfaces:interface": [{"name": IFACE, "enabled": "si"}]}
    res = client.patch_interface(IFACE, cuerpo)
    assert res.status == 400 and "booleano" in res.error
    assert client.get_interface(IFACE).data == antes


@pytest.mark.parametrize("cuerpo, fragmento", [
    ({"ietf-interfaces:interface": [{"name": IFACE, "ietf-ip:ipv4": {
        "address": [{"ip": "300.1.1.1", "prefix-length": 24}]}}]}, "IPv4 inválida"),
    ({"ietf-interfaces:interface": [{"name": IFACE, "ietf-ip:ipv4": {
        "address": [{"ip": "192.168.10.0", "prefix-length": 24}]}}]}, "red o de broadcast"),
    ({"ietf-interfaces:interface": [{"name": IFACE, "ietf-ip:ipv4": {
        "address": [{"ip": "10.0.12.2", "prefix-length": 30}]}}]}, "se superpone"),
    ({"ietf-interfaces:interface": [{"name": "OtraInterfaz", "description": "x"}]}, "no coincide"),
    ({"ietf-interfaces:interface": [{"name": IFACE, "oper-status": "up"}]}, "solo lectura"),
    ({"ietf-interfaces:interface": [{"name": IFACE, "color": "azul"}]}, "desconocido"),
])
def test_validaciones_del_modelo_en_el_servidor(client, cuerpo, fragmento):
    res = client.patch_interface(IFACE, cuerpo)
    assert res.status == 400
    assert fragmento in res.error


def test_put_sin_hoja_obligatoria_type_400(client):
    res = client.put_interface(IFACE, {"ietf-interfaces:interface": [{"name": IFACE}]})
    assert res.status == 400 and "type" in res.error


def test_interfaz_protegida_403(client):
    res = client.patch_interface("GigabitEthernet0", {"ietf-interfaces:interface": [
        {"name": "GigabitEthernet0", "enabled": False}]})
    assert res.status == 403


def test_metodo_no_permitido_405(client):
    res = client.request("DELETE", interface_path(IFACE))
    assert res.status == 405
    assert "PATCH" in res.headers.get("Allow", "")


def test_content_type_incorrecto_415(client):
    res = client.request("PATCH", interface_path(IFACE), raw_body="{}",
                         content_type="application/xml")
    assert res.status == 415


def test_error_interno_500(client, inject_fault):
    inject_fault("error500")
    res = client.get_interfaces()
    assert res.status == 500 and res.error_kind == "http"
    assert client.get_interfaces().ok  # el fallo inyectado es de una sola vez


def test_timeout(sim_server, inject_fault):
    inject_fault("delay", delay_seconds=2)
    c = RestconfClient(sim_server["host"], sim_server["port"], "admin", "admin123",
                       use_https=False, timeout=0.5, mode=MODE_SIM)
    res = c.get_interfaces()
    assert not res.ok and res.status is None and res.error_kind == "timeout"


def test_sin_conectividad():
    with socket.socket() as s:  # puerto libre en el que nadie escucha
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    # En Windows, la conexion a un puerto cerrado se reintenta durante ~2 s
    # antes de ser rechazada; el tiempo de espera debe ser mayor que eso para
    # que el error se clasifique como falta de conectividad y no como timeout.
    c = RestconfClient("127.0.0.1", puerto, "admin", "x", use_https=False, timeout=10)
    res = c.discover()
    assert not res.ok and res.error_kind == "connection"


def test_respuesta_malformada(client, manager, inject_fault):
    inject_fault("malformed")
    res = client.get_interfaces()
    assert not res.ok and res.error_kind == "malformed"
    inject_fault("malformed")
    out = manager.fetch_all()
    assert not out.ok and "malformada" in out.error


def test_estructura_inesperada_se_reporta(sim_server):
    class FalsoCliente:
        def get_interfaces(self):
            from application.restconf_client import RestconfResult
            return RestconfResult(True, "GET", "/x", 200, 1.0, {"otra": "cosa"})
    out = InterfaceManager(FalsoCliente()).fetch_all()
    assert not out.ok and "malformada" in out.error


@pytest.mark.parametrize("ip, prefijo", [
    ("192.168.1.256", 24), ("192.168.1.0", 24), ("224.0.0.5", 24), ("10.0.0.1", 33),
    ("abc", 24),
])
def test_validacion_local_evita_solicitudes_invalidas(manager, ip, prefijo):
    with pytest.raises(v.ValidationError):
        manager.plan_ipv4(IFACE, ip, prefijo)


def test_descripcion_demasiado_larga_se_rechaza_localmente(manager):
    with pytest.raises(v.ValidationError):
        manager.plan_description(IFACE, "x" * 201)
