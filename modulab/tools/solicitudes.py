"""registrar_solicitud_especial: necesidades que no existen en el catálogo.

En memoria para la rebanada; el vie 27 se guarda en SQL Server
(tabla solicitudes_especiales). Nunca lleva precio.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

SOLICITUDES: list[dict] = []


class ArgsSolicitudEspecial(BaseModel):
    descripcion: str = Field(description="Lo que pidió el dueño y no existe en el catálogo")
    giro: str = Field(description="Giro del negocio")


def registrar_solicitud_especial(args: ArgsSolicitudEspecial) -> dict:
    folio = f"SOL-{len(SOLICITUDES) + 1:04d}"
    SOLICITUDES.append({"id": folio, **args.model_dump()})
    return {"id": folio, "registrada": True,
            "nota": "No existe en el catálogo: no tiene precio; el desarrollador la cotiza aparte."}
