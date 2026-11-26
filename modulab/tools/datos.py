"""Acceso al catálogo y a la lista de precios (archivos de Gustavo en data/)."""
from __future__ import annotations

import contextvars
import csv
import json
from functools import lru_cache
from pathlib import Path

from .. import config

# Carpeta de salida de la sesión actual (la fija el orquestador).
carpeta_sesion: contextvars.ContextVar[Path] = contextvars.ContextVar(
    "carpeta_sesion", default=config.OUTPUTS_DIR / "sin_sesion")


@lru_cache(maxsize=1)
def catalogo() -> dict:
    return json.loads(config.CATALOGO_PATH.read_text(encoding="utf-8"))


def modulos() -> dict[str, dict]:
    return {m["id"]: m for m in catalogo()["modulos"]}


@lru_cache(maxsize=1)
def precios() -> dict[str, dict]:
    with config.PRECIOS_PATH.open(encoding="utf-8") as f:
        return {fila["id"]: {"nombre": fila["nombre"], "precio": float(fila["precio_mxn"])}
                for fila in csv.DictReader(f)}


def recargar() -> None:
    catalogo.cache_clear()
    precios.cache_clear()

# Sesión y negocio actuales (los fija el orquestador; las herramientas los usan al guardar).
sesion_actual: contextvars.ContextVar[str] = contextvars.ContextVar("sesion_actual", default="sin_sesion")
codigo_actual: contextvars.ContextVar[str | None] = contextvars.ContextVar("codigo_actual", default=None)
# Módulos que el negocio ya tiene contratados (cliente que regresa): no se vuelven a cotizar.
contratados_actual: contextvars.ContextVar[tuple] = contextvars.ContextVar("contratados_actual", default=())
