"""Confirmación humana para acciones irreversibles.

La confirmación NO es una frase del modelo ni del dueño: es un token que solo
crea este módulo cuando una persona aprueba (botón Confirmar en la interfaz)
o, en pruebas automáticas, cuando el proveedor está en modo siempre_si/guion.

- Un token sirve UNA sola vez.
- Está ligado a la acción y al hash del contenido que se mostró al dueño:
  si el contenido cambia, el token ya no sirve.
- Escribir "confirmo" en el chat no crea ningún token.
"""
from __future__ import annotations

import secrets
import threading
from typing import Any, Optional

from .schemas import Token

ACCIONES = ("emitir_cotizacion", "sobrescribir_perfil")


class TokenInvalido(Exception):
    pass


class RegistroTokens:
    def __init__(self):
        self._tokens: dict[str, Token] = {}
        self._lock = threading.Lock()

    def crear(self, accion: str, contenido: Any) -> str:
        if accion not in ACCIONES:
            raise ValueError(f"Acción desconocida: {accion}")
        valor = secrets.token_urlsafe(24)
        with self._lock:
            self._tokens[valor] = Token(accion=accion, hash_contenido=Token.hash_de(contenido))
        return valor

    def consumir(self, valor: Optional[str], accion: str, contenido: Any) -> None:
        """Valida y gasta el token. Lanza TokenInvalido si no sirve."""
        with self._lock:
            token = self._tokens.get(valor or "")
            if token is None:
                raise TokenInvalido("No hay confirmación válida para esta acción.")
            if token.usado:
                raise TokenInvalido("Esta confirmación ya se usó.")
            if token.accion != accion:
                raise TokenInvalido("La confirmación es para otra acción.")
            if token.hash_contenido != Token.hash_de(contenido):
                raise TokenInvalido("El contenido cambió desde que se confirmó.")
            token.usado = True


REGISTRO = RegistroTokens()


class ProveedorConfirmacion:
    """Decide si una acción irreversible se aprueba.

    modos:
      ui         -> queda pendiente hasta que la interfaz llame a `decidir` (botón Confirmar)
      siempre_si -> aprueba (pruebas automáticas)
      siempre_no -> rechaza (pruebas automáticas)
      guion      -> toma la siguiente decisión de una lista de True/False
    """

    PENDIENTE = "pendiente"

    def __init__(self, modo: str = "ui", guion: Optional[list[bool]] = None,
                 registro: RegistroTokens = REGISTRO):
        if modo not in ("ui", "siempre_si", "siempre_no", "guion"):
            raise ValueError(f"Modo de confirmación desconocido: {modo}")
        self.modo = modo
        self._guion = list(guion or [])
        self.registro = registro

    def solicitar(self, accion: str, contenido: Any):
        """Devuelve un token (aprobado), None (rechazado) o PENDIENTE (espera a la interfaz)."""
        if self.modo == "ui":
            return self.PENDIENTE
        if self.modo == "siempre_si":
            aprobado = True
        elif self.modo == "siempre_no":
            aprobado = False
        else:
            aprobado = self._guion.pop(0) if self._guion else False
        return self.registro.crear(accion, contenido) if aprobado else None

    def decidir(self, accion: str, contenido: Any, aprobado: bool) -> Optional[str]:
        """Lo llama la interfaz cuando la persona presiona Confirmar o Cancelar."""
        return self.registro.crear(accion, contenido) if aprobado else None
