"""Guardrails: deciden si un mensaje del dueño se atiende, ANTES de llamar al modelo.

Son una capa más, no la única: aunque algo pase este filtro, los precios salen
solo del CSV, el validador revisa todo y las acciones irreversibles exigen token.
(Diferencia con el validador: el guardrail decide si se atiende la petición;
el validador revisa que el resultado del agente sea correcto.)
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

MENSAJES = {
    "inyeccion": "Solo puedo ayudarte a elegir y cotizar los módulos de la plataforma web de tu negocio. "
                 "Cuéntame cómo trabaja tu negocio y con gusto te ayudo.",
    "precios": "Los precios son los de la lista oficial del desarrollador y no puedo cambiarlos ni aplicar "
               "descuentos. Si el presupuesto no alcanza, puedo priorizar los módulos que más necesitas.",
    "memoria": "Solo guardo los datos de tu negocio (giro, presupuesto y módulos), no instrucciones para "
               "otras sesiones. ¿Seguimos con tu plataforma?",
    "proposito": "Eso queda fuera de lo que hago: solo ayudo a elegir y cotizar los módulos de la plataforma "
                 "web de tu negocio. ¿Te ayudo con eso?",
}

_PATRONES = {
    "inyeccion": [
        r"\bignora\w*\b.{0,40}\b(instrucciones|reglas|indicaciones|prompt)",
        r"\bolvida\w*\b.{0,40}\b(instrucciones|reglas|indicaciones)",
        r"\b(muestra|dime|revela|ensena|imprime|repite)\w*\b.{0,30}\b(tu|tus|el)\b.{0,15}\b(prompt|instrucciones|reglas)",
        r"\bsystem prompt\b", r"\bprompt del sistema\b",
        r"\b(actua|comportate|finge)\b.{0,20}\bcomo\b", r"\b(ahora|desde ahora|a partir de ahora) (eres|seras)\b",
        r"\bmodo (desarrollador|dios|admin\w*)\b", r"\bjailbreak\b", r"\bDAN\b",
        r"\bignore (all |the )?(previous|prior|above) (instructions|rules)\b", r"\breveal (your )?(system )?prompt\b",
        r"</?\s*(mensaje_del_dueno|perfil_guardado|system)\s*>",
    ],
    "precios": [
        r"\b(aplica|aplicame|hazme|dame|ponme)\b.{0,25}\b(descuento|rebaja|precio especial)",
        r"\b\d{1,3}\s*%\s*(de\s+)?(descuento|rebaja|menos)",
        r"\b(cuesta|vale|precio es|cobra)\w*\b.{0,30}(\$\s*0\b|cero pesos|gratis|nada)",
        r"\b(todo|todos los modulos|el sitio|la plataforma)\b.{0,20}\bgratis\b",
        r"\bcambia\w*\b.{0,20}\bprecio",
    ],
    # "Guarda mis datos para la próxima vez" es válido; lo que se rechaza es guardar una INSTRUCCIÓN.
    "memoria": [
        r"\b(futur|proxim|siguiente|otra)\w*\s+(sesion|vez|veces|conversaci)\w*\b.{0,60}"
        r"\b(gratis|descuento|ignora|sin costo|regla|instruccion|obedece)",
        r"\b(guarda|recuerda|memoriza|anota)\w*\b.{0,40}\b(gratis|descuento|ignora|sin costo|regla|instruccion)",
        r"\bde ahora en adelante\b.{0,40}\b(gratis|descuento|ignora|sin costo)",
    ],
    "proposito": [
        r"\b(escribe|escribeme|redacta|hazme)\b.{0,25}\b(ensayo|poema|cuento|cancion|tarea|resumen de un libro)",
        r"\b(consejo|diagnostico|receta)\w*\s+medic\w*", r"\bque medicamento\b",
        r"\b(resuelve|resuelveme)\b.{0,20}\b(ecuacion|examen|ejercicio)",
        r"\b(hackea\w*|contrasena de|robar)\b",
    ],
}
_COMPILADOS = {cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in _PATRONES.items()}


def _normalizar(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


@dataclass
class Veredicto:
    categoria: str
    mensaje: str
    patron: str


def revisar(texto: str) -> Optional[Veredicto]:
    """None si el mensaje se puede atender; Veredicto con la respuesta fija si no."""
    normal = _normalizar(texto)
    for categoria in ("inyeccion", "memoria", "precios", "proposito"):
        for patron in _COMPILADOS[categoria]:
            if patron.search(normal):
                return Veredicto(categoria, MENSAJES[categoria], patron.pattern)
    return None


def delimitar(texto: str) -> str:
    """El texto del dueño entra al modelo como datos, delimitado y sin etiquetas falsas."""
    limpio = re.sub(r"</?\s*(mensaje_del_dueno|perfil_guardado)\s*>", "", texto, flags=re.IGNORECASE)
    return f"<mensaje_del_dueno>\n{limpio}\n</mensaje_del_dueno>"
