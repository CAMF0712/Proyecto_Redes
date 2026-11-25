# Prueba de compatibilidad RESTCONF en Packet Tracer

**Fecha:** 25 de noviembre de 2026
**Software:** Cisco Packet Tracer 9.0.1 (Windows)
**Objetivo:** determinar si algún router del simulador permite habilitar las
interfaces programables necesarias para el proyecto (RESTCONF / NETCONF).

## Procedimiento

1. Se colocaron un router **ISR4331** y un router **2901**.
2. En cada uno se respondió `no` al diálogo inicial y se ingresó a modo de
   configuración global (`enable`, `configure terminal`).
3. Se ejecutaron los cuatro comandos necesarios en un IOS XE real:

```
restconf
netconf-yang
ip http secure-server
ip http server
```

4. En el ISR4331 se ejecutó además `show version` para registrar la versión.

## Resultado observado

| Comando | ISR4331 | 2901 |
|---|---|---|
| `restconf` | `% Invalid input detected at '^' marker.` | `% Invalid input detected at '^' marker.` |
| `netconf-yang` | `% Invalid input detected at '^' marker.` | `% Invalid input detected at '^' marker.` |
| `ip http secure-server` | `% Invalid input detected at '^' marker.` | `% Invalid input detected at '^' marker.` |
| `ip http server` | `% Invalid input detected at '^' marker.` | `% Invalid input detected at '^' marker.` |

`show version` del ISR4331 en Packet Tracer:

```
Cisco IOS Software [Everest], ISR Software (X86_64_LINUX_IOSD-UNIVERSALK9-M), Version 16.6.4, RELEASE SOFTWARE (fc3)
System image file is "bootflash:isr4300-universalk9.16.06.04.SPA.bin"
```

La prueba se repitió en R1 de la topología final (ISR4331 ya configurado y
con OSPF activo) con el mismo resultado; ver
[`../evidence/packet_tracer/salidas_cli.md`](../evidence/packet_tracer/salidas_cli.md).

## Interpretación

* Packet Tracer **no implementa** RESTCONF, NETCONF ni el servidor HTTP/HTTPS
  en sus routers.
* La limitación es del simulador, no del modelo de router: el ISR4331 reporta
  IOS XE 16.6.4, y en hardware real Cisco documenta RESTCONF para la serie
  ISR 4000 a partir de IOS XE 16.3
  (<https://developer.cisco.com/site/standard-network-devices/>).
* Se evaluó también el *Network Controller* de Packet Tracer, que expone una
  API REST hacia el equipo anfitrión. Se descartó porque esa API es propia del
  controlador: no sigue el RFC 8040 ni usa modelos YANG.

## Pendiente para el equipo

Repetir la prueba en su propia instancia de Packet Tracer y guardar las capturas
como evidencia:

- `evidence/packet_tracer/restconf_rechazado_ISR4331.png`
- `evidence/packet_tracer/restconf_rechazado_2901.png`
- `evidence/packet_tracer/show_version_ISR4331.png`

> Nota práctica: si un comando mal escrito se interpreta como nombre de host,
> el router intenta resolverlo por DNS y se queda esperando. Se cancela con
> **Ctrl+Shift+6**. Las configuraciones del laboratorio incluyen
> `no ip domain-lookup` para evitarlo.
