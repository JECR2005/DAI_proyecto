"""Contratos compartidos del proyecto (pydantic).

Todos los módulos importan sus tipos de aquí. Si cambias un contrato,
avisa al equipo: Gustavo (herramientas de datos y app.py) y Carlos
(validador, casos y trazas) dependen de estos modelos.

El modelo `Caso` (casos de prueba) lo mantiene Carlos en eval/.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Mensaje(BaseModel):
    """Mensaje de entrada normalizado (ficha, sección 6)."""
    sesion: str
    texto: str
    idioma: str = "es"


class Perfil(BaseModel):
    """Perfil del negocio guardado en memoria (SQL Server desde el jue 26).

    No tiene campos para datos de personas: ni del dueño ni de los niños
    o papás que atiende una estética infantil.
    """
    codigo_negocio: Optional[str] = None
    giro: Optional[str] = None
    tamano: Optional[str] = None
    presupuesto: Optional[float] = None
    necesidades: list[str] = Field(default_factory=list)
    modulos_previos: list[str] = Field(default_factory=list)
    # Texto libre del dueño: se guarda como dato NO confiable y se
    # reinyecta delimitado, nunca como instrucción.
    notas_no_confiables: Optional[str] = None


class ModuloRecomendado(BaseModel):
    id: str = Field(description="Id del módulo del catálogo, por ejemplo M04")
    motivo: str = Field(description="Por qué le sirve a este negocio, en una frase")
    doc_id: str = Field(description="Id del documento del catálogo que respalda la recomendación")


class ModuloDescartado(BaseModel):
    id: str = Field(description="Id del módulo del catálogo")
    motivo: str = Field(description="Por qué no aplica a este negocio")


class ModuloFueraPresupuesto(BaseModel):
    id: str = Field(description="Id del módulo útil que se deja fuera por presupuesto")
    motivo: str = Field(description="Para qué le serviría más adelante")


class Propuesta(BaseModel):
    """Salida del Analista de giro."""
    giro: str = Field(description="Giro del negocio con sus palabras, por ejemplo 'estética infantil'")
    resumen_negocio: str = Field(description="Resumen del negocio en dos frases, sin datos personales")
    presupuesto: Optional[float] = Field(default=None, description="Presupuesto en pesos si el dueño lo dijo")
    modulos: list[ModuloRecomendado] = Field(description="Módulos adicionales recomendados (sin los 3 base)")
    descartados: list[ModuloDescartado] = Field(default_factory=list)
    fuera_presupuesto: list[ModuloFueraPresupuesto] = Field(default_factory=list)
    fuera_catalogo: list[str] = Field(default_factory=list, description="Necesidades que no existen en el catálogo")


class LineaCotizacion(BaseModel):
    id: str
    nombre: str
    precio: float
    cantidad: int = 1

    @property
    def importe(self) -> float:
        return self.precio * self.cantidad


class Cotizacion(BaseModel):
    """Cotización armada por código: los precios SIEMPRE salen del CSV."""
    lineas: list[LineaCotizacion]
    total: float
    presupuesto: Optional[float] = None
    excede_presupuesto: bool = False
    fuera_presupuesto: list[LineaCotizacion] = Field(default_factory=list)


class Token(BaseModel):
    """Token de confirmación de un solo uso (confirmation.py, jue 26)."""
    accion: Literal["emitir_cotizacion", "sobrescribir_perfil"]
    hash_contenido: str
    usado: bool = False

    @staticmethod
    def hash_de(contenido: Any) -> str:
        datos = json.dumps(contenido, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(datos.encode("utf-8")).hexdigest()


class Traza(BaseModel):
    """Un registro por paso del agente (ficha, sección 6)."""
    ejecucion_id: str
    agente: str
    paso: int
    razonamiento: Optional[str] = None
    herramienta: Optional[str] = None
    args: Optional[dict[str, Any]] = None
    resultado: Optional[Any] = None
    tokens_entrada: int = 0
    tokens_salida: int = 0
    latencia_ms: int = 0
    modelo: Optional[str] = None
    error: Optional[str] = None
    momento: datetime = Field(default_factory=datetime.now)


class Respuesta(BaseModel):
    """Lo que el orquestador devuelve a la interfaz (consola o app.py)."""
    tipo: Literal["pregunta", "propuesta", "confirmacion", "emitida", "rechazo", "error"]
    texto: str
    propuesta: Optional[Propuesta] = None
    cotizacion: Optional[Cotizacion] = None
    archivos: dict[str, str] = Field(default_factory=dict)
    preguntas_hechas: int = 0
    # Confirmación humana: si requiere_confirmacion es True, la interfaz muestra los
    # botones Confirmar/Cancelar y llama a Orquestador.confirmar(sesion, aprobado).
    requiere_confirmacion: bool = False
    accion_pendiente: Optional[Literal["emitir_cotizacion", "sobrescribir_perfil"]] = None
    diferencia_perfil: Optional[dict[str, Any]] = None
    folio: Optional[str] = None
    vigencia: Optional[str] = None
    codigo_negocio: Optional[str] = None
