# Salidas de verificación del laboratorio (Packet Tracer 9.0.1)

**Fecha:** 25 de noviembre de 2026 · **Archivo:** [`lab/topologia_ce5301.pkt`](../../lab/topologia_ce5301.pkt)

> Estas salidas son **reales**: provienen de los routers y PC simulados por Packet
> Tracer en la topología del repositorio. Se **transcribieron** de la pantalla
> porque el botón *Copy* de la CLI de Packet Tracer no copió el texto; el
> espaciado de las columnas es aproximado. Para el informe conviene agregar
> también capturas de pantalla.

## R1 — `show ip interface brief`

```
R1#show ip interface brief
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0/0   10.0.12.1       YES manual up                    up
GigabitEthernet0/0/1   192.168.10.1    YES manual up                    up
GigabitEthernet0/0/2   unassigned      YES unset  administratively down down
Loopback0              1.1.1.1         YES manual up                    up
```

## R1 — `show ip ospf neighbor`

```
Neighbor ID     Pri   State           Dead Time   Address         Interface
2.2.2.2           1   FULL/DR         00:00:31    10.0.12.2       GigabitEthernet0/0/0
```

Registro de la adyacencia en la consola de R1:

```
%OSPF-5-ADJCHG: Process 1, Nbr 2.2.2.2 on GigabitEthernet0/0/0 from LOADING to FULL, Loading Done
```

## R1 — `show ip route ospf` (después de la convergencia)

```
R1#show ip route ospf
     2.0.0.0/32 is subnetted, 1 subnets
O       2.2.2.2 [110/2] via 10.0.12.2, 00:05:24, GigabitEthernet0/0/0
     3.0.0.0/32 is subnetted, 1 subnets
O       3.3.3.3 [110/3] via 10.0.12.2, 00:04:37, GigabitEthernet0/0/0
     10.0.0.0/8 is variably subnetted, 3 subnets, 2 masks
O       10.0.23.0 [110/2] via 10.0.12.2, 00:04:47, GigabitEthernet0/0/0
O    192.168.20.0 [110/3] via 10.0.12.2, 00:04:37, GigabitEthernet0/0/0
```

Nota: en un primer `show ip route` la red 192.168.20.0/24 todavía no aparecía
porque la interfaz LAN de R3 se conectó después; apareció en la siguiente consulta.

## R2 — `show ip interface brief` y `show ip ospf neighbor`

```
R2>show ip interface brief
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0/0   10.0.12.2       YES manual up                    up
GigabitEthernet0/0/1   10.0.23.1       YES manual up                    up
GigabitEthernet0/0/2   unassigned      YES unset  administratively down down
Loopback0              2.2.2.2         YES manual up                    up
R2>show ip ospf neighbor

Neighbor ID     Pri   State           Dead Time   Address         Interface
3.3.3.3           1   FULL/DR         00:00:30    10.0.23.2       GigabitEthernet0/0/1
1.1.1.1           1   FULL/BDR        00:00:33    10.0.12.1       GigabitEthernet0/0/0
```

## R3 — `show ip interface brief` y `show ip route ospf`

```
R3#show ip interface brief
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0/0   10.0.23.2       YES manual up                    up
GigabitEthernet0/0/1   192.168.20.1    YES manual up                    up
GigabitEthernet0/0/2   unassigned      YES unset  administratively down down
Loopback0              3.3.3.3         YES manual up                    up
R3#show ip route ospf
     1.0.0.0/32 is subnetted, 1 subnets
O       1.1.1.1 [110/3] via 10.0.23.1, 00:05:45, GigabitEthernet0/0/0
     2.0.0.0/32 is subnetted, 1 subnets
O       2.2.2.2 [110/2] via 10.0.23.1, 00:05:45, GigabitEthernet0/0/0
     10.0.0.0/8 is variably subnetted, 3 subnets, 2 masks
O       10.0.12.0 [110/2] via 10.0.23.1, 00:05:45, GigabitEthernet0/0/0
O    192.168.10.0 [110/3] via 10.0.23.1, 00:05:45, GigabitEthernet0/0/0
```

## PC1 — `ipconfig`, `ping` y `tracert` hacia PC2

```
C:\>ipconfig

FastEthernet0 Connection:(default port)

   Connection-specific DNS Suffix..:
   Link-local IPv6 Address.........: FE80::209:7CFF:FECC:812
   IPv6 Address....................: ::
   IPv4 Address....................: 192.168.10.10
   Subnet Mask.....................: 255.255.255.0
   Default Gateway.................: ::
                                     192.168.10.1

C:\>ping 192.168.20.10

Pinging 192.168.20.10 with 32 bytes of data:

Request timed out.
Reply from 192.168.20.10: bytes=32 time<1ms TTL=125
Reply from 192.168.20.10: bytes=32 time<1ms TTL=125
Reply from 192.168.20.10: bytes=32 time<1ms TTL=125

Ping statistics for 192.168.20.10:
    Packets: Sent = 4, Received = 3, Lost = 1 (25% loss),
Approximate round trip times in milli-seconds:
    Minimum = 0ms, Maximum = 0ms, Average = 0ms

C:\>tracert 192.168.20.10

Tracing route to 192.168.20.10 over a maximum of 30 hops:

  1   0 ms      0 ms      0 ms      192.168.10.1
  2   0 ms      0 ms      0 ms      10.0.12.2
  3   0 ms      0 ms      0 ms      10.0.23.2
  4   0 ms      0 ms      0 ms      192.168.20.10

Trace complete.
```

El primer eco se pierde mientras se resuelve ARP. `TTL=125` (128 − 3) confirma
que el paquete atravesó los tres routers.

## R1 — Prueba de RESTCONF en la topología

```
R1#configure terminal
Enter configuration commands, one per line.  End with CNTL/Z.
R1(config)#restconf
                ^
% Invalid input detected at '^' marker.

R1(config)#netconf-yang
                ^
% Invalid input detected at '^' marker.

R1(config)#ip http secure-server
               ^
% Invalid input detected at '^' marker.

R1(config)#ip http server
               ^
% Invalid input detected at '^' marker.

R1(config)#end
```

## Comandos no disponibles en Packet Tracer

Durante la verificación se comprobó que Packet Tracer **no** acepta
`terminal length 0` ni `show running-config interface <nombre>`. Use
`show running-config` completo.
