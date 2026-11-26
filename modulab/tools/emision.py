"""emitir_cotizacion: acción irreversible.

No se le da a ningún agente: la ejecuta el código solo cuando el dueño
presiona Confirmar y existe un token válido para ESTE contenido.
1. Gasta el token (confirmation.REGISTRO); sin token válido no pasa nada.
2. Toma el siguiente folio (secuencia de SQL Server) e inserta la cotización,
   que queda inmutable: el usuario de la app no puede modificarla ni borrarla.
3. Genera el documento oficial con folio y vigencia.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .. import config, db
from ..confirmation import REGISTRO, Token
from . import datos
from .salidas import generar_documento_oficial, lineas_de


class ArgsEmitirCotizacion(BaseModel):
    modulos: list[str] = Field(description="Ids de los módulos adicionales (sin los 3 base)")
    token: str = Field(description="Token de confirmación creado por el programa")


def contenido_de(modulos: list[str]) -> dict:
    """Lo que el dueño ve y confirma: líneas con precio oficial y total."""
    lineas = lineas_de(modulos)
    return {"lineas": [(l["id"], l["precio"]) for l in lineas], "total": sum(l["precio"] for l in lineas)}


def emitir_cotizacion(args: ArgsEmitirCotizacion) -> dict:
    contenido = contenido_de(args.modulos)
    REGISTRO.consumir(args.token, "emitir_cotizacion", contenido)  # lanza TokenInvalido si no sirve
    lineas = lineas_de(args.modulos)
    registro = db.repositorio().emitir_cotizacion(
        modulos=[l["id"] for l in lineas], total=contenido["total"],
        hash_contenido=Token.hash_de(contenido), codigo_negocio=datos.codigo_actual.get())
    archivo = generar_documento_oficial(lineas, registro["folio"], registro["fecha"], registro["vigencia"])
    return {"folio": registro["folio"], "vigencia": registro["vigencia"], "total_mxn": contenido["total"],
            "archivo": archivo, "vigencia_dias": config.VIGENCIA_DIAS}
