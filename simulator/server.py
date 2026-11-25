"""Punto de entrada del SIMULADOR RESTCONF local.

Uso (desde la raíz del proyecto):
    python -m simulator.server
    python -m simulator.server --port 5000 --enable-faults
    python -m simulator.server --tls          # HTTPS con certificado autofirmado

Credenciales por defecto: admin / admin123 (cambiar con las variables de
entorno SIM_USER y SIM_PASS).

Este servidor NO es un router y no se comunica con Packet Tracer.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from flask import Flask

from .data_store import InterfaceStore
from .routes import bp, register_error_handlers

BANNER = r"""
================================================================
  SIMULADOR RESTCONF - CE-5301 Redes de Computadoras (TEC)
  ATENCIÓN: este servidor es una SIMULACIÓN local.
  Los datos NO provienen de un router real ni de Packet Tracer.
================================================================
"""


def create_app(data_file: str | Path | None = None, enable_faults: bool = False,
               user: str | None = None, password: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["STORE"] = InterfaceStore(data_file)
    app.config["SIM_USER"] = user or os.environ.get("SIM_USER", "admin")
    app.config["SIM_PASS"] = password or os.environ.get("SIM_PASS", "admin123")
    app.config["ENABLE_FAULTS"] = enable_faults
    app.config["FAULTS"] = {}
    app.json.ensure_ascii = False
    app.register_blueprint(bp)
    register_error_handlers(app)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador local de una API RESTCONF "
                                                 "(ietf-interfaces).")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Dirección de escucha (por defecto solo el equipo local).")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--data", default=None, help="Archivo JSON con los datos iniciales.")
    parser.add_argument("--tls", action="store_true",
                        help="Servir por HTTPS con un certificado autofirmado temporal "
                             "(requiere el paquete 'cryptography').")
    parser.add_argument("--enable-faults", action="store_true",
                        help="Habilita POST /simulator/fault para inyectar errores 500, "
                             "demoras y respuestas malformadas.")
    args = parser.parse_args()

    app = create_app(args.data, args.enable_faults)
    scheme = "https" if args.tls else "http"
    print(BANNER)
    print(f"  URL base:     {scheme}://{args.host}:{args.port}/restconf")
    print(f"  Usuario:      {app.config['SIM_USER']}  (contraseña definida por SIM_PASS)")
    print(f"  Fallos:       {'habilitados' if args.enable_faults else 'deshabilitados'}")
    print("  Detener:      Ctrl+C\n")
    app.run(host=args.host, port=args.port, threaded=True,
            ssl_context="adhoc" if args.tls else None)


if __name__ == "__main__":
    main()
