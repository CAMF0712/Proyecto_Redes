"""Pruebas de consulta (GET). Requisitos 1 y 2 del plan de pruebas.

Se ejecutan contra el SIMULADOR local; no implican comunicación con un router.
"""

from application.interface_manager import parse_config, summarize
from application.restconf_client import IF_PATH, interface_path


def test_descubrimiento_raiz_restconf(client):
    res = client.discover()
    assert res.ok and res.status == 200
    assert "ietf-restconf:restconf" in res.data


def test_respuestas_identificadas_como_simulador(client):
    res = client.get_interfaces()
    assert res.is_simulator, "Toda respuesta del simulador debe llevar el encabezado X-Simulator"


def test_get_todas_las_interfaces(client):
    """P02: GET /restconf/data/ietf-interfaces:interfaces."""
    res = client.get_interfaces()
    assert res.ok and res.status == 200
    assert res.endpoint == IF_PATH
    lista = res.data["ietf-interfaces:interfaces"]["interface"]
    nombres = {i["name"] for i in lista}
    assert {"GigabitEthernet0/0/0", "GigabitEthernet0/0/1", "GigabitEthernet0/0/2"} <= nombres
    for entrada in lista:
        assert entrada["type"].startswith("iana-if-type:")
        assert isinstance(entrada["enabled"], bool)


def test_get_interfaz_individual_codifica_la_clave(client):
    """P03: la '/' del nombre debe ir codificada como %2F (RFC 8040, 3.5.3)."""
    assert interface_path("GigabitEthernet0/0/1").endswith("interface=GigabitEthernet0%2F0%2F1")
    res = client.get_interface("GigabitEthernet0/0/1")
    assert res.ok and res.status == 200
    entrada = parse_config(res.data)[0]
    assert entrada.name == "GigabitEthernet0/0/1"
    assert entrada.ip == "192.168.10.1" and entrada.prefix == 24


def test_get_estado_operativo(client):
    res = client.get_interfaces_state()
    assert res.ok
    estados = {i["name"]: i for i in res.data["ietf-interfaces:interfaces-state"]["interface"]}
    assert estados["GigabitEthernet0/0/2"]["admin-status"] == "down"
    assert estados["GigabitEthernet0/0/2"]["oper-status"] == "down"
    assert estados["GigabitEthernet0/0/0"]["oper-status"] == "up"


def test_manager_combina_configuracion_y_estado(manager):
    out = manager.fetch_all()
    assert out.ok
    por_nombre = {i.name: i for i in out.interfaces}
    gi0 = por_nombre["GigabitEthernet0/0/0"]
    assert (gi0.ip, gi0.prefix, gi0.admin_status, gi0.oper_status) == ("10.0.12.1", 30, "up", "up")
    assert por_nombre["GigabitEthernet0/0/2"].enabled is False
    resumen = summarize(out.interfaces)
    assert resumen["total"] == len(out.interfaces)
    assert resumen["activas"] + resumen["desactivadas"] == resumen["total"]


def test_parse_acepta_formato_objeto_de_ios_xe():
    """IOS XE devuelve una entrada individual como objeto, no como lista."""
    data = {"ietf-interfaces:interface": {
        "name": "GigabitEthernet1", "type": "iana-if-type:ethernetCsmacd", "enabled": True,
        "ietf-ip:ipv4": {"address": [{"ip": "10.10.20.48", "netmask": "255.255.255.0"}]}}}
    info = parse_config(data)[0]
    assert info.name == "GigabitEthernet1" and info.prefix == 24
