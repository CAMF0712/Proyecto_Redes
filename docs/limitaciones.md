# Limitaciones del proyecto

## Resumen

| Limitación | Consecuencia | Cómo se maneja |
|---|---|---|
| Packet Tracer no implementa RESTCONF/NETCONF/HTTP en routers | La aplicación no puede conectarse al laboratorio | Laboratorio y aplicación separados; comparación manual |
| No hay router físico compatible | El modo real no se ha ejecutado | Modo real implementado y probable con DevNet Sandbox; pruebas listas pero omitidas |
| El simulador implementa un subconjunto de RFC 8040 | No cubre POST, DELETE, XML, parámetros de consulta, NACM ni ETag | Documentado; la aplicación solo usa GET, PATCH y PUT |
| Datos del simulador ficticios y en memoria | No reflejan un dispositivo real y se pierden al reiniciar | Identificados con `X-Simulator`, franja naranja y avisos |
| Tiempos medidos contra localhost | No representan un router real | Se reportan con esa advertencia |
| Capturas de la GUI generadas en Linux | El aspecto puede variar levemente en Windows | Repetir capturas en Windows para el informe |

## Evidencia de la limitación de Packet Tracer

Ver [`../lab/prueba_restconf_packet_tracer.md`](../lab/prueba_restconf_packet_tracer.md).

## Texto para el informe (sección *Limitaciones encontradas*)

Requiere las figuras `fig:pt-4331` y `fig:pt-2901` con las capturas del rechazo de
los comandos, y las entradas `cisco_restconf` y `pt_controller` en el `.bib`.

```latex
\textbf{Ausencia de RESTCONF en el entorno de laboratorio.} El laboratorio se
desarrolló en Cisco Packet Tracer 9.0.1. Para determinar si algún router del
simulador permitía habilitar interfaces programables, se colocaron un router
ISR4331 y un router 2901 y se ejecutaron, en modo de configuración global, los
comandos \texttt{restconf}, \texttt{netconf-yang}, \texttt{ip http
secure-server} e \texttt{ip http server}. En ambos equipos el simulador rechazó
los cuatro comandos con el mensaje \texttt{\% Invalid input detected}
(Figuras~\ref{fig:pt-4331} y \ref{fig:pt-2901}).

Este resultado obedece al simulador y no al modelo de router seleccionado: según
\texttt{show version}, el ISR4331 de Packet Tracer reporta Cisco IOS XE 16.6.4,
y en equipos físicos Cisco documenta soporte de RESTCONF para la serie ISR 4000 a
partir de IOS XE 16.3 \parencite{cisco_restconf}. Packet Tracer emula un
subconjunto de comandos orientado a la enseñanza de configuración por CLI y no
implementa el servidor HTTP de los routers, el agente RESTCONF ni los modelos YANG.

Se evaluó también el \textit{Network Controller} de Packet Tracer, que ofrece una
API REST accesible desde el equipo anfitrión \parencite{pt_controller}. Se
descartó porque dicha API es propia del controlador, no sigue el RFC 8040 y no
utiliza modelos YANG \parencite{rfc8040}.

El equipo no dispone de routers físicos compatibles. Por ello la solución se
dividió en dos componentes independientes: (1) el laboratorio de Packet Tracer,
configurado y verificado mediante CLI; y (2) la aplicación RESTCONF, probada
contra un simulador local que sigue el modelo \texttt{ietf-interfaces} y el
comportamiento HTTP del RFC 8040. La aplicación conserva un modo de conexión
real, listo para usarse con un dispositivo IOS XE que tenga RESTCONF habilitado,
pero dicho modo no pudo ejecutarse por falta de equipo. Los resultados de API
presentados en este informe provienen del simulador y se identifican como tales.
No existe sincronización automática entre el simulador y Packet Tracer; la
comparación entre ambos se realizó manualmente.
```

Entradas de bibliografía:

```bibtex
@misc{cisco_restconf,
  author       = {{Cisco Systems, Inc.}},
  title        = {Explore and learn about open management interfaces},
  year         = {2026},
  howpublished = {\url{https://developer.cisco.com/site/standard-network-devices/}},
  note         = {Tabla de soporte de NETCONF/RESTCONF por plataforma. Consultado el 25 de noviembre de 2026}
}
@misc{pt_controller,
  author       = {{Cisco Networking Academy}},
  title        = {Configuring Network Controllers -- Cisco Packet Tracer Help},
  year         = {2026},
  howpublished = {\url{https://tutorials.ptnetacad.net/help/default/config_NetworkControllers.htm}},
  note         = {Consultado el 25 de noviembre de 2026}
}
```

> Si el equipo logra ejecutar el modo real (por ejemplo con DevNet Sandbox), hay
> que actualizar el tercer párrafo: indicar el equipo, la versión de IOS XE, la
> fecha y qué pruebas se ejecutaron.
