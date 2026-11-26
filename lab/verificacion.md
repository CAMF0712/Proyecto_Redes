# Verificación del laboratorio (CLI de Packet Tracer)

Este documento indica **qué comandos ejecutar y qué observar**. Las salidas
reales obtenidas el 25/11/2026 están en
[`../evidence/packet_tracer/salidas_cli.md`](../evidence/packet_tracer/salidas_cli.md);
las capturas de pantalla van en `evidence/packet_tracer/`.

## 1. Estado de interfaces — `show ip interface brief`

Ejecutar en R1, R2 y R3 (modo `Router#`).

| Router | Interfaz | IP esperada | Status / Protocol esperado |
|---|---|---|---|
| R1 | GigabitEthernet0/0/0 | 10.0.12.1 | up / up |
| R1 | GigabitEthernet0/0/1 | 192.168.10.1 | up / up (si S1 está conectado) |
| R1 | GigabitEthernet0/0/2 | unassigned | administratively down / down |
| R1 | Loopback0 | 1.1.1.1 | up / up |
| R2 | GigabitEthernet0/0/0 | 10.0.12.2 | up / up |
| R2 | GigabitEthernet0/0/1 | 10.0.23.1 | up / up |
| R3 | GigabitEthernet0/0/0 | 10.0.23.2 | up / up |
| R3 | GigabitEthernet0/0/1 | 192.168.20.1 | up / up |

Captura sugerida: `evidence/packet_tracer/R1_show_ip_interface_brief.png` (una por router).

## 2. Configuración — `show running-config`

Comprobar en cada router: `hostname`, descripción e IP de cada interfaz,
`shutdown` en G0/0/2 y la sección `router ospf 1`.

> Packet Tracer **no** acepta `show running-config interface <nombre>` ni
> `terminal length 0`: use `show running-config` y avance con la barra espaciadora.

## 3. Enrutamiento OSPF

```
show ip ospf neighbor
show ip route
show ip route ospf
show ip protocols
```

| Router | Vecinos esperados | Rutas OSPF (O) esperadas |
|---|---|---|
| R1 | 2.2.2.2 en G0/0/0, estado FULL | 10.0.23.0/30, 192.168.20.0/24, 2.2.2.2/32, 3.3.3.3/32 |
| R2 | 1.1.1.1 y 3.3.3.3, estado FULL | 192.168.10.0/24, 192.168.20.0/24, 1.1.1.1/32, 3.3.3.3/32 |
| R3 | 2.2.2.2 en G0/0/0, estado FULL | 10.0.12.0/30, 192.168.10.0/24, 1.1.1.1/32, 2.2.2.2/32 |

## 4. Conectividad extremo a extremo

Desde PC1 (*Desktop → Command Prompt*):

```
ipconfig
ping 192.168.10.1
ping 192.168.20.1
ping 192.168.20.10
tracert 192.168.20.10
```

Resultado esperado: respuestas a los pings (el primero puede perder un paquete
mientras se resuelve ARP) y un `tracert` que pasa por 192.168.10.1 → 10.0.12.2 →
10.0.23.2 → 192.168.20.10.

## 5. Prueba de cambio de estado (para comparar con la aplicación)

En R1:

```
configure terminal
interface GigabitEthernet0/0/1
 shutdown
end
show ip interface brief
```

Observar que G0/0/1 pasa a `administratively down` y que el ping de PC1 a PC2
falla. Restaurar con `no shutdown`.

## Lista de evidencias a capturar

- [x] Topología completa (vista lógica) — `topologia.png`
- [x] `show ip interface brief` de R1, R2 y R3
- [x] `show running-config` de R1 (sección de interfaces y OSPF)
- [x] `show ip ospf neighbor` de R2
- [x] `show ip route` de R1
- [x] `ping` y `tracert` de PC1 a PC2
- [x] Prueba de `shutdown` / `no shutdown`
- [x] Rechazo de `restconf` en el ISR4331 (ver `prueba_restconf_packet_tracer.md`)
