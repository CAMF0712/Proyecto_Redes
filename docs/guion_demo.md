# Guion del video de demostración (máximo 10 minutos)

Requisitos de la consigna: participan **todas las personas integrantes** con la
cámara encendida durante su parte; incluye introducción del caso de uso,
requerimientos de red y de aplicaciones, configuración o programación utilizada y
una demostración clara de la utilidad de la solución.

Reemplazar *Integrante 1/2/3* por los nombres reales.

## Preparación (antes de grabar)

- [ ] Topología de Packet Tracer abierta, configurada y con OSPF convergido.
- [ ] Terminal 1: `python -m simulator.server --enable-faults`
- [ ] Terminal 2: entorno virtual activado en la raíz del repositorio.
- [ ] Postman con la colección y el entorno *Simulador RESTCONF local* importados.
- [ ] Ejecutar `POST /simulator/reset` (o reiniciar el simulador) para partir de los
      datos iniciales.
- [ ] Cerrar notificaciones y aumentar el tamaño de letra de las terminales.

## Desarrollo

| Tiempo | Integrante | Contenido | Qué se muestra |
|---|---|---|---|
| 0:00–1:00 | Integrante 1 | Presentación del equipo y del problema: administrar interfaces equipo por equipo por CLI no escala | Portada / diapositiva |
| 1:00–2:00 | Integrante 1 | Conceptos: YANG define los datos, RESTCONF los transporta por HTTP, JSON como formato | Diagrama de arquitectura (`docs/img/arquitectura.png`) |
| 2:00–3:30 | Integrante 2 | **Componente A.** Topología, direccionamiento y OSPF. `show ip interface brief`, `show ip route`, ping PC1 → PC2 | Packet Tracer |
| 3:30–4:15 | Integrante 2 | **Limitación:** `restconf` rechazado en el ISR4331 (IOS XE 16.6.4). Explicar por qué se usa un simulador y que no hay sincronización | Packet Tracer + `lab/prueba_restconf_packet_tracer.md` |
| 4:15–5:00 | Integrante 3 | Modelo YANG con `pyang -f tree` y estructura del código | Terminal + VS Code |
| 5:00–7:30 | Integrante 3 | **Demostración de la aplicación:** conectar en modo simulador (señalar la franja naranja), tabla y resumen, consulta individual, cambio de descripción con confirmación y verificación, deshabilitar G0/0/1 y ver el estado operativo, historial | GUI |
| 7:30–8:30 | Integrante 1 | **Errores:** contraseña incorrecta (401), IP inválida (validación local), interfaz protegida (403), simulador apagado (sin conectividad) | GUI |
| 8:30–9:15 | Integrante 2 | Postman: GET, PATCH y GET de verificación; pruebas en verde. `python -m pytest -v` | Postman + terminal |
| 9:15–10:00 | Integrante 3 | Resultados, limitaciones (sin equipo real), cómo se usaría con un IOS XE real o DevNet Sandbox, conclusiones | Diapositiva final |

## Frases clave (para no presentar datos simulados como reales)

* "Los datos que ven en la aplicación provienen del **simulador local**, no del
  router de Packet Tracer."
* "El simulador usa la misma estructura YANG y los mismos códigos HTTP que un
  equipo IOS XE, por lo que el mismo cliente funcionaría con un router real."
* "Hicimos la comparación entre la CLI y la aplicación **manualmente**; los dos
  entornos no están conectados."

## Después de grabar

- Subir el video y pegar el enlace en el informe (sección *Video de demostración*).
- Verificar que dura menos de 10:00 y que aparecen todos los integrantes.
