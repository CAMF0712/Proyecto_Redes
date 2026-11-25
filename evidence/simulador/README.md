# Evidencias del simulador RESTCONF

> **SIMULADO: generado contra el simulador RESTCONF local. No es comunicación con un router real ni con Packet Tracer.**

Generado: 2026-11-25T13:25:37-06:00 con `python scripts/generar_evidencias.py`.

## Solicitudes y respuestas

| # | Escenario | Método | Código HTTP | Tiempo (ms) | Archivo |
|---|---|---|---|---|---|
| 1 | P02 Consulta GET de todas las interfaces | GET | 200 | 7.56 | [`01_get_interfaces.json`](01_get_interfaces.json) |
| 2 | P03 Consulta de una interfaz individual | GET | 200 | 2.72 | [`02_get_interfaz_individual.json`](02_get_interfaz_individual.json) |
| 3 | Consulta del estado operativo (interfaces-state) | GET | 200 | 2.19 | [`03_get_estado_operativo.json`](03_get_estado_operativo.json) |
| 4 | P04 Modificación de la descripción mediante PATCH | PATCH | 204 | 2.43 | [`04_patch_descripcion.json`](04_patch_descripcion.json) |
| 5 | P05 Consulta posterior para comprobar el cambio | GET | 200 | 2.58 | [`05_get_verificacion.json`](05_get_verificacion.json) |
| 6 | P06 Interfaz inexistente | GET | 404 | 1.71 | [`06_error_404_interfaz_inexistente.json`](06_error_404_interfaz_inexistente.json) |
| 7 | P07 Autenticación incorrecta | GET | 401 | 1.84 | [`07_error_401_credenciales.json`](07_error_401_credenciales.json) |
| 8 | P08 Solicitud inválida (JSON mal formado) | PATCH | 400 | 1.65 | [`08_error_400_json_malformado.json`](08_error_400_json_malformado.json) |
| 9 | P08 Solicitud inválida (IP fuera del modelo, no se aplica) | PATCH | 400 | 1.9 | [`09_error_400_no_cumple_modelo.json`](09_error_400_no_cumple_modelo.json) |
| 10 | Interfaz protegida (403) | PATCH | 403 | 1.8 | [`10_error_403_interfaz_protegida.json`](10_error_403_interfaz_protegida.json) |
| 11 | Método no permitido (405) | DELETE | 405 | 1.88 | [`11_error_405_metodo.json`](11_error_405_metodo.json) |
| 12 | Error interno inyectado (500) | GET | 500 | 2.05 | [`12_error_500_inyectado.json`](12_error_500_inyectado.json) |
| 13 | Cambio de IP con PUT (entrada completa) | PUT | 204 | 1.97 | [`13_put_cambio_ip.json`](13_put_cambio_ip.json) |

## Tiempos de respuesta

Medidos contra el simulador en el mismo equipo (127.0.0.1), con una solicitud de calentamiento descartada. **No representan el tiempo de respuesta de un router real**, que incluye latencia de red, TLS y el procesamiento del dispositivo.

| Operación | n | Promedio | Mediana | Desv. est. | Mín | P95 | Máx |
|---|---|---|---|---|---|---|---|
| GET interfaces | 50 | 2.07 | 2.03 | 0.37 | 1.39 | 2.69 | 3.18 |
| GET interfaz individual | 50 | 2.11 | 1.96 | 0.8 | 1.58 | 2.36 | 7.43 |
| PATCH descripción | 50 | 2.24 | 2.27 | 0.4 | 1.56 | 2.81 | 3.38 |
| Cambio completo (PATCH + GET de verificación) | 50 | 4.41 | 4.45 | 0.51 | 3.33 | 5.09 | 5.57 |

Valores en milisegundos. Datos crudos: [`tiempos_respuesta.csv`](tiempos_respuesta.csv).

## Registro de operaciones de la aplicación

[`registro_operaciones.jsonl`](registro_operaciones.jsonl) y [`registro_operaciones.csv`](registro_operaciones.csv): flujo ejecutado con el cliente de la aplicación. Ninguno contiene contraseñas.
