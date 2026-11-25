# Evidencias

| Carpeta | Origen | ¿Datos reales de un router? |
|---|---|---|
| [`simulador/`](simulador/) | `scripts/generar_evidencias.py` contra el simulador local | **No — simulados** |
| [`pruebas/`](pruebas/) | `python -m pytest -v` | **No — simulados** (las pruebas del dispositivo real se omiten) |
| [`gui/`](gui/) | Capturas de la aplicación en modo simulador | **No — simulados** |
| [`pyang/`](pyang/) | Validación de los modelos YANG | No aplica |
| [`packet_tracer/`](packet_tracer/) | Salidas de la CLI de la topología (`salidas_cli.md`); faltan capturas de pantalla | Sí: routers simulados por Packet Tracer |

Las capturas de `gui/` se generaron en Linux; conviene repetirlas en Windows para el informe.
