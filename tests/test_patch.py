"""Pruebas de modificación (PATCH / PUT), verificación y registro.

Requisitos 3, 4 y 8 del plan de pruebas. Se ejecutan contra el SIMULADOR.
"""

import json

from application.restconf_client import interface_path

IFACE = "GigabitEthernet0/0/1"


def test_plan_muestra_la_solicitud_exacta(manager):
    plan = manager.plan_description(IFACE, "LAN de usuarios - piso 2")
    assert plan.method == "PATCH"
    assert plan.endpoint == interface_path(IFACE)
    assert plan.body == {"ietf-interfaces:interface": [
        {"name": IFACE, "description": "LAN de usuarios - piso 2"}]}


def test_patch_descripcion_y_verificacion_con_get(manager, client):
    """P04 + P05: PATCH de la descripción y GET posterior que confirma el cambio."""
    nueva = "LAN de usuarios - modificada por RESTCONF"
    outcome = manager.apply(manager.plan_description(IFACE, nueva))
    assert outcome.apply_result.status == 204
    assert outcome.verify_result is not None and outcome.verify_result.method == "GET"
    assert outcome.verified, outcome.mismatches
    # Consulta independiente adicional.
    res = client.get_interface(IFACE)
    assert res.data["ietf-interfaces:interface"][0]["description"] == nueva


def test_patch_no_altera_otras_hojas(manager, client):
    antes = client.get_interface(IFACE).data["ietf-interfaces:interface"][0]
    manager.apply(manager.plan_description(IFACE, "solo cambia esto"))
    despues = client.get_interface(IFACE).data["ietf-interfaces:interface"][0]
    assert despues["ietf-ip:ipv4"] == antes["ietf-ip:ipv4"]
    assert despues["enabled"] == antes["enabled"]


def test_deshabilitar_y_habilitar_interfaz(manager):
    out = manager.apply(manager.plan_enabled(IFACE, False))
    assert out.verified
    info, _, _ = manager.fetch_one(IFACE)
    assert info.admin_status == "down" and info.oper_status == "down"
    out = manager.apply(manager.plan_enabled(IFACE, True))
    assert out.verified
    info, _, _ = manager.fetch_one(IFACE)
    assert info.admin_status == "up" and info.oper_status == "up"


def test_put_cambia_direccion_ip(manager):
    plan, lectura = manager.plan_ipv4(IFACE, "192.168.11.1", 25)
    assert lectura.ok and plan.method == "PUT"
    entrada = plan.body["ietf-interfaces:interface"][0]
    assert entrada["ietf-ip:ipv4"]["address"] == [{"ip": "192.168.11.1",
                                                    "netmask": "255.255.255.128"}]
    assert entrada["description"]  # PUT conserva el resto de la configuración
    out = manager.apply(plan)
    assert out.apply_result.status == 204 and out.verified
    assert out.after.ip_cidr == "192.168.11.1/25"


def test_registro_de_operaciones_sin_contrasenas(manager, op_logger):
    """P08: cada operación queda registrada con los campos requeridos."""
    manager.fetch_all()
    manager.apply(manager.plan_description(IFACE, "registro"))
    manager.client.get_interface("NoExiste")
    entradas = op_logger.entries
    assert len(entradas) >= 5
    for e in entradas:
        assert e.fecha and e.operacion and e.metodo and e.endpoint
        assert e.resultado.startswith(("OK", "ERROR"))
        assert e.tiempo_ms >= 0
    metodos = [e.metodo for e in entradas]
    assert "PATCH" in metodos and "GET" in metodos
    assert any(e.codigo_http == 404 for e in entradas)
    contenido = op_logger.log_file.read_text(encoding="utf-8")
    assert "admin123" not in contenido
    assert "Authorization" not in contenido
    for linea in contenido.splitlines():
        json.loads(linea)  # formato JSON Lines válido


def test_exportar_historial_csv(manager, op_logger, tmp_path):
    manager.fetch_all()
    destino = op_logger.export_csv(tmp_path / "historial.csv")
    texto = destino.read_text(encoding="utf-8-sig")
    assert texto.splitlines()[0] == "fecha,modo,operacion,metodo,endpoint,codigo_http,resultado,tiempo_ms"
    assert "admin123" not in texto
