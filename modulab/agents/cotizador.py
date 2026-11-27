"""Cotizador/Configurador: prepara configuración, maqueta y cotización en borrador.

El modelo solo decide qué herramientas llamar y la lista de módulos; los
precios y el total los arma `armar_cotizacion` desde el CSV.
"""
from __future__ import annotations

import json
from typing import Optional

from .. import config
from ..llm import ClienteLLM
from ..loop import ResultadoAgente, ejecutar_agente
from ..schemas import Cotizacion, LineaCotizacion, Propuesta
from ..tools import HERRAMIENTAS_COTIZADOR
from ..tools import datos
from ..tools.salidas import lineas_de
from ..tracing import Trazador

VERSION_PROMPT = "cotizador_v1"
NOMBRE = "cotizador"


def prompt() -> str:
    return (config.PROMPTS_DIR / f"{VERSION_PROMPT}.md").read_text(encoding="utf-8")


def ejecutar(propuesta: Propuesta, cliente: ClienteLLM, trazador: Trazador,
             correcciones: Optional[str] = None) -> ResultadoAgente:
    contenido = "Propuesta aprobada por el Analista de giro:\n" + json.dumps(
        propuesta.model_dump(), ensure_ascii=False, indent=2)
    if correcciones:
        contenido += f"\n\nEl validador rechazó la entrega anterior. Corrige: {correcciones}"
    mensajes = [{"role": "user", "content": contenido}]
    return ejecutar_agente(NOMBRE, prompt(), mensajes, HERRAMIENTAS_COTIZADOR, cliente, trazador,
                           solo_herramientas=True)


def armar_cotizacion(modulos: list[str], propuesta: Propuesta) -> Cotizacion:
    lineas = [LineaCotizacion(**l) for l in lineas_de(modulos)]
    total = sum(l.importe for l in lineas)
    precios = datos.precios()
    fuera = [LineaCotizacion(id=f.id, nombre=precios[f.id]["nombre"], precio=precios[f.id]["precio"])
             for f in propuesta.fuera_presupuesto if f.id in precios]
    excede = propuesta.presupuesto is not None and total > propuesta.presupuesto
    return Cotizacion(lineas=lineas, total=total, presupuesto=propuesta.presupuesto,
                      excede_presupuesto=excede, fuera_presupuesto=fuera)
