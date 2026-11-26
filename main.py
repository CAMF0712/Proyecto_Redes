"""Aplicación de administracion de interfaces mediante RESTCONF.

Uso:
    python main.py                 # abre la interfaz gráfica en modo simulador
    python main.py --local         # inicia también el simulador local
    python main.py --modo real     # abre la interfaz en modo RESTCONF real

Sin --local, inicie el simulador en otra terminal:
    python -m simulator.server
"""

from __future__ import annotations

import argparse
import threading

from application.restconf_client import MODE_REAL, MODE_SIM


def main() -> None:
    parser = argparse.ArgumentParser(description="Administrador de interfaces RESTCONF "
                                                 "(CE-5301, TEC).")
    parser.add_argument("--modo", choices=["simulador", "real"], default="simulador",
                        help="Modo inicial de la aplicación.")
    parser.add_argument("--local", action="store_true",
                        help="Iniciar y detener el simulador junto con la aplicación.")
    args = parser.parse_args()

    if args.local and args.modo != "simulador":
        parser.error("--local solo se puede usar en modo simulador")

    from application.dashboard import run  # import diferido: requiere tkinter

    if not args.local:
        run(MODE_REAL if args.modo == "real" else MODE_SIM)
        return

    from werkzeug.serving import make_server
    from simulator.server import create_app

    server = make_server("127.0.0.1", 5000, create_app(), threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        run(MODE_SIM)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


if __name__ == "__main__":
    main()
