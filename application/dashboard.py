"""Interfaz gráfica (CustomTkinter) del administrador de interfaces RESTCONF.

Las operaciones de red se ejecutan en hilos secundarios para no congelar la
ventana; los resultados vuelven al hilo de la interfaz con ``after``.
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

import customtkinter as ctk

from . import validators as v
from .interface_manager import ChangeOutcome, ChangePlan, InterfaceInfo, InterfaceManager, summarize
from .operation_log import LogEntry, OperationLogger
from .restconf_client import MODE_REAL, MODE_SIM, RestconfClient

APP_TITLE = "Administrador de interfaces RESTCONF - CE-5301"
COLOR_SIM = "#B45309"     # naranja: modo simulador
COLOR_REAL = "#1D4ED8"    # azul: dispositivo real
COLOR_OFF = "#4B5563"     # gris: sin conexión
COLOR_OK = "#15803D"
COLOR_ERR = "#B91C1C"

DEFAULTS = {
    MODE_SIM: {"host": "127.0.0.1", "port": "5000", "https": False, "verify": False},
    MODE_REAL: {"host": "", "port": "443", "https": True, "verify": True},
}


class Dashboard(ctk.CTk):
    def __init__(self, initial_mode: str = MODE_SIM, log_file: str | Path | None = None):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1360x860")
        self.minsize(1100, 700)

        self.logger = OperationLogger(log_file or Path("logs") / "operaciones.jsonl")
        self.logger.add_listener(lambda e: self.after(0, self._append_history, e))
        self.client: RestconfClient | None = None
        self.manager: InterfaceManager | None = None
        self.interfaces: list[InterfaceInfo] = []
        self._busy = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_banner()
        self._build_sidebar()
        self._build_main()
        self._style_tables()
        self.mode_var.set(initial_mode)
        self._on_mode_change(initial_mode)
        self._set_disconnected()

    # ================================================================ layout
    def _build_banner(self) -> None:
        self.banner = ctk.CTkLabel(self, text="", height=40, corner_radius=0,
                                   font=ctk.CTkFont(size=15, weight="bold"), text_color="white")
        self.banner.grid(row=0, column=0, columnspan=2, sticky="ew")

    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(self, width=310, corner_radius=0)
        side.grid(row=1, column=0, sticky="nsw")
        side.grid_propagate(False)
        pad = {"padx": 16, "pady": (4, 0), "sticky": "ew"}

        ctk.CTkLabel(side, text="Conexión", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        ctk.CTkLabel(side, text="Modo de funcionamiento").grid(row=1, column=0, **pad)
        self.mode_var = ctk.StringVar(value=MODE_SIM)
        self.mode_selector = ctk.CTkSegmentedButton(side, values=[MODE_SIM, MODE_REAL],
                                                    variable=self.mode_var,
                                                    command=self._on_mode_change)
        self.mode_selector.grid(row=2, column=0, padx=16, pady=(2, 8), sticky="ew")

        self.host_entry = self._labeled_entry(side, 3, "Dirección IP / host")
        self.port_entry = self._labeled_entry(side, 5, "Puerto")
        self.user_entry = self._labeled_entry(side, 7, "Usuario")
        self.pass_entry = self._labeled_entry(side, 9, "Contraseña", show="*")
        self.timeout_entry = self._labeled_entry(side, 11, "Tiempo de espera (s)")
        self.timeout_entry.insert(0, "10")

        self.https_var = ctk.BooleanVar(value=False)
        self.verify_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(side, text="Usar HTTPS", variable=self.https_var,
                        command=self._update_tls_widgets).grid(row=13, column=0, padx=16,
                                                               pady=(10, 2), sticky="w")
        self.verify_check = ctk.CTkCheckBox(side, text="Verificar certificado TLS",
                                            variable=self.verify_var,
                                            command=self._update_tls_widgets)
        self.verify_check.grid(row=14, column=0, padx=16, pady=2, sticky="w")
        ca_row = ctk.CTkFrame(side, fg_color="transparent")
        ca_row.grid(row=15, column=0, padx=16, pady=2, sticky="ew")
        ca_row.grid_columnconfigure(0, weight=1)
        self.ca_entry = ctk.CTkEntry(ca_row, placeholder_text="Certificado CA (opcional)")
        self.ca_entry.grid(row=0, column=0, sticky="ew")
        self.ca_button = ctk.CTkButton(ca_row, text="...", width=34, command=self._choose_ca)
        self.ca_button.grid(row=0, column=1, padx=(4, 0))

        self.connect_button = ctk.CTkButton(side, text="Conectar", height=36,
                                            command=self._on_connect)
        self.connect_button.grid(row=16, column=0, padx=16, pady=(14, 4), sticky="ew")
        self.disconnect_button = ctk.CTkButton(side, text="Desconectar", height=30,
                                               fg_color="transparent", border_width=1,
                                               command=self._on_disconnect)
        self.disconnect_button.grid(row=17, column=0, padx=16, pady=4, sticky="ew")
        self.conn_status = ctk.CTkLabel(side, text="", wraplength=270, justify="left")
        self.conn_status.grid(row=18, column=0, padx=16, pady=(8, 4), sticky="w")

        ctk.CTkLabel(side, text="Apariencia").grid(row=19, column=0, padx=16, pady=(18, 0),
                                                   sticky="w")
        ctk.CTkOptionMenu(side, values=["Oscuro", "Claro"],
                          command=lambda m: ctk.set_appearance_mode(
                              "dark" if m == "Oscuro" else "light")).grid(
            row=20, column=0, padx=16, pady=4, sticky="ew")

    @staticmethod
    def _labeled_entry(parent, row: int, label: str, show: str | None = None) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=16, pady=(6, 0), sticky="w")
        entry = ctk.CTkEntry(parent, show=show) if show else ctk.CTkEntry(parent)
        entry.grid(row=row + 1, column=0, padx=16, pady=(2, 0), sticky="ew")
        return entry

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=1, sticky="nsew", padx=12, pady=12)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=3)
        main.grid_rowconfigure(5, weight=2)

        # --- tarjetas de resumen (panel principal)
        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew")
        self.card_values: dict[str, ctk.CTkLabel] = {}
        specs = [("modo", "Modo"), ("estado", "Estado de conexión"), ("servidor", "Servidor"),
                 ("total", "Interfaces"), ("activas", "Activas"), ("desactivadas", "Desactivadas")]
        for col, (key, title) in enumerate(specs):
            cards.grid_columnconfigure(col, weight=2 if key in ("servidor", "estado") else 1)
            card = ctk.CTkFrame(cards)
            card.grid(row=0, column=col, padx=4, sticky="nsew")
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12)).pack(padx=10, pady=(8, 0),
                                                                          anchor="w")
            value = ctk.CTkLabel(card, text="-", font=ctk.CTkFont(size=17, weight="bold"),
                                 wraplength=260, justify="left")
            value.pack(padx=10, pady=(0, 8), anchor="w")
            self.card_values[key] = value

        # --- tabla de interfaces y acciones
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(12, 4))
        ctk.CTkLabel(bar, text="Interfaces (ietf-interfaces)",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.action_buttons: list[ctk.CTkButton] = []
        for text, cmd in [("Habilitar / Deshabilitar", self._on_toggle),
                          ("Cambiar IP", self._on_change_ip),
                          ("Cambiar descripción", self._on_change_description),
                          ("Consultar seleccionada (GET)", self._on_get_one),
                          ("Actualizar (GET)", self._on_refresh)]:
            btn = ctk.CTkButton(bar, text=text, command=cmd, width=10)
            btn.pack(side="right", padx=3)
            self.action_buttons.append(btn)

        table_frame = ctk.CTkFrame(main)
        table_frame.grid(row=2, column=0, sticky="nsew")
        cols = ("name", "description", "ip", "prefix", "admin", "oper")
        headings = ("Nombre", "Descripción", "Dirección IP", "Prefijo", "Estado administrativo",
                    "Estado operativo")
        widths = (190, 360, 140, 70, 160, 140)
        self.if_table = ttk.Treeview(table_frame, columns=cols, show="headings",
                                     selectmode="browse", style="RC.Treeview")
        for c, h, w in zip(cols, headings, widths):
            self.if_table.heading(c, text=h)
            self.if_table.column(c, width=w, anchor="w", stretch=c == "description")
        self.if_table.tag_configure("down", foreground="#F87171")
        self.if_table.tag_configure("admin_down", foreground="#9CA3AF")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.if_table.yview)
        self.if_table.configure(yscrollcommand=sb.set)
        self.if_table.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        sb.pack(side="right", fill="y", pady=6)
        self.if_table.bind("<Double-1>", lambda _e: self._on_get_one())

        self.status_line = ctk.CTkLabel(main, text="", anchor="w")
        self.status_line.grid(row=3, column=0, sticky="ew", pady=(4, 0))

        # --- historial de operaciones
        hist_bar = ctk.CTkFrame(main, fg_color="transparent")
        hist_bar.grid(row=4, column=0, sticky="ew", pady=(10, 4))
        ctk.CTkLabel(hist_bar, text="Historial de operaciones",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(hist_bar, text="Exportar CSV", width=10,
                      command=self._export_history).pack(side="right")
        hist_frame = ctk.CTkFrame(main)
        hist_frame.grid(row=5, column=0, sticky="nsew")
        hcols = ("fecha", "modo", "operación", "método", "endpoint", "código", "resultado", "tiempo")
        hhead = ("Fecha", "Modo", "Operación", "Método", "Endpoint", "HTTP", "Resultado", "ms")
        hwid = (152, 114, 205, 62, 275, 45, 150, 45)
        self.hist_table = ttk.Treeview(hist_frame, columns=hcols, show="headings",
                                       style="RC.Treeview")
        for c, h, w in zip(hcols, hhead, hwid):
            self.hist_table.heading(c, text=h)
            self.hist_table.column(c, width=w, anchor="w", stretch=c in ("endpoint", "resultado"))
        self.hist_table.tag_configure("error", foreground="#F87171")
        hsb = ttk.Scrollbar(hist_frame, orient="vertical", command=self.hist_table.yview)
        self.hist_table.configure(yscrollcommand=hsb.set)
        self.hist_table.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        hsb.pack(side="right", fill="y", pady=6)

    def _style_tables(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("RC.Treeview", background="#1F2937", fieldbackground="#1F2937",
                        foreground="#F3F4F6", rowheight=26, borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("RC.Treeview.Heading", background="#374151", foreground="#F9FAFB",
                        font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("RC.Treeview", background=[("selected", "#2563EB")])

    # ============================================================ utilidades
    def _run_async(self, work: Callable[[], Any], done: Callable[[Any], None],
                   busy_text: str) -> None:
        """Ejecuta ``work`` en un hilo y ``done(resultado)`` en el hilo de la GUI."""
        if self._busy:
            return
        self._set_busy(True, busy_text)

        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001 - se muestra al usuario
                result = exc
            self.after(0, lambda: self._finish_async(done, result))

        threading.Thread(target=runner, daemon=True).start()

    def _finish_async(self, done: Callable[[Any], None], result: Any) -> None:
        self._set_busy(False, "")
        if isinstance(result, v.ValidationError):
            messagebox.showwarning("Dato inválido", str(result), parent=self)
        elif isinstance(result, Exception):
            messagebox.showerror("Error inesperado", f"{type(result).__name__}: {result}",
                                 parent=self)
        else:
            done(result)

    def _set_busy(self, busy: bool, text: str) -> None:
        self._busy = busy
        state = "disabled" if busy or self.manager is None else "normal"
        for btn in self.action_buttons:
            btn.configure(state=state)
        self.connect_button.configure(state="disabled" if busy else "normal")
        self.status_line.configure(text=text)
        self.configure(cursor="watch" if busy else "")

    def _selected(self) -> InterfaceInfo | None:
        sel = self.if_table.selection()
        if not sel:
            messagebox.showinfo("Seleccione una interfaz",
                                "Seleccione primero una interfaz en la tabla.", parent=self)
            return None
        name = self.if_table.item(sel[0], "values")[0]
        return next((i for i in self.interfaces if i.name == name), None)

    # ============================================================ conexión
    def _on_mode_change(self, mode: str) -> None:
        d = DEFAULTS[mode]
        for entry, value in ((self.host_entry, d["host"]), (self.port_entry, d["port"])):
            entry.delete(0, "end")
            entry.insert(0, value)
        if not self.user_entry.get():
            self.user_entry.insert(0, "admin")
        self.https_var.set(d["https"])
        self.verify_var.set(d["verify"])
        self._update_tls_widgets()
        if self.client is not None:
            self._on_disconnect()
        self._update_banner()

    def _update_tls_widgets(self) -> None:
        https = self.https_var.get()
        self.verify_check.configure(state="normal" if https else "disabled")
        on = https and self.verify_var.get()
        self.ca_entry.configure(state="normal" if on else "disabled")
        self.ca_button.configure(state="normal" if on else "disabled")

    def _choose_ca(self) -> None:
        path = filedialog.askopenfilename(title="Certificado de la autoridad (CA)",
                                          filetypes=[("Certificados", "*.pem *.crt *.cer"),
                                                     ("Todos", "*.*")])
        if path:
            self.ca_entry.delete(0, "end")
            self.ca_entry.insert(0, path)

    def _update_banner(self) -> None:
        mode = self.mode_var.get()
        if mode == MODE_SIM:
            text = ("MODO SIMULADOR - Los datos provienen del simulador local. "
                    "NO corresponden a un router real ni a Packet Tracer.")
            color = COLOR_SIM
        elif self.client is not None:
            text = f"MODO RESTCONF REAL - Dispositivo {self.client.base_url}"
            color = COLOR_REAL
        else:
            text = "MODO RESTCONF REAL - Sin conexión con un dispositivo"
            color = COLOR_OFF
        self.banner.configure(text=text, fg_color=color)
        self.card_values["modo"].configure(text=mode)

    def _on_connect(self) -> None:
        try:
            host = v.validate_host(self.host_entry.get())
            port = v.validate_port(self.port_entry.get())
            timeout = v.validate_timeout(self.timeout_entry.get())
            user = self.user_entry.get().strip()
            password = self.pass_entry.get()
            v.validate_credentials(user, password)
        except v.ValidationError as exc:
            messagebox.showwarning("Datos de conexión", str(exc), parent=self)
            return
        https = self.https_var.get()
        verify: bool | str = self.verify_var.get()
        if https and verify and self.ca_entry.get().strip():
            verify = self.ca_entry.get().strip()
        if https and verify is False and self.mode_var.get() == MODE_REAL:
            if not messagebox.askyesno(
                    "Verificación TLS desactivada",
                    "No se verificará el certificado del dispositivo. Use esta opción solo en "
                    "laboratorio con certificados autofirmados. Desea continuar?", parent=self):
                return
        if self.client is not None:
            self.client.close()
        client = RestconfClient(host, port, user, password, use_https=https, verify=verify,
                                timeout=timeout, mode=self.mode_var.get(), logger=self.logger)

        def done(res) -> None:
            if res.ok:
                if self.mode_var.get() == MODE_REAL and res.is_simulator:
                    messagebox.showwarning(
                        "Atención", "El servidor respondio con el encabezado X-Simulator: es el "
                        "simulador local, no un dispositivo real.", parent=self)
                self.client = client
                self.manager = InterfaceManager(client)
                self._set_connected()
                self._on_refresh()
            else:
                client.close()
                self._set_disconnected(error=res.error)
                messagebox.showerror("No se pudo conectar", res.error, parent=self)

        self._run_async(client.discover, done, f"Conectando con {client.base_url} ...")

    def _on_disconnect(self) -> None:
        if self.client is not None:
            self.client.close()
        self.client = None
        self.manager = None
        self.interfaces = []
        self.if_table.delete(*self.if_table.get_children())
        self._set_disconnected()

    def _set_connected(self) -> None:
        self.conn_status.configure(text=f"Conectado a {self.client.base_url}", text_color=COLOR_OK)
        self.card_values["estado"].configure(text="Conectado", text_color=COLOR_OK)
        self.card_values["servidor"].configure(text=self.client.base_url)
        self._set_busy(False, "")
        self._update_banner()

    def _set_disconnected(self, error: str | None = None) -> None:
        self.conn_status.configure(text=error or "Sin conexión",
                                   text_color=COLOR_ERR if error else "gray")
        self.card_values["estado"].configure(text="Error" if error else "Desconectado",
                                             text_color=COLOR_ERR if error else "gray")
        self.card_values["servidor"].configure(text="-")
        for key in ("total", "activas", "desactivadas"):
            self.card_values[key].configure(text="-")
        self._set_busy(False, "")
        self._update_banner()

    # ============================================================ consultas
    def _on_refresh(self) -> None:
        if self.manager is None:
            return
        self._run_async(self.manager.fetch_all, self._show_interfaces,
                        "GET /restconf/data/ietf-interfaces:interfaces ...")

    def _show_interfaces(self, outcome) -> None:
        if not outcome.ok:
            self.card_values["estado"].configure(text="Error", text_color=COLOR_ERR)
            messagebox.showerror("Error al consultar interfaces", outcome.error, parent=self)
            return
        self.card_values["estado"].configure(text="Conectado", text_color=COLOR_OK)
        selected = self.if_table.selection()
        selected_name = self.if_table.item(selected[0], "values")[0] if selected else None
        self.interfaces = outcome.interfaces
        self.if_table.delete(*self.if_table.get_children())
        for info in self.interfaces:
            tag = ("admin_down",) if info.enabled is False else (
                ("down",) if info.oper_status == "down" else ())
            iid = self.if_table.insert("", "end", values=(
                info.name, info.description, info.ip or "-",
                f"/{info.prefix}" if info.prefix is not None else "-",
                info.admin_status, info.oper_status), tags=tag)
            if info.name == selected_name:
                self.if_table.selection_set(iid)
        s = summarize(self.interfaces)
        self.card_values["total"].configure(text=str(s["total"]))
        self.card_values["activas"].configure(text=str(s["activas"]))
        self.card_values["desactivadas"].configure(text=str(s["desactivadas"]))
        note = "" if outcome.state_result and outcome.state_result.ok else \
            "  (estado operativo no disponible en el dispositivo)"
        self.status_line.configure(text=f"{s['total']} interfaces consultadas.{note}")

    def _on_get_one(self) -> None:
        info = self._selected()
        if info is None or self.manager is None:
            return

        def done(result) -> None:
            parsed, cfg, state = result
            if not cfg.ok:
                messagebox.showerror("Error", cfg.error, parent=self)
                return
            body = {"configuración": cfg.data}
            if state is not None and state.ok:
                body["estado"] = state.data
            self._show_json(f"GET {info.name}  -  HTTP {cfg.status}  -  {cfg.elapsed_ms:.0f} ms",
                            body)

        self._run_async(lambda: self.manager.fetch_one(info.name), done,
                        f"GET interfaz {info.name} ...")

    # ======================================================== modificaciones
    def _on_change_description(self) -> None:
        info = self._selected()
        if info is None:
            return
        dialog = _FormDialog(self, f"Descripción de {info.name}",
                             [("Nueva descripción", info.description)])
        values = dialog.result
        if values is None:
            return
        try:
            plan = self.manager.plan_description(info.name, values[0])
        except v.ValidationError as exc:
            messagebox.showwarning("Dato inválido", str(exc), parent=self)
            return
        self._confirm_and_apply(plan, info)

    def _on_toggle(self) -> None:
        info = self._selected()
        if info is None:
            return
        self._confirm_and_apply(self.manager.plan_enabled(info.name, not info.enabled), info)

    def _on_change_ip(self) -> None:
        info = self._selected()
        if info is None:
            return
        dialog = _FormDialog(self, f"Dirección IPv4 de {info.name}",
                             [("Dirección IP", info.ip),
                              ("Prefijo (1-32)", str(info.prefix or 24))])
        values = dialog.result
        if values is None:
            return
        try:
            v.validate_ipv4_host(values[0], values[1])
        except v.ValidationError as exc:
            messagebox.showwarning("Dato inválido", str(exc), parent=self)
            return

        def done(result) -> None:
            plan, read = result
            if plan is None:
                messagebox.showerror("No se pudo preparar el cambio", read.error, parent=self)
                return
            self._confirm_and_apply(plan, info)

        self._run_async(lambda: self.manager.plan_ipv4(info.name, values[0], values[1]), done,
                        f"Leyendo configuración actual de {info.name} (GET) ...")

    def _confirm_and_apply(self, plan: ChangePlan, before: InterfaceInfo) -> None:
        target = "al SIMULADOR local" if self.client.mode == MODE_SIM else \
            f"al DISPOSITIVO REAL {self.client.base_url}"
        text = (f"Se enviará la siguiente solicitud {target}:\n\n"
                f"Accion:   {plan.action}\nInterfaz: {plan.interface}\n"
                f"Método:   {plan.method}\nEndpoint: {plan.endpoint}\n\nCuerpo JSON:\n"
                f"{json.dumps(plan.body, indent=2, ensure_ascii=False)}\n\n"
                "Después se ejecutará un GET para verificar el resultado. Desea continuar?")
        if not _ConfirmDialog(self, "Confirmar modificación", text).confirmed:
            self.status_line.configure(text="Modificación cancelada por el usuario.")
            return
        self._run_async(lambda: self.manager.apply(plan),
                        lambda out: self._show_outcome(out, before),
                        f"{plan.method} {plan.endpoint} ...")

    def _show_outcome(self, out: ChangeOutcome, before: InterfaceInfo) -> None:
        res = out.apply_result
        if not res.ok:
            messagebox.showerror("La modificación fue rechazada",
                                 f"{out.plan.method} -> HTTP {res.status or '-'}\n\n{res.error}",
                                 parent=self)
        elif out.verified:
            after = out.after
            messagebox.showinfo(
                "Cambio aplicado y verificado",
                f"{out.plan.method} -> HTTP {res.status} ({res.elapsed_ms:.0f} ms)\n"
                f"Verificación GET -> HTTP {out.verify_result.status}\n\n"
                f"Antes:   desc='{before.description}', ip={before.ip_cidr or '-'}, "
                f"habilitada={before.enabled}\n"
                f"Después: desc='{after.description}', ip={after.ip_cidr or '-'}, "
                f"habilitada={after.enabled}", parent=self)
        else:
            detail = out.verify_result.error if out.verify_result and not out.verify_result.ok \
                else "\n".join(out.mismatches)
            messagebox.showwarning("Cambio enviado pero NO verificado",
                                   f"El dispositivo acepto la solicitud (HTTP {res.status}), "
                                   f"pero la verificación no coincide:\n\n{detail}", parent=self)
        self._on_refresh()

    # ============================================================ historial
    def _append_history(self, e: LogEntry) -> None:
        tag = ("error",) if e.resultado.startswith("ERROR") else ()
        path = e.endpoint.split("://", 1)[-1]
        path = path[path.find("/"):] if "/" in path else path
        self.hist_table.insert("", 0, values=(e.fecha.replace("T", " ")[:19], e.modo, e.operacion,
                                              e.metodo, path, e.codigo_http or "-", e.resultado,
                                              f"{e.tiempo_ms:.0f}"), tags=tag)

    def _export_history(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile="historial_operaciones.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            self.logger.export_csv(path)
            messagebox.showinfo("Historial exportado", f"Archivo guardado en:\n{path}",
                                parent=self)

    def _show_json(self, title: str, data: Any) -> None:
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("760x620")
        win.transient(self)
        box = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Consolas", size=13))
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))
        box.configure(state="disabled")


class _FormDialog(ctk.CTkToplevel):
    """Diálogo modal simple con uno o más campos de texto."""

    def __init__(self, parent, title: str, fields: list[tuple[str, str]]):
        super().__init__(parent)
        self.title(title)
        self.result: list[str] | None = None
        self.transient(parent)
        self.resizable(False, False)
        self.entries = []
        for i, (label, value) in enumerate(fields):
            ctk.CTkLabel(self, text=label).grid(row=i * 2, column=0, padx=16, pady=(12, 0),
                                                sticky="w")
            entry = ctk.CTkEntry(self, width=420)
            entry.insert(0, value or "")
            entry.grid(row=i * 2 + 1, column=0, columnspan=2, padx=16, sticky="ew")
            self.entries.append(entry)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=len(fields) * 2, column=0, columnspan=2, pady=14)
        ctk.CTkButton(buttons, text="Aceptar", command=self._ok).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Cancelar", fg_color="gray", command=self.destroy).pack(
            side="left", padx=6)
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(100, self._grab)
        self.wait_window()

    def _grab(self) -> None:
        try:
            self.grab_set()
            self.entries[0].focus_set()
        except tk.TclError:
            pass

    def _ok(self) -> None:
        self.result = [e.get() for e in self.entries]
        self.destroy()


class _ConfirmDialog(ctk.CTkToplevel):
    """Confirmación que muestra la solicitud exacta antes de enviarla."""

    def __init__(self, parent, title: str, text: str):
        super().__init__(parent)
        self.title(title)
        self.confirmed = False
        self.transient(parent)
        self.geometry("700x560")
        box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=13))
        box.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        box.insert("1.0", text)
        box.configure(state="disabled")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(pady=(0, 12))
        ctk.CTkButton(buttons, text="Confirmar y enviar", fg_color=COLOR_OK,
                      command=self._yes).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Cancelar", fg_color="gray", command=self.destroy).pack(
            side="left", padx=6)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(100, self._grab)
        self.wait_window()

    def _grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _yes(self) -> None:
        self.confirmed = True
        self.destroy()


def run(initial_mode: str = MODE_SIM) -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = Dashboard(initial_mode)
    app.mainloop()
