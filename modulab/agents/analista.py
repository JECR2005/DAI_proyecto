"""Analista de giro: entrevista al dueño y entrega una Propuesta."""
from __future__ import annotations

import re

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
    # Pregunta con preguntar_al_dueno y entrega con entregar_propuesta: el texto suelto no cierra el turno.
    return ejecutar_agente(NOMBRE, prompt(), mensajes, herramientas, cliente, trazador, solo_herramientas=True)


def montos_en(texto: str) -> set[float]:
    """Cantidades que escribió el dueño ("$4,000", "8 mil", "8000"), para saber qué presupuesto dio."""
    montos = set()
    for numero, mil in re.findall(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(mil\b)?", texto.lower()):
        valor = float(numero.replace(",", ""))
        montos.add(valor * 1000 if mil else valor)
    return montos


def revisar_coherencia(propuesta, preguntas_hechas: int, preguntar_recorte: bool = False,
                       montos_dueno: set[float] | None = None) -> list[str]:
    """Reglas del analista que el prompt no logra garantizar (corridas reales del 25 y 26 nov).

    1. Sin haber preguntado nada, no puede descartar un módulo que el catálogo marca para el giro.
    2. Lo que va en fuera_presupuesto debe NO caber de verdad (si cabe, se incluye o se descarta
       con lo que dijo el dueño).
    3. Si deja módulos del giro fuera por presupuesto sin haber preguntado, debe preguntar primero.
    4. El total no puede pasarse del presupuesto (corrida real COT-2026-0007: $8,900 de $8,000).
       Con preguntar_recorte, la primera vez debe preguntarle al dueño qué deja fuera en lugar de elegir
       solo (casos de desarrollo del 26-nov: quitó lo que la dueña había pedido).
    5. El presupuesto de la propuesta debe ser una cifra que el dueño escribió (27-nov: inventó $4,800).
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
        if montos_dueno is not None and propuesta.presupuesto not in montos_dueno:
            dichos = ", ".join(f"${m:,.0f}" for m in sorted(montos_dueno) if m >= 1000) or "ninguna cifra"
            errores.append(f"El dueño nunca dijo ${propuesta.presupuesto:,.0f}; las cantidades que escribió son "
                           f"{dichos}. Usa el presupuesto que él dio y no lo cambies sin que diga otra cifra.")
        if sobra < 0:
            base = sum(l["precio"] for l in lineas_de([]))
            exceso = (f"Tu total es ${total:,.0f} y el presupuesto es ${propuesta.presupuesto:,.0f} (te pasas por "
                      f"${-sobra:,.0f}). " + (f"La base (${base:,.0f}) siempre cuenta dentro del presupuesto: para "
                      f"módulos adicionales quedan ${max(propuesta.presupuesto - base, 0):,.0f}. " if base else ""))
            if preguntar_recorte:
                errores.append(exceso + "No decidas tú qué quitar: pregúntale al dueño (una sola pregunta, con el "
                               "total y el precio de cada opción) qué prefiere dejar para después o si puede gastar más.")
            else:
                errores.append(exceso + "Deja en modulos solo lo que quepa, empezando por lo que el dueño pidió "
                               "primero; lo demás va a fuera_presupuesto, aunque él lo haya pedido (explica que no "
                               "alcanza). Cambia el presupuesto solo si el dueño escribió otra cifra.")
        for f in propuesta.fuera_presupuesto:
            if f.id not in precios or f.id in incluidos:
                continue
            costo = sum(l["precio"] for l in lineas_de(incluidos + [f.id])) - total  # con sus dependencias
            if costo <= sobra:
                errores.append(
                    f"{f.id} ({catalogo[f.id]['nombre']}, ${costo:,.0f} con lo que requiere) sí cabe: tu total es "
                    f"${total:,.0f} de ${propuesta.presupuesto:,.0f} (sobran ${sobra:,.0f}). Inclúyelo, o si el dueño "
                    "dijo que no lo quiere, ponlo en descartados con lo que dijo. No quites lo que el dueño eligió.")

    if preguntas_hechas == 0 and any(f.id in del_giro for f in propuesta.fuera_presupuesto):
        errores.append(
            "El presupuesto te obliga a elegir entre módulos que sirven a este giro y no has hecho ninguna pregunta: "
            "antes de entregar, pregúntale al dueño cuál le importa más (una sola pregunta).")
    return errores
