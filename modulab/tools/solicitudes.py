"""registrar_solicitud_especial: necesidades que no existen en el catálogo.

Se guardan en SQL Server (tabla solicitudes_especiales) para que el
desarrollador las cotice aparte. Nunca llevan precio.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .. import db
from . import datos


class ArgsSolicitudEspecial(BaseModel):
    descripcion: str = Field(description="Lo que pidió el dueño y no existe en el catálogo")
    giro: str = Field(description="Giro del negocio")


def registrar_solicitud_especial(args: ArgsSolicitudEspecial) -> dict:
    numero = db.repositorio().registrar_solicitud(
        descripcion=args.descripcion, giro=args.giro,
        sesion=datos.sesion_actual.get(), codigo_negocio=datos.codigo_actual.get())
    return {"id": f"SOL-{numero:04d}", "registrada": True,
            "nota": "No existe en el catálogo: no tiene precio; el desarrollador la cotiza aparte."}
