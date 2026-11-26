# Comparación: CLI de Packet Tracer vs. aplicación RESTCONF

**Fecha:** 26 de noviembre de 2026 · **Realizada por:** César Andrés Mora Fajardo

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

1. **Packet Tracer:** abrir `lab/topologia_ce5301.pkt`, entrar a R1
   (`enable`, contraseña `class`) y ejecutar `show ip interface brief` y
   `show running-config` (avanzar con la barra espaciadora hasta la sección de
   interfaces). Capturar la pantalla.
2. **Aplicación:** iniciar el simulador (`python -m simulator.server`), abrir
   la GUI (`python main.py`), conectar y pulsar *Actualizar (GET)*. Capturar la
   pantalla (el encabezado naranja identifica el modo simulador).
3. Llenar la tabla siguiente **a mano**, copiando los valores observados.
4. Realizar el mismo cambio en ambos lados (la descripción de G0/0/1): por CLI
   en Packet Tracer y con *Cambiar descripción* en la aplicación. Comparar el
   procedimiento, el tiempo y la verificación.

## Tabla de comparación

| Interfaz | Campo | Packet Tracer — R1 (CLI) | Aplicación — modo: Simulador local | ¿Coinciden? |
|---|---|---|---|---|
| G0/0/0 | IP / prefijo | `10.0.12.1/30 (10.0.12.1 255.255.255.252)` | `10.0.12.1` · `/30` | Sí |
| G0/0/0 | Estado administrativo | `up (no shutdown, habilitada)` | `up` | Sí |
| G0/0/0 | Estado operativo | `up (Protocol up, vecino OSPF 2.2.2.2 FULL)` | `up` | Sí |
| G0/0/1 | IP / prefijo | `192.168.10.1/24 (192.168.10.1 255.255.255.0)` | `192.168.10.1` · `/24` | Sí |
| G0/0/1 | Descripción | `LAN1 - red de usuarios` | `LAN1 - red de usuarios` | Sí |
| G0/0/1 | Estado administrativo | `up (no shutdown, habilitada)` | `up` | Sí |
| G0/0/2 | Estado administrativo | `administratively down (shutdown, deshabilitada)` | `down` (`enabled: false`) | Sí (equivalente) |
| Loopback0 | IP / prefijo | `1.1.1.1/32 (1.1.1.1 255.255.255.255)` | `1.1.1.1` · `/32` | Sí |

**Resultado:** los 8 campos comparados coinciden. Esto confirma que el
conjunto de datos del simulador reproduce correctamente el plan de R1. **No**
demuestra comunicación entre la aplicación y Packet Tracer: los valores
coinciden porque se copiaron manualmente al diseñar el simulador.

## Mismo cambio en ambos lados: descripción de G0/0/1

| Aspecto | Packet Tracer (CLI) | Aplicación (RESTCONF, simulador) |
|---|---|---|
| Pasos | `configure terminal` → `interface GigabitEthernet0/0/1` → `description Cambio por CLI` → `end` → `show running-config` | Seleccionar la interfaz → *Cambiar descripción* → escribir el texto → *Aceptar* → *Confirmar y enviar* |
| Cantidad | 5 comandos (después de `enable`) | 4 clics + escribir el texto |
| Solicitud enviada | Comandos de texto por consola | `PATCH` a `/restconf/data/ietf-interfaces:interfaces/interface=GigabitEthernet0%2F0%2F1` (HTTP 204) |
| Confirmación previa | No | Sí: muestra método, endpoint y JSON antes de enviar |
| Verificación | Manual, leyendo `show running-config` | Automática: `GET` posterior (HTTP 200) que compara el valor esperado |
| Registro | No queda registro estructurado | Historial con fecha, método, endpoint, código HTTP y tiempo |
| Tiempo estimado de operación (no medido) | ≈ 30–45 s (escribir 5 comandos y revisar la salida de `show running-config`) | ≈ 10–15 s (4 clics, escribir el texto y leer la confirmación) |
| Tiempo de respuesta del servidor (medido) | — | 4,41 ms en promedio para PATCH + GET de verificación (50 repeticiones contra el simulador local; ver `evidence/simulador/README.md`) |

> Los tiempos de operación son **estimaciones** del tiempo que tarda una persona
> en completar cada procedimiento; no se cronometraron. El tiempo de respuesta
> del servidor sí es una medición real, hecha contra el simulador local, y no
> representa el de un router real.

Ambos cambios se aplicaron, cada uno en su propio sistema: la descripción
cambiada por CLI no aparece en la aplicación, y la cambiada en la aplicación
no aparece en Packet Tracer, lo que confirma que no hay sincronización.

## Equivalencias entre CLI y modelo YANG

| CLI de IOS | Hoja YANG | Módulo |
|---|---|---|
| `description TEXTO` | `interface/description` | ietf-interfaces |
| `shutdown` / `no shutdown` | `interface/enabled` (false / true) | ietf-interfaces |
| `ip address A.B.C.D M.M.M.M` | `interface/ietf-ip:ipv4/address/{ip, netmask}` | ietf-ip |
| Columna *Status* de `show ip interface brief` | `interfaces-state/interface/admin-status` | ietf-interfaces |
| Columna *Protocol* de `show ip interface brief` | `interfaces-state/interface/oper-status` | ietf-interfaces |

## Diferencias observadas

* El simulador incluye `GigabitEthernet0` (gestión), que es de solo lectura y
  sirve para probar el error **403**. Esa interfaz no forma parte del laboratorio.
* La CLI muestra la máscara en notación decimal (`255.255.255.0`) y la
  aplicación muestra el prefijo (`/24`); el simulador guarda `netmask`, como
  IOS XE, y la aplicación lo convierte.
* La CLI distingue `administratively down` de `down`; en el modelo YANG la
  primera corresponde a `enabled: false` / `admin-status: down`.
* Los contadores de tráfico del simulador son artificiales.
* Un cambio hecho en Packet Tracer **no** aparece en la aplicación, y viceversa.