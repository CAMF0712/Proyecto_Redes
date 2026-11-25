# Uso con un dispositivo RESTCONF real

La aplicación funciona con cualquier dispositivo que implemente RFC 8040 y el
modelo `ietf-interfaces`. Este documento describe dos opciones con Cisco IOS XE.

> Estado del proyecto: el modo real está implementado y cubierto por
> `tests/test_real_device.py`, pero **todavía no se ha ejecutado** contra un
> dispositivo. Cuando se haga, documentar fecha, equipo y versión en
> `evidence/dispositivo_real/`.

## Opción 1 — Cisco DevNet Sandbox (gratuito, sin hardware)

Cisco ofrece un IOS XE virtual (*Catalyst 8000V*) en la modalidad
**Always-On** con NETCONF y RESTCONF habilitados.

1. Crear una cuenta gratuita en <https://developer.cisco.com>.
2. Ir a <https://devnetsandbox.cisco.com> y buscar **IOS XE** en el catálogo.
3. Abrir el sandbox *Always-On* y copiar de su ficha: **host**, **usuario**,
   **contraseña** y **puertos abiertos**.
4. Verificar que el puerto **443** aparece entre los puertos abiertos. Cisco lo ha
   deshabilitado temporalmente en algunas ocasiones; si no aparece, RESTCONF no
   estará disponible ese día (probar luego o reservar un sandbox no compartido).
5. Prueba rápida desde PowerShell:

```powershell
curl.exe -k -u USUARIO:CONTRASENA -H "Accept: application/yang-data+json" https://HOST/restconf/data/ietf-interfaces:interfaces
```

Consideraciones:
* Es un equipo **compartido**: otros usuarios pueden cambiar la configuración al
  mismo tiempo. Modificar solo la **descripción** de una interfaz secundaria y
  restaurarla. **Nunca** deshabilitar la interfaz de gestión (normalmente
  `GigabitEthernet1`): se perdería el acceso.
* El certificado es autofirmado: en la aplicación, desmarcar *Verificar
  certificado TLS* (la aplicación pide confirmación) o usar `RESTCONF_VERIFY=false`
  en las pruebas.

## Opción 2 — Router o switch IOS XE propio

Requisitos: IOS XE 16.6 o superior con RESTCONF (ISR 4000, ISR 1000, Catalyst 8000,
Catalyst 9000, CSR1000v/Catalyst 8000V).

```
configure terminal
 hostname R1
 username admin privilege 15 secret <contraseña-segura>
 ip domain name lab.local
 crypto key generate rsa modulus 2048
 ip http secure-server
 ip http authentication local
 restconf
end
write memory
```

Verificación en el equipo:

```
show running-config | include restconf|ip http
show platform software yang-management process
```

El segundo comando debe mostrar los procesos de gestión YANG en estado *Running*
(entre ellos `nginx`, que atiende HTTPS).

## Uso desde la aplicación

1. `python main.py --modo real`
2. Host, puerto `443`, usuario y contraseña. *Usar HTTPS* marcado.
3. Certificado: indicar el archivo CA del equipo, o desmarcar la verificación
   solo en laboratorio.
4. **Conectar**: la aplicación hace `GET /restconf`. Si responde 200, carga las
   interfaces.

## Pruebas automatizadas contra el equipo

```powershell
$env:RESTCONF_HOST="HOST"
$env:RESTCONF_USER="USUARIO"
$env:RESTCONF_PASS="CONTRASENA"
$env:RESTCONF_VERIFY="false"
python -m pytest tests/test_real_device.py -v

# Escritura (opcional): cambia y restaura la descripción de UNA interfaz no crítica
$env:RESTCONF_ALLOW_WRITE="1"; $env:RESTCONF_IFACE="Loopback0"
python -m pytest tests/test_real_device.py -v
```

## Diferencias que se pueden encontrar

* IOS XE devuelve una entrada individual como **objeto** y no como lista; la
  aplicación acepta ambas formas.
* Algunas versiones no publican `ietf-interfaces:interfaces-state`; la aplicación
  sigue funcionando y muestra el estado operativo como *desconocido*.
* Los mensajes de error son de IOS XE, aunque los códigos HTTP siguen RFC 8040.
* Cambiar la IP de la interfaz por la que se gestiona el equipo corta la sesión.
