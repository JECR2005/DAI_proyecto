"""Cliente único para los modelos de lenguaje.

`ClienteLLM.chat(...)` es la única puerta al modelo en todo el proyecto:
- Gemini como principal y Groq como alterno (o al revés, según MODELO).
- Reintentos ante 429/500/503 y cambio automático al otro proveedor.
- Caché en disco: la misma petición no gasta cuota dos veces.
- Registra tokens, latencia y modelo de cada respuesta.
- Proveedor "simulado": reproduce un guion sin red (pruebas y depuración).

Formato interno de mensajes (neutral, independiente del proveedor):
    {"role": "user", "content": "..."}
    {"role": "assistant", "content": "..." | None, "tool_calls": [{"id", "name", "args"}]}
    {"role": "tool", "tool_call_id": "...", "name": "...", "content": <dict>}
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from . import config


# --------------------------------------------------------------------------
# Tipos
# --------------------------------------------------------------------------
@dataclass
class LlamadaHerramienta:
    id: str
    nombre: str
    args: dict[str, Any]


@dataclass
class RespuestaLLM:
    texto: Optional[str]
    llamadas: list[LlamadaHerramienta] = field(default_factory=list)
    tokens_entrada: int = 0
    tokens_salida: int = 0
    latencia_ms: int = 0
    modelo: str = ""
    desde_cache: bool = False
    crudo: Any = None  # partes originales del proveedor (Gemini las necesita para reenviar llamadas)

    def a_dict(self) -> dict:
        return {
            "texto": self.texto,
            "llamadas": [vars(l) for l in self.llamadas],
            "tokens_entrada": self.tokens_entrada,
            "tokens_salida": self.tokens_salida,
            "modelo": self.modelo,
        }

    @staticmethod
    def de_dict(d: dict) -> "RespuestaLLM":
        return RespuestaLLM(
            texto=d.get("texto"),
            llamadas=[LlamadaHerramienta(**l) for l in d.get("llamadas", [])],
            tokens_entrada=d.get("tokens_entrada", 0),
            tokens_salida=d.get("tokens_salida", 0),
            modelo=d.get("modelo", ""),
            desde_cache=True,
        )


class ErrorLLM(Exception):
    """Error de un proveedor. `reintentable` indica si vale la pena reintentar o cambiar."""

    def __init__(self, mensaje: str, reintentable: bool = False, codigo: Optional[int] = None):
        super().__init__(mensaje)
        self.reintentable = reintentable
        self.codigo = codigo


def _codigo_http(e: Exception) -> Optional[int]:
    for atributo in ("code", "status_code", "status"):
        valor = getattr(e, atributo, None)
        if isinstance(valor, int):
            return valor
    respuesta = getattr(e, "response", None)
    valor = getattr(respuesta, "status_code", None)
    return valor if isinstance(valor, int) else None


def _envolver(e: Exception, proveedor: str) -> ErrorLLM:
    codigo = _codigo_http(e)
    reintentable = codigo in (408, 429, 500, 502, 503, 504) or "timeout" in type(e).__name__.lower()
    return ErrorLLM(f"{proveedor}: {type(e).__name__}: {e}", reintentable=reintentable, codigo=codigo)


# --------------------------------------------------------------------------
# Esquemas de herramientas
# --------------------------------------------------------------------------
def _esquema_gemini(esquema: dict) -> dict:
    """Convierte JSON Schema al subconjunto que acepta Gemini (tipos en mayúsculas)."""
    if not isinstance(esquema, dict):
        return esquema
    salida: dict[str, Any] = {}
    for clave, valor in esquema.items():
        if clave in ("title", "default", "additionalProperties", "$schema"):
            continue
        if clave == "type":
            if isinstance(valor, list):  # ["string", "null"]
                tipos = [t for t in valor if t != "null"]
                salida["type"] = tipos[0].upper() if tipos else "STRING"
                if "null" in valor:
                    salida["nullable"] = True
            else:
                salida["type"] = valor.upper()
        elif clave == "properties":
            salida["properties"] = {k: _esquema_gemini(v) for k, v in valor.items()}
        elif clave == "items":
            salida["items"] = _esquema_gemini(valor)
        else:
            salida[clave] = valor
    return salida


# --------------------------------------------------------------------------
# Proveedores
# --------------------------------------------------------------------------
class ProveedorGemini:
    nombre = "gemini"

    def __init__(self, modelo: str = config.GEMINI_MODEL, api_key: str = config.GEMINI_API_KEY):
        if not api_key:
            raise ErrorLLM("Falta GEMINI_API_KEY en .env", reintentable=True)
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:  # pragma: no cover
            raise ErrorLLM("Instala google-genai (pip install google-genai)", reintentable=True) from e
        self._types = types
        self._cliente = genai.Client(api_key=api_key)
        self.modelo = modelo

    def _contenidos(self, mensajes: list[dict]):
        t = self._types
        contenidos: list = []
        for m in mensajes:
            if m["role"] == "assistant":
                if m.get("crudo_gemini"):
                    partes = m["crudo_gemini"]
                else:
                    partes = []
                    if m.get("content"):
                        partes.append(t.Part.from_text(text=m["content"]))
                    for j, ll in enumerate(m.get("tool_calls", [])):
                        parte = t.Part(function_call=t.FunctionCall(name=ll["name"], args=ll["args"]))
                        if j == 0:
                            # Gemini 3 exige la firma de pensamiento en la primera llamada de cada paso.
                            # Si no tenemos la original (respuesta del caché o de Groq), se usa la firma
                            # de omisión que documenta Google para historiales reconstruidos.
                            parte.thought_signature = b"skip_thought_signature_validator"
                        partes.append(parte)
                contenidos.append(t.Content(role="model", parts=partes))
                continue
            if m["role"] == "tool":
                parte = t.Part.from_function_response(name=m["name"], response={"resultado": m["content"]})
            else:
                parte = t.Part.from_text(text=m["content"])
            # Gemini prefiere un solo bloque "user" seguido: se agrupan respuestas y texto.
            if contenidos and contenidos[-1].role == "user":
                contenidos[-1].parts.append(parte)
            else:
                contenidos.append(t.Content(role="user", parts=[parte]))
        return contenidos

    def chat(self, system: str, mensajes: list[dict], herramientas: list[dict]) -> RespuestaLLM:
        t = self._types
        declaraciones = [
            t.FunctionDeclaration(name=h["nombre"], description=h["descripcion"],
                                  parameters=_esquema_gemini(h["parametros"]))
            for h in herramientas
        ]
        ajustes = t.GenerateContentConfig(
            system_instruction=system,
            temperature=config.TEMPERATURA,
            tools=[t.Tool(function_declarations=declaraciones)] if declaraciones else None,
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
        )
        inicio = time.perf_counter()
        try:
            r = self._cliente.models.generate_content(
                model=self.modelo, contents=self._contenidos(mensajes), config=ajustes)
        except Exception as e:
            raise _envolver(e, self.nombre) from e
        latencia = int((time.perf_counter() - inicio) * 1000)
        partes = (r.candidates[0].content.parts or []) if r.candidates and r.candidates[0].content else []
        textos, llamadas = [], []
        for i, p in enumerate(partes):
            if getattr(p, "function_call", None):
                fc = p.function_call
                llamadas.append(LlamadaHerramienta(id=fc.id or f"g{uuid.uuid4().hex[:10]}", nombre=fc.name,
                                                   args=dict(fc.args or {})))
            elif getattr(p, "text", None) and not getattr(p, "thought", False):
                textos.append(p.text)
        uso = r.usage_metadata
        return RespuestaLLM(
            texto="\n".join(textos) or None, llamadas=llamadas,
            tokens_entrada=getattr(uso, "prompt_token_count", 0) or 0,
            tokens_salida=getattr(uso, "candidates_token_count", 0) or 0,
            latencia_ms=latencia, modelo=f"gemini:{self.modelo}", crudo=partes)


class ProveedorGroq:
    nombre = "groq"

    def __init__(self, modelo: str = config.GROQ_MODEL, api_key: str = config.GROQ_API_KEY):
        if not api_key:
            raise ErrorLLM("Falta GROQ_API_KEY en .env", reintentable=True)
        try:
            from groq import Groq
        except ImportError as e:  # pragma: no cover
            raise ErrorLLM("Instala groq (pip install groq)", reintentable=True) from e
        self._cliente = Groq(api_key=api_key)
        self.modelo = modelo

    @staticmethod
    def _mensajes(system: str, mensajes: list[dict]) -> list[dict]:
        salida = [{"role": "system", "content": system}]
        for m in mensajes:
            if m["role"] == "assistant":
                item: dict[str, Any] = {"role": "assistant", "content": m.get("content") or ""}
                if m.get("tool_calls"):
                    item["tool_calls"] = [
                        {"id": ll["id"], "type": "function",
                         "function": {"name": ll["name"], "arguments": json.dumps(ll["args"], ensure_ascii=False)}}
                        for ll in m["tool_calls"]]
                salida.append(item)
            elif m["role"] == "tool":
                salida.append({"role": "tool", "tool_call_id": m["tool_call_id"],
                               "content": json.dumps(m["content"], ensure_ascii=False, default=str)})
            else:
                salida.append({"role": "user", "content": m["content"]})
        return salida

    def chat(self, system: str, mensajes: list[dict], herramientas: list[dict]) -> RespuestaLLM:
        tools = [{"type": "function", "function": {"name": h["nombre"], "description": h["descripcion"],
                                                   "parameters": h["parametros"]}} for h in herramientas]
        inicio = time.perf_counter()
        try:
            r = self._cliente.chat.completions.create(
                model=self.modelo, messages=self._mensajes(system, mensajes),
                tools=tools or None, temperature=config.TEMPERATURA)
        except Exception as e:
            raise _envolver(e, self.nombre) from e
        latencia = int((time.perf_counter() - inicio) * 1000)
        msg = r.choices[0].message
        llamadas = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_argumentos_invalidos": tc.function.arguments}
            llamadas.append(LlamadaHerramienta(id=tc.id, nombre=tc.function.name, args=args))
        return RespuestaLLM(
            texto=msg.content or None, llamadas=llamadas,
            tokens_entrada=getattr(r.usage, "prompt_tokens", 0) or 0,
            tokens_salida=getattr(r.usage, "completion_tokens", 0) or 0,
            latencia_ms=latencia, modelo=f"groq:{self.modelo}")


class ProveedorSimulado:
    """Reproduce respuestas escritas a mano, por agente. Sin red y sin cuota.

    guion = {"analista": [{"texto": ..., "llamadas": [{"nombre": ..., "args": {...}}]}, ...], ...}
    """
    nombre = "simulado"

    def __init__(self, guion: dict[str, list[dict]]):
        self._guion = {agente: list(pasos) for agente, pasos in guion.items()}
        self._contador = 0
        self.agente_actual = "analista"

    def chat(self, system: str, mensajes: list[dict], herramientas: list[dict]) -> RespuestaLLM:
        pasos = self._guion.get(self.agente_actual) or []
        if not pasos:
            raise ErrorLLM(f"simulado: el guion de '{self.agente_actual}' se terminó")
        paso = pasos.pop(0)
        llamadas = []
        for ll in paso.get("llamadas", []):
            self._contador += 1
            llamadas.append(LlamadaHerramienta(id=f"sim{self._contador}", nombre=ll["nombre"],
                                               args=copy.deepcopy(ll["args"])))
        return RespuestaLLM(texto=paso.get("texto"), llamadas=llamadas, modelo="simulado")


# --------------------------------------------------------------------------
# Cliente con cadena de respaldo y caché
# --------------------------------------------------------------------------
class ClienteLLM:
    def __init__(self, proveedores: Optional[list] = None, usar_cache: bool = config.USAR_CACHE):
        self._fabricas = proveedores
        self._instancias: dict[int, Any] = {}
        self.usar_cache = usar_cache
        self.llamadas_reales = 0

    @staticmethod
    def desde_config() -> "ClienteLLM":
        if config.MODELO == "simulado":
            raise ValueError("Para el modo simulado crea ClienteLLM([ProveedorSimulado(guion)])")
        orden = [ProveedorGemini, ProveedorGroq] if config.MODELO != "groq" else [ProveedorGroq, ProveedorGemini]
        return ClienteLLM(orden)

    def _proveedor(self, i: int):
        if i not in self._instancias:
            fabrica = self._fabricas[i]
            self._instancias[i] = fabrica() if isinstance(fabrica, type) else fabrica
        return self._instancias[i]

    @staticmethod
    def _clave(system: str, mensajes: list[dict], herramientas: list[dict]) -> str:
        limpios = [{k: v for k, v in m.items() if not k.startswith("crudo")} for m in mensajes]
        datos = json.dumps([system, limpios, herramientas], sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(datos.encode("utf-8")).hexdigest()

    def chat(self, system: str, mensajes: list[dict], herramientas: list[dict],
             agente: str = "agente") -> RespuestaLLM:
        errores: list[str] = []
        for i in range(len(self._fabricas)):
            try:
                proveedor = self._proveedor(i)
            except ErrorLLM as e:
                errores.append(str(e))
                continue
            if isinstance(proveedor, ProveedorSimulado):
                proveedor.agente_actual = agente
                return proveedor.chat(system, mensajes, herramientas)

            clave = self._clave(f"{proveedor.nombre}:{proveedor.modelo}\n{system}", mensajes, herramientas)
            archivo = config.CACHE_DIR / f"{clave}.json"
            if self.usar_cache and archivo.exists():
                return RespuestaLLM.de_dict(json.loads(archivo.read_text(encoding="utf-8")))

            for intento in range(config.REINTENTOS_POR_PROVEEDOR):
                try:
                    r = proveedor.chat(system, mensajes, herramientas)
                    self.llamadas_reales += 1
                    if self.usar_cache:
                        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        archivo.write_text(json.dumps(r.a_dict(), ensure_ascii=False), encoding="utf-8")
                    return r
                except ErrorLLM as e:
                    errores.append(str(e))
                    if not e.reintentable:
                        break  # reintentar no sirve (modelo inexistente, llave inválida): pasa al siguiente
                    time.sleep(1.5 * (intento + 1))
            # se agotaron los reintentos o el error no es reintentable: pasa al siguiente proveedor
        raise ErrorLLM("Ningún proveedor respondió: " + " | ".join(errores), reintentable=False)
