"""Validador determinista V1–V9.

PROVISIONAL: Carlos es dueño de este módulo y lo completa el jue 26 con
las 9 reglas y sus pruebas. El orquestador ya llama a estas dos funciones;
mantengan las firmas: devuelven una lista de errores (vacía = pasa).
"""
from __future__ import annotations

from .schemas import Cotizacion, Propuesta


def validar_propuesta(propuesta: Propuesta) -> list[str]:
    return []  # TODO Carlos: V3 (módulos existen), V4 (dependencias), V9 (doc_id respalda módulo)


def validar_cotizacion(cotizacion: Cotizacion, propuesta: Propuesta) -> list[str]:
    return []  # TODO Carlos: V1 (total), V5 (base), V6 (presupuesto), V8 (precios del CSV)
