"""Configurador (tercer agente): adapta la configuración y la maqueta del sitio al giro del negocio.

Recibe la propuesta y la lista final de módulos ya cotizada. Solo cambia textos y orden: el código
de generar_configuracion rechaza módulos que el sitio no tendrá y cualquier precio en los textos.
Si falla, el orquestador genera la maqueta genérica por código, así que el flujo no se rompe.
"""
from __future__ import annotations

import json

from .. import config
from ..llm import ClienteLLM
from ..loop import ResultadoAgente, ejecutar_agente
from ..schemas import Propuesta
from ..tools import HERRAMIENTAS_CONFIGURADOR
from ..tools import datos
from ..tracing import Trazador

VERSION_PROMPT = "configurador_v1"
NOMBRE = "configurador"
MAX_PASOS = 4


def prompt() -> str:
    return (config.PROMPTS_DIR / f"{VERSION_PROMPT}.md").read_text(encoding="utf-8")


def ejecutar(propuesta: Propuesta, modulos: list[str], cliente: ClienteLLM, trazador: Trazador) -> ResultadoAgente:
    catalogo = datos.modulos()
    contratados = list(datos.contratados_actual.get())
    sitio = list(dict.fromkeys(config.MODULOS_BASE + contratados + modulos))
    contenido = json.dumps({
        "giro": propuesta.giro,
        "resumen_negocio": propuesta.resumen_negocio,
        "modulos_adicionales": modulos,
        "motivos": {m.id: m.motivo for m in propuesta.modulos},
        "modulos_del_sitio": {m: catalogo[m]["nombre"] for m in sitio if m in catalogo},
    }, ensure_ascii=False, indent=2)
    mensajes = [{"role": "user", "content": "Configura el sitio de este negocio:\n" + contenido}]
    return ejecutar_agente(NOMBRE, prompt(), mensajes, HERRAMIENTAS_CONFIGURADOR, cliente, trazador,
                           max_pasos=MAX_PASOS, solo_herramientas=True)
