# Guía del equipo — Desafío de Redes (CE-5301)

Este documento resume **qué se hizo**, **cómo probarlo** y **qué falta** para terminar
el proyecto entre todos. El detalle técnico está en el [`README.md`](README.md).

| Integrante | Carné | Rol |
|---|---|---|
| Giancarlo Vega Marín | 2020195338 | Coordinador del proyecto y del informe |
| José Manuel Loría Cordero | 2022211671 | Responsable del laboratorio de red (Packet Tracer) |
| César Andrés Mora Fajardo | 2020053458 | Desarrollador de la aplicación |
| Marco Villatoro Chacon | 2021057692 | Desarrollador del simulador y modelos YANG |
| Mariana Rojas Rojas | 2020076936 | Responsable de pruebas, evidencias y video |

---

## 1. Qué se hizo

### En resumen

* **Aplicación en Python** con interfaz gráfica que consulta y modifica interfaces de red
  mediante **RESTCONF** usando los modelos YANG `ietf-interfaces` e `ietf-ip`. Permite
  cambiar la descripción, la IP y habilitar/deshabilitar una interfaz; pide confirmación
  antes de cada cambio, lo verifica con un GET y guarda un historial (sin contraseñas).
* **Simulador RESTCONF** (Flask): un servidor local que se comporta como un router IOS XE
  con RESTCONF. Se usa porque **Packet Tracer no soporta RESTCONF** (lo comprobamos).
* **Laboratorio en Packet Tracer 9.0.1**: 3 routers ISR4331 con OSPF, 2 switches y 2 PC.
  **Ya está armado, configurado y verificado** (OSPF y ping de PC1 a PC2 funcionan).
* **44 pruebas automatizadas** (39 contra el simulador + 5 para un equipo real).
* **Colección de Postman**, modelos YANG validados con pyang, evidencias y **el informe en LaTeX**.

### Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Topología de Packet Tracer | [`lab/topologia_ce5301.pkt`](lab/topologia_ce5301.pkt) |
| Configuraciones de R1, R2, R3, S1, S2 | [`lab/configuraciones/`](lab/configuraciones/) |
| Salidas de la CLI (show, ping, tracert) | [`evidence/packet_tracer/salidas_cli.md`](evidence/packet_tracer/salidas_cli.md) |
| Prueba de que PT no soporta RESTCONF | [`lab/prueba_restconf_packet_tracer.md`](lab/prueba_restconf_packet_tracer.md) |
| Código de la aplicación | [`main.py`](main.py) y [`application/`](application/) |
| Simulador | [`simulator/`](simulator/) |
| Pruebas | [`tests/`](tests/) |
| Postman | [`postman/`](postman/) |
| Informe (`.tex` + `.pdf` + figuras) | [`docs/informe/`](docs/informe/) |
| Guion del video | [`docs/guion_demo.md`](docs/guion_demo.md) |
| Cómo usar un router real (DevNet Sandbox) | [`docs/dispositivo_real.md`](docs/dispositivo_real.md) |
| Texto de limitaciones | [`docs/limitaciones.md`](docs/limitaciones.md) |

### Lo más importante para defenderlo ante el profesor

1. **Packet Tracer no tiene RESTCONF.** En el ISR4331 (que reporta IOS XE 16.6.4) y en el
   2901, los comandos `restconf`, `netconf-yang`, `ip http secure-server` e `ip http server`
   dan `% Invalid input detected`. Por eso el laboratorio y la aplicación son
   **independientes**.
2. **Todo resultado de API viene del simulador**, no de un router. La app lo indica con una
   franja naranja y cada respuesta trae el encabezado `X-Simulator`. Nunca digan que la app
   se conectó a Packet Tracer.
3. **La comparación entre la CLI y la app es manual**; no hay sincronización.
4. El mismo código funcionaría con un IOS XE real (modo *RESTCONF real*), pero **no se ha
   probado con uno** (ver tarea opcional de DevNet abajo).

---

## 2. Cómo probarlo (Windows)

### 2.1 Obtener el repositorio

En **GitHub Desktop**: *File → Clone repository* → `CAMF0712/Proyecto_Redes`.
Si ya lo tienen, presionen **Fetch origin** y luego **Pull origin**.

### 2.2 Instalar (una sola vez)

Necesitan **Python 3.10 o superior** de python.org (marcar *tcl/tk* al instalar).
En PowerShell, dentro de la carpeta del repositorio:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell no deja activar el entorno:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y repetir la activación.

### 2.3 Correr las pruebas

```powershell
python -m pytest -v
```

Resultado esperado: **39 passed, 5 skipped** (las 5 omitidas son las del router real).

### 2.4 Usar la aplicación

Abrir **dos** terminales en la carpeta del repo (con el entorno activado en ambas):

```powershell
# Terminal 1 — dejarla abierta
python -m simulator.server

# Terminal 2
python main.py
```

En la aplicación:
1. Contraseña: `admin123` (el usuario `admin` ya viene puesto) → **Conectar**.
2. Seleccionar `GigabitEthernet0/0/1` → **Cambiar descripción** → revisar la confirmación → **Confirmar y enviar**.
3. Probar **Cambiar IP** y **Habilitar / Deshabilitar**.
4. Errores para la demo: contraseña incorrecta (401), modificar `GigabitEthernet0` (403),
   una IP como `192.168.10.0/24` (la app la rechaza), apagar el simulador (sin conexión).

### 2.5 Postman

*Import* → `postman/collection.json` y `postman/entorno_simulador.json` → seleccionar el
entorno *Simulador RESTCONF local* → ejecutar las solicitudes 1 a 4 en orden (con el
simulador corriendo).

### 2.6 Packet Tracer

Abrir `lab/topologia_ce5301.pkt` con **Packet Tracer 9.0.1**. Desde PC1
(*Desktop → Command Prompt*): `ping 192.168.20.10`. En R1, R2 o R3:
`show ip interface brief`, `show ip ospf neighbor`, `show ip route`.

> Tip: Ctrl+V no funciona en la CLI de PT; usen el botón **Paste** de la ventana. Si un
> comando mal escrito se queda "Translating...", se cancela con **Ctrl+Shift+6**.

---

## 3. Qué falta y quién lo hace

Todo lo marcado en **rojo como PENDIENTE** en el PDF del informe está en esta lista.

### Giancarlo — coordinación e informe

- [ ] Subir la carpeta `docs/informe/` completa a **Overleaf** (el `.tex`, `referencias.bib` y `figuras/`) y compartir el proyecto con el equipo.
- [ ] Poner la **fecha de entrega** en la portada.
- [ ] Llenar las **minutas** de las reuniones reales (fecha, participantes, temas, acuerdos). No inventar reuniones.
- [ ] Completar las fechas pendientes del **cronograma** (revisión final y video).
- [ ] Confirmar con Marco si su apellido lleva tilde (**Chacón**) y corregirlo en el `.tex` si aplica.
- [ ] Revisión final del informe y compilación del PDF definitivo.

### José Manuel — laboratorio

- [ ] Abrir `lab/topologia_ce5301.pkt` y tomar **capturas de pantalla** (guardarlas en `evidence/packet_tracer/`):
  - [ ] Topología completa (vista lógica).
  - [ ] `show ip interface brief` en R1, R2 y R3.
  - [ ] `show ip ospf neighbor` en R2 y `show ip route` en R1.
  - [ ] `ping` y `tracert` de PC1 a PC2.
  - [ ] Rechazo de `restconf` en un ISR4331 y en un 2901, y `show version` del ISR4331.
- [ ] Insertar esas capturas en el informe (secciones *Topología del laboratorio*, *Resultados de conectividad* y *Limitaciones*).

### César — aplicación

- [ ] Correr la app en Windows y tomar capturas nuevas de: panel principal, confirmación de un cambio, resultado verificado e historial, y un error (por ejemplo 401). Reemplazar las de `docs/informe/figuras/` (las actuales se generaron en Linux).
- [ ] Llenar la **tabla de comparación** de `lab/comparacion_cli_vs_aplicacion.md` (CLI de R1 vs. app en modo simulador).

### Marco — simulador y YANG

- [ ] *(Opcional, pero sube mucho la nota)* Intentar el **modo real** con el router gratuito de **Cisco DevNet Sandbox** siguiendo [`docs/dispositivo_real.md`](docs/dispositivo_real.md):
  - Crear cuenta en developer.cisco.com, buscar el sandbox *IOS XE Always-On* y revisar que el puerto 443 esté abierto.
  - Conectar con `python main.py --modo real` y correr `python -m pytest tests/test_real_device.py -v`.
  - Si funciona: guardar capturas en `evidence/dispositivo_real/` y avisar a Giancarlo para actualizar la sección de limitaciones del informe.
- [ ] Preparar su parte del video: árbol YANG con `pyang -p models -f tree models/ietf-interfaces.yang models/ietf-ip.yang`.

### Mariana — pruebas, evidencias y video

- [ ] Correr `python -m pytest -v` en Windows y tomar una captura del resultado.
- [ ] Importar la colección en Postman, ejecutar las solicitudes 1 a 4 y los 3 errores, y tomar capturas.
- [ ] Coordinar la **grabación del video** según [`docs/guion_demo.md`](docs/guion_demo.md) (máximo 10 min, todos con cámara).
- [ ] Subir el video y pasar el **enlace** a Giancarlo para el informe.

### Todos

- [ ] Clonar el repo, instalar y probar la app (sección 2) para poder explicarla.
- [ ] Llenar cada uno su fila de la **bitácora individual** (fechas, horas y actividad con evidencia).
- [ ] Hacer la **autoevaluación y coevaluación**.
- [ ] Completar el **formulario individual** del profesor (una sola vez cada uno) y enviar a Giancarlo una captura de la confirmación (sin mostrar las respuestas):
  <https://docs.google.com/forms/d/e/1FAIpQLSfC_crNLh92D2pbcmpS1f_qeWVgdBkoXvHkjbXpWi53Q9b6UQ/viewform>
- [ ] Participar en el video en su bloque del guion.

---

## 4. Reglas para trabajar en el repo

1. Antes de empezar: **Fetch origin → Pull origin** en GitHub Desktop.
2. Hagan commits pequeños con un mensaje claro (por ejemplo: `Capturas de Packet Tracer de R1`).
3. Al terminar: **Push origin** y avisen en el grupo.
4. No suban contraseñas reales, carpetas `.venv/` ni `logs/` (ya están ignoradas).
5. El informe se edita en **Overleaf**; cuando esté final, quien coordina descarga el `.tex`
   y el PDF y los sube a `docs/informe/`.
6. Si cambian el simulador o la aplicación, corran `python -m pytest` antes de subir.
