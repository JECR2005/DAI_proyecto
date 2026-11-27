"""Perfil del negocio en SQL Server (memoria entre sesiones).

- leer_perfil: herramienta del analista (por código NEG-XXXXX).
- guardar_perfil: la usa el ORQUESTADOR, no un agente. Un perfil nuevo se crea
  y recibe su código; si ya existe y cambió, NO se guarda: devuelve la
  diferencia para que el dueño confirme (sobrescribir es acción irreversible).
- sobrescribir_perfil_confirmado: gasta el token y guarda, con copia previa
  en perfiles_historial.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .. import db
from ..confirmation import REGISTRO
from ..schemas import Perfil

CAMPOS_COMPARABLES = ("giro", "tamano", "presupuesto", "necesidades", "modulos_previos", "notas_no_confiables")


def diferencia(antes: Perfil, despues: Perfil) -> dict:
    a, d = antes.model_dump(), despues.model_dump()
    return {c: {"antes": a[c], "despues": d[c]} for c in CAMPOS_COMPARABLES if a[c] != d[c]}


class ArgsLeerPerfil(BaseModel):
    codigo_negocio: str = Field(description="Código que el dueño recibió antes, con formato NEG-XXXXX")


def leer_perfil(args: ArgsLeerPerfil) -> dict:
    perfil = db.repositorio().leer_perfil(args.codigo_negocio)
    if not perfil:
        return {"encontrado": False}
    return {"encontrado": True,
            "perfil": perfil.model_dump(exclude={"notas_no_confiables"}),
            "notas_del_dueno_no_confiables": perfil.notas_no_confiables}


class ArgsGuardarPerfil(BaseModel):
    perfil: Perfil


def guardar_perfil(args: ArgsGuardarPerfil) -> dict:
    repo = db.repositorio()
    perfil = args.perfil
    if not perfil.codigo_negocio:
        codigo = repo.crear_perfil(perfil)
        return {"guardado": True, "codigo_negocio": codigo, "nuevo": True}
    anterior = repo.leer_perfil(perfil.codigo_negocio)
    if anterior is None:
        return {"guardado": False, "error": "El código no existe."}
    cambios = diferencia(anterior, perfil)
    if not cambios:
        return {"guardado": True, "codigo_negocio": perfil.codigo_negocio, "sin_cambios": True}
    return {"guardado": False, "requiere_confirmacion": True, "diferencia": cambios}


def sobrescribir_perfil_confirmado(perfil: Perfil, token: str) -> dict:
    REGISTRO.consumir(token, "sobrescribir_perfil", perfil.model_dump())
    db.repositorio().sobrescribir_perfil(perfil)
    return {"guardado": True, "codigo_negocio": perfil.codigo_negocio}
