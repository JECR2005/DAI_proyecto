"""Herramientas terminales: así un agente cierra su turno y entrega resultados.

No son de las 9 herramientas de dominio de la ficha; son la forma en que
cada trabajador le devuelve el control al orquestador. Carlos puede
excluirlas de la métrica de secuencia de herramientas.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..schemas import Propuesta


class ArgsPreguntar(BaseModel):
    pregunta: str = Field(description="Una sola pregunta clara para el dueño, sin tecnicismos")


class ArgsEntregarCotizacion(BaseModel):
    modulos: list[str] = Field(description="Ids de los módulos adicionales finales (sin los 3 base)")
    resumen: str = Field(description="Resumen breve para el dueño, sin precios (los pone el sistema)")


class ArgsEntregarConfiguracion(BaseModel):
    resumen: str = Field(description="Qué adaptaste del sitio para este negocio, en una frase y sin precios")


ArgsEntregarPropuesta = Propuesta
