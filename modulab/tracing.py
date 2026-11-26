"""Trazas JSON por ejecución (una línea por paso).

PROVISIONAL: Carlos es dueño de este módulo y puede ampliarlo (visor,
guardar también en SQL Server). Mantengan la firma `Trazador.registrar`.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from . import config
from .schemas import Traza


class Trazador:
    def __init__(self, ejecucion_id: Optional[str] = None, carpeta: Path = config.TRAZAS_DIR,
                 en_consola: bool = False):
        self.ejecucion_id = ejecucion_id or uuid.uuid4().hex[:12]
        self.archivo = carpeta / f"{self.ejecucion_id}.jsonl"
        self.en_consola = en_consola
        self.registros: list[Traza] = []

    def registrar(self, **campos) -> Traza:
        traza = Traza(ejecucion_id=self.ejecucion_id, **campos)
        self.registros.append(traza)
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        with self.archivo.open("a", encoding="utf-8") as f:
            f.write(traza.model_dump_json() + "\n")
        if self.en_consola:
            if traza.agente == "validador":
                print(f"   [traza] validador: propuesta regresada para corregir -> {traza.error}")
            else:
                detalle = traza.herramienta or traza.razonamiento or "respuesta"
                print(f"   [traza] {traza.agente} paso {traza.paso}: {detalle}"
                      + (f" (error: {traza.error})" if traza.error else ""))
        return traza

    @property
    def herramientas_usadas(self) -> list[str]:
        return [t.herramienta for t in self.registros if t.herramienta]
