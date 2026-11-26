"""Analista de giro: entrevista al dueño y entrega una Propuesta."""
from __future__ import annotations

from .. import config
from ..llm import ClienteLLM
from ..loop import ResultadoAgente, ejecutar_agente
from ..tools import HERRAMIENTAS_ANALISTA, PREGUNTAR_AL_DUENO
from ..tracing import Trazador

VERSION_PROMPT = "analista_v2"
NOMBRE = "analista"


def prompt() -> str:
    return (config.PROMPTS_DIR / f"{VERSION_PROMPT}.md").read_text(encoding="utf-8")


def ejecutar(mensajes: list[dict], cliente: ClienteLLM, trazador: Trazador,
             puede_preguntar: bool = True) -> ResultadoAgente:
    herramientas = [h for h in HERRAMIENTAS_ANALISTA if puede_preguntar or h is not PREGUNTAR_AL_DUENO]
    return ejecutar_agente(NOMBRE, prompt(), mensajes, herramientas, cliente, trazador)
