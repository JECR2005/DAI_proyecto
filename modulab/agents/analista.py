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

    1. Sin haber preguntado nada, no puede descartar un módulo que el catálogo marca para el giro.
    2. Lo que va en fuera_presupuesto debe NO caber de verdad (si cabe, se incluye o se descarta
       con lo que dijo el dueño).
    3. Si deja módulos del giro fuera por presupuesto sin haber preguntado, debe preguntar primero.
    No sustituye al validador V1–V9 de Carlos: revisa decisiones de la entrevista, no cálculos.
    """
    from ..tools import datos
    from ..tools.salidas import lineas_de

    errores = []
    catalogo = datos.modulos()
    precios = datos.precios()
    giro = (propuesta.giro or "").lower()
    contratados = set(datos.contratados_actual.get())
    del_giro = {mid for mid, m in catalogo.items()
                if m["tipo"] != "base" and mid not in contratados
                and any(g != "todos" and (g in giro or giro in g) for g in m["giros"])}

    if preguntas_hechas == 0:
        for d in propuesta.descartados:
            if d.id in del_giro:
                errores.append(
                    f"Descartaste {d.id} ({catalogo[d.id]['nombre']}) sin preguntar, pero el catálogo lo marca para el "
                    f"giro '{propuesta.giro}'. Pregúntale al dueño si le sirve o, si no alcanza el presupuesto, ponlo en "
                    "fuera_presupuesto.")

    if propuesta.presupuesto:
        incluidos = [m.id for m in propuesta.modulos]
        total = sum(l["precio"] for l in lineas_de(incluidos))
        sobra = propuesta.presupuesto - total
        for f in propuesta.fuera_presupuesto:
            if f.id in precios and f.id not in incluidos and precios[f.id]["precio"] <= sobra:
                errores.append(
                    f"{f.id} ({catalogo[f.id]['nombre']}, ${precios[f.id]['precio']:,.0f}) sí cabe: tu total es "
                    f"${total:,.0f} de ${propuesta.presupuesto:,.0f} (sobran ${sobra:,.0f}). Inclúyelo, o si el dueño "
                    "dijo que no lo quiere, ponlo en descartados con lo que dijo. No quites lo que el dueño eligió.")

    if preguntas_hechas == 0 and any(f.id in del_giro for f in propuesta.fuera_presupuesto):
        errores.append(
            "El presupuesto te obliga a elegir entre módulos que sirven a este giro y no has hecho ninguna pregunta: "
            "antes de entregar, pregúntale al dueño cuál le importa más (una sola pregunta).")
    return errores
