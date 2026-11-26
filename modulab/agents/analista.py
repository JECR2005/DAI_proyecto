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


def revisar_coherencia(propuesta, preguntas_hechas: int) -> list[str]:
    """Reglas del analista que el prompt no logra garantizar (corridas reales del 25 y 26 nov).

    No sustituye al validador V1–V9 de Carlos: revisa decisiones de la entrevista, no cálculos.
    """
    from ..tools import datos

    errores = []
    catalogo = datos.modulos()
    giro = (propuesta.giro or "").lower()
    del_giro = {mid for mid, m in catalogo.items()
                if m["tipo"] != "base" and any(g != "todos" and (g in giro or giro in g) for g in m["giros"])}
    for d in propuesta.descartados:
        if d.id in del_giro:
            errores.append(
                f"Descartaste {d.id} ({catalogo[d.id]['nombre']}), pero el catálogo lo marca para el giro "
                f"'{propuesta.giro}'. Si no alcanza el presupuesto, ponlo en fuera_presupuesto con para qué le "
                "serviría; si no sabes si lo necesita, pregúntale al dueño.")
    if preguntas_hechas == 0 and (propuesta.fuera_presupuesto or any(d.id in del_giro for d in propuesta.descartados)):
        errores.append(
            "El presupuesto te obliga a elegir entre módulos que sirven a este giro y no has hecho ninguna pregunta: "
            "antes de entregar, pregúntale al dueño cuál le importa más (una sola pregunta).")
    return errores
