"""emitir_cotizacion: acción irreversible.

PENDIENTE (jue 26): verificar token de confirmation.py, tomar
NEXT VALUE FOR seq_folios en SQL Server, insertar en cotizaciones_emitidas
y generar el PDF oficial con la función de Gustavo.

No se le da a ningún agente: la ejecuta el código cuando el dueño presiona
Confirmar.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ArgsEmitirCotizacion(BaseModel):
    modulos: list[str] = Field(description="Ids de los módulos adicionales")
    token: str = Field(description="Token de confirmación creado por el programa")


def emitir_cotizacion(args: ArgsEmitirCotizacion) -> dict:
    raise NotImplementedError("emitir_cotizacion se implementa el jue 26 (token + SQL Server).")
