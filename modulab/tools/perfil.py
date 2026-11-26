"""leer_perfil y guardar_perfil.

STUB en memoria para la rebanada vertical. El jue 26 pasan a SQL Server
(db.py) con diferencia antes/después, copia en perfiles_historial y
confirmación por token al sobrescribir.
"""
from __future__ import annotations

import secrets
import string

from pydantic import BaseModel, Field

from ..schemas import Perfil

_PERFILES: dict[str, Perfil] = {}


def nuevo_codigo() -> str:
    alfabeto = string.ascii_uppercase + string.digits
    return "NEG-" + "".join(secrets.choice(alfabeto) for _ in range(5))


class ArgsLeerPerfil(BaseModel):
    codigo_negocio: str = Field(description="Código que el dueño recibió antes, con formato NEG-XXXXX")


def leer_perfil(args: ArgsLeerPerfil) -> dict:
    perfil = _PERFILES.get(args.codigo_negocio.strip().upper())
    if not perfil:
        return {"encontrado": False}
    return {"encontrado": True, "perfil": perfil.model_dump()}


class ArgsGuardarPerfil(BaseModel):
    perfil: Perfil


def guardar_perfil(args: ArgsGuardarPerfil) -> dict:
    perfil = args.perfil
    if perfil.codigo_negocio and perfil.codigo_negocio in _PERFILES:
        # TODO jue 26: mostrar diferencia y exigir token de confirmación.
        return {"guardado": False, "motivo": "Ya existe: sobrescribir requiere confirmación (pendiente jue 26)."}
    perfil.codigo_negocio = perfil.codigo_negocio or nuevo_codigo()
    _PERFILES[perfil.codigo_negocio] = perfil
    return {"guardado": True, "codigo_negocio": perfil.codigo_negocio}
