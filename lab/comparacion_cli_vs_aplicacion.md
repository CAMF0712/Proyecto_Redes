# Comparación: CLI de Packet Tracer vs. aplicación RESTCONF

## Advertencia

Los dos sistemas **no están conectados ni sincronizados**:

| | Fuente A: Packet Tracer (CLI) | Fuente B: aplicación |
|---|---|---|
| Origen de los datos | Router R1 simulado en Packet Tracer | Simulador RESTCONF local (`simulator/`) **o** dispositivo IOS XE real |
| Cómo se obtienen | `show ip interface brief`, `show running-config` | `GET /restconf/data/ietf-interfaces:interfaces` y `.../interfaces-state` |
| ¿Datos de un router? | Sí (router simulado por Packet Tracer) | Solo en modo **RESTCONF real**; en modo simulador son datos de prueba |
| Sincronización | — | **Ninguna**. Un cambio en un lado no se refleja en el otro |

El conjunto de datos inicial del simulador se diseñó **a imagen** del plan de
direccionamiento de R1 (mismos nombres de interfaz e IPs) para que la
comparación sea didáctica. Las coincidencias son intencionales y manuales, no
resultado de una integración.

## Procedimiento

1. **Packet Tracer:** en R1 ejecutar `show ip interface brief` y
   `show running-config | section interface`. Capturar la pantalla.
2. **Aplicación:** iniciar el simulador (`python -m simulator.server`), abrir
   la GUI (`python main.py`), conectar y pulsar *Actualizar (GET)*. Capturar la
   pantalla (el encabezado naranja identifica el modo simulador).
3. Llenar la tabla siguiente **a mano**, copiando los valores observados.
4. Realizar el mismo cambio en ambos lados (por ejemplo, la descripción de
   G0/0/1): por CLI en Packet Tracer y con *Cambiar descripción* en la
   aplicación. Comparar el procedimiento, el tiempo y la verificación.

## Tabla de comparación (completar)

| Interfaz | Campo | Packet Tracer — R1 (CLI) | Aplicación — modo: ________ | ¿Coinciden? |
|---|---|---|---|---|
| G0/0/0 | IP / prefijo | | | |
| G0/0/0 | Estado administrativo | | | |
| G0/0/0 | Estado operativo | | | |
| G0/0/1 | IP / prefijo | | | |
| G0/0/1 | Descripción | | | |
| G0/0/1 | Estado administrativo | | | |
| G0/0/2 | Estado administrativo | | | |
| Loopback0 | IP / prefijo | | | |

## Equivalencias entre CLI y modelo YANG

| CLI de IOS | Hoja YANG | Módulo |
|---|---|---|
| `description TEXTO` | `interface/description` | ietf-interfaces |
| `shutdown` / `no shutdown` | `interface/enabled` (false / true) | ietf-interfaces |
| `ip address A.B.C.D M.M.M.M` | `interface/ietf-ip:ipv4/address/{ip, netmask}` | ietf-ip |
| Columna *Status* de `show ip interface brief` | `interfaces-state/interface/admin-status` | ietf-interfaces |
| Columna *Protocol* de `show ip interface brief` | `interfaces-state/interface/oper-status` | ietf-interfaces |

## Diferencias esperadas

* El simulador incluye `GigabitEthernet0` (gestión), que es de solo lectura y
  sirve para probar el error **403**. Esa interfaz no forma parte del laboratorio.
* Los contadores de tráfico del simulador son artificiales.
* Un cambio hecho en Packet Tracer **no** aparece en la aplicación, y viceversa.
