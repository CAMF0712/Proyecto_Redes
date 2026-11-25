"""Registro de operaciones RESTCONF.

Cada entrada guarda: fecha, modo, operación, método, endpoint, código HTTP,
resultado y tiempo de respuesta. NUNCA se registran contraseñas, encabezados
de autorizacion ni cuerpos de solicitud.
"""

from __future__ import annotations

import csv
import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

DEFAULT_LOG_FILE = Path("logs") / "operaciones.jsonl"


@dataclass
class LogEntry:
    fecha: str
    modo: str
    operacion: str
    metodo: str
    endpoint: str
    codigo_http: int | None
    resultado: str
    tiempo_ms: float


def strip_credentials(url: str) -> str:
    """Elimina usuario y contraseña incrustados en una URL (user:pass@host)."""
    parts = urlsplit(url)
    if parts.username or parts.password:
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        parts = parts._replace(netloc=host)
    return urlunsplit(parts)


class OperationLogger:
    def __init__(self, log_file: Path | str | None = DEFAULT_LOG_FILE):
        self._lock = threading.Lock()
        self._entries: list[LogEntry] = []
        self._listeners: list[Callable[[LogEntry], None]] = []
        self.log_file = Path(log_file) if log_file else None
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def add_listener(self, callback: Callable[[LogEntry], None]) -> None:
        self._listeners.append(callback)

    def record(self, modo: str, operacion: str, metodo: str, endpoint: str,
               codigo_http: int | None, resultado: str, tiempo_ms: float) -> LogEntry:
        entry = LogEntry(
            fecha=datetime.now().astimezone().isoformat(timespec="seconds"),
            modo=modo,
            operacion=operacion,
            metodo=metodo,
            endpoint=strip_credentials(endpoint),
            codigo_http=codigo_http,
            resultado=resultado,
            tiempo_ms=round(tiempo_ms, 1),
        )
        with self._lock:
            self._entries.append(entry)
            if self.log_file:
                with self.log_file.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        for callback in list(self._listeners):
            try:
                callback(entry)
            except Exception:  # noqa: BLE001 - un listener defectuoso no debe romper el registro
                pass
        return entry

    @property
    def entries(self) -> list[LogEntry]:
        with self._lock:
            return list(self._entries)

    def export_csv(self, path: Path | str) -> Path:
        path = Path(path)
        with path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(LogEntry.__dataclass_fields__))
            writer.writeheader()
            for entry in self.entries:
                writer.writerow(asdict(entry))
        return path
