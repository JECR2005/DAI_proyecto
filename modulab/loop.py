"""Bucle ReAct genérico: pensar -> llamar herramienta -> observar, con tope de pasos.

Cada agente (analista, cotizador) es una llamada a `ejecutar_agente` con su
propio system prompt y su propio subconjunto de herramientas. El bucle
termina cuando el modelo llama a una herramienta *terminal* (por ejemplo
`preguntar_al_dueno` o `entregar_propuesta`), cuando responde solo con
texto, o cuando llega al tope de pasos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel, ValidationError

from . import config
from .llm import ClienteLLM, ErrorLLM
from .tracing import Trazador


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    Args: type[BaseModel]
    funcion: Optional[Callable[[BaseModel], Any]] = None
    terminal: bool = False

    def especificacion(self) -> dict:
        return {"nombre": self.nombre, "descripcion": self.descripcion,
                "parametros": esquema_plano(self.Args)}


@dataclass
class ResultadoAgente:
    terminal: Optional[str] = None          # nombre de la herramienta terminal que cerró el turno
    args: Optional[BaseModel] = None        # sus argumentos ya validados
    texto: Optional[str] = None             # texto libre si el modelo no llamó herramientas
    pasos: int = 0
    agotado: bool = False                   # llegó al tope de pasos
    error: Optional[str] = None
    herramientas: list[str] = field(default_factory=list)


def esquema_plano(modelo: type[BaseModel]) -> dict:
    """JSON Schema sin $ref, $defs ni títulos (lo aceptan Gemini y Groq)."""
    esquema = modelo.model_json_schema()
    definiciones = esquema.pop("$defs", {})

    def resolver(nodo):
        if isinstance(nodo, dict):
            if "$ref" in nodo:
                return resolver(definiciones[nodo["$ref"].split("/")[-1]])
            if "anyOf" in nodo:  # Optional[X] -> X con nullable
                opciones = [o for o in nodo["anyOf"] if o.get("type") != "null"]
                base = resolver(opciones[0]) if opciones else {"type": "string"}
                extra = {k: v for k, v in nodo.items() if k not in ("anyOf", "title", "default")}
                return {**base, **extra}
            return {k: resolver(v) for k, v in nodo.items() if k not in ("title", "default")}
        if isinstance(nodo, list):
            return [resolver(x) for x in nodo]
        return nodo

    return resolver(esquema)


def ejecutar_agente(agente: str, system: str, mensajes: list[dict], herramientas: list[Herramienta],
                    cliente: ClienteLLM, trazador: Trazador,
                    max_pasos: int = config.MAX_PASOS_POR_TURNO) -> ResultadoAgente:
    """Corre un turno del agente. `mensajes` se modifica en su lugar (memoria del agente)."""
    registro = {h.nombre: h for h in herramientas}
    especificaciones = [h.especificacion() for h in herramientas]
    resultado = ResultadoAgente()

    for paso in range(1, max_pasos + 1):
        resultado.pasos = paso
        try:
            r = cliente.chat(system, mensajes, especificaciones, agente=agente)
            if getattr(cliente, "respaldo", None):  # el principal falló y respondió el de respaldo
                trazador.registrar(agente=agente, paso=paso, modelo=r.modelo,
                                   error="se usó el modelo de respaldo: " + " | ".join(cliente.respaldo)[:300])
        except ErrorLLM as e:
            trazador.registrar(agente=agente, paso=paso, error=str(e))
            resultado.error = str(e)
            return resultado

        mensaje_modelo: dict[str, Any] = {
            "role": "assistant", "content": r.texto,
            "tool_calls": [{"id": ll.id, "name": ll.nombre, "args": ll.args} for ll in r.llamadas]}
        if r.crudo is not None:
            mensaje_modelo["crudo_gemini"] = r.crudo
        mensajes.append(mensaje_modelo)

        comunes = dict(agente=agente, paso=paso, razonamiento=r.texto, modelo=r.modelo,
                       tokens_entrada=r.tokens_entrada, tokens_salida=r.tokens_salida,
                       latencia_ms=r.latencia_ms)

        if not r.llamadas:
            trazador.registrar(**comunes)
            resultado.texto = r.texto
            return resultado

        cierre: Optional[tuple[str, BaseModel]] = None
        for ll in r.llamadas:
            if cierre:  # ya hubo una herramienta terminal en esta respuesta
                _responder(mensajes, ll, {"omitida": "El turno ya se cerró con otra herramienta."})
                continue
            h = registro.get(ll.nombre)
            if h is None:
                salida = {"error": f"La herramienta '{ll.nombre}' no existe o no está disponible para ti."}
                _responder(mensajes, ll, salida)
                trazador.registrar(**comunes, herramienta=ll.nombre, args=ll.args, error=salida["error"])
                continue
            try:
                args = h.Args.model_validate(ll.args)
            except ValidationError as e:
                salida = {"error": "Argumentos inválidos; corrígelos y vuelve a llamar.",
                          "detalle": e.errors(include_url=False, include_context=False)}
                _responder(mensajes, ll, salida)
                trazador.registrar(**comunes, herramienta=ll.nombre, args=ll.args, error="argumentos inválidos")
                continue

            resultado.herramientas.append(h.nombre)
            if h.terminal:
                _responder(mensajes, ll, {"recibido": True})
                trazador.registrar(**comunes, herramienta=h.nombre, args=args.model_dump())
                cierre = (h.nombre, args)
                continue
            try:
                salida = h.funcion(args)
                error = None
            except Exception as e:  # la herramienta falló: el modelo lo ve como observación
                salida = {"error": f"{type(e).__name__}: {e}"}
                error = salida["error"]
            _responder(mensajes, ll, salida)
            trazador.registrar(**comunes, herramienta=h.nombre, args=args.model_dump(),
                               resultado=salida, error=error)

        if cierre:
            resultado.terminal, resultado.args = cierre
            return resultado

    resultado.agotado = True
    trazador.registrar(agente=agente, paso=max_pasos, error=f"Tope de {max_pasos} pasos alcanzado")
    return resultado


def _responder(mensajes: list[dict], llamada, contenido: Any) -> None:
    mensajes.append({"role": "tool", "tool_call_id": llamada.id, "name": llamada.nombre, "content": contenido})
