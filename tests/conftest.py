"""Fixtures compartidas.

Las pruebas de los archivos test_get, test_patch y test_errors levantan el
SIMULADOR en un hilo, en un puerto libre de 127.0.0.1, y se comunican con el
por HTTP real usando el mismo cliente que la aplicación grafica. No requieren
ningún dispositivo de red.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.interface_manager import InterfaceManager  # noqa: E402
from application.operation_log import OperationLogger  # noqa: E402
from application.restconf_client import MODE_SIM, RestconfClient  # noqa: E402
from simulator.server import create_app  # noqa: E402

SIM_USER = "admin"
SIM_PASS = "admin123"


@pytest.fixture(scope="session")
def sim_server():
    app = create_app(enable_faults=True, user=SIM_USER, password=SIM_PASS)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"app": app, "host": "127.0.0.1", "port": server.server_port}
    server.shutdown()


@pytest.fixture(autouse=True)
def _reset_simulator(request):
    """Restaura los datos del simulador antes de cada prueba que lo use."""
    if "sim_server" in request.fixturenames:
        app = request.getfixturevalue("sim_server")["app"]
        app.config["STORE"].reset()
        app.config["FAULTS"].clear()
    yield


@pytest.fixture
def op_logger(tmp_path):
    return OperationLogger(tmp_path / "operaciones.jsonl")


@pytest.fixture
def client(sim_server, op_logger):
    c = RestconfClient(sim_server["host"], sim_server["port"], SIM_USER, SIM_PASS,
                       use_https=False, timeout=5, mode=MODE_SIM, logger=op_logger)
    yield c
    c.close()


@pytest.fixture
def manager(client):
    return InterfaceManager(client)


@pytest.fixture
def inject_fault(sim_server):
    def _inject(kind: str, **kwargs):
        sim_server["app"].config["FAULTS"].update({"kind": kind, "count": 1, **kwargs})
    return _inject
