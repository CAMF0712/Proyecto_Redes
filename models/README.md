# Modelos YANG

| Archivo | Revisión | Norma | Uso |
|---|---|---|---|
| `ietf-interfaces.yang` | 2018-02-20 | RFC 8343 | Lista de interfaces: `name`, `description`, `type`, `enabled`, estado |
| `ietf-ip.yang` | 2018-02-22 | RFC 8344 | Aumenta cada interfaz con `ipv4/address` (`ip`, `prefix-length` o `netmask`) |
| `iana-if-type.yang` | 2023-01-26 | IANA | Identidades de tipo (`ethernetCsmacd`, `softwareLoopback`) |
| `ietf-inet-types.yang` | 2013-07-15 | RFC 6991 | Tipos de direcciones IP |
| `ietf-yang-types.yang` | 2013-07-15 | RFC 6991 | Tipos comunes (contadores, fechas, MAC) |

Fuente: repositorio público [YangModels/yang](https://github.com/YangModels/yang) (carpetas `standard/ietf/RFC` y `standard/iana`).

Validación (desde la raíz del proyecto):

```powershell
pyang -p models --strict models/ietf-interfaces.yang models/ietf-ip.yang
pyang -p models -f tree models/ietf-interfaces.yang models/ietf-ip.yang
```

Resultado guardado en [`../evidence/pyang/`](../evidence/pyang/): sin errores ni advertencias.
