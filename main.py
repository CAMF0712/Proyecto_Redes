"""Aplicación de administracion de interfaces mediante RESTCONF.

Uso:
    python main.py                 # abre la interfaz gráfica en modo simulador
    python main.py --modo real     # abre la interfaz en modo RESTCONF real

Antes de usar el modo simulador, inicie el simulador en otra terminal:
    python -m simulator.server
"""

from __future__ import annotations

import argparse

from application.restconf_client import MODE_REAL, MODE_SIM


def main() -> None:
    parser = argparse.ArgumentParser(description="Administrador de interfaces RESTCONF "
                                                 "(CE-5301, TEC).")
    parser.add_argument("--modo", choices=["simulador", "real"], default="simulador",
                        help="Modo inicial de la aplicación.")
    args = parser.parse_args()

    from application.dashboard import run  # import diferido: requiere tkinter

    run(MODE_REAL if args.modo == "real" else MODE_SIM)


if __name__ == "__main__":
    main()
