"""buscar_catalogo, consultar_precios y resolver_dependencias.

- resolver_dependencias: REAL (Jesús).
- consultar_precios: real, lee el CSV (Gustavo puede reemplazarla).
- buscar_catalogo: PROVISIONAL, búsqueda por palabras sobre catalogo.json
  y data/corpus/*.md. Gustavo la reemplaza por ChromaDB manteniendo la
  misma firma y el mismo formato de salida (doc_id obligatorio).
"""
from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

from .. import config
from . import datos

# ---------------------------------------------------------------- buscar_catalogo
_VACIAS = set("""a al algo como con de del el en es la las lo los me mi mis mucho muy no o para pero por
que se si sin su sus te tengo tiene un una uno y ya yo tambien hay hacer quiero""".split())


def _palabras(texto: str) -> set[str]:
    sin_acentos = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return {p for p in re.findall(r"[a-z0-9]+", sin_acentos) if len(p) > 2 and p not in _VACIAS}


def _documentos() -> list[dict]:
    docs = []
    for m in datos.catalogo()["modulos"]:
        texto = " ".join([m["nombre"], m["descripcion"], " ".join(m["ejemplos"]), " ".join(m["giros"])])
        docs.append({"doc_id": m["doc_id"], "modulo": m["id"], "tipo": "ficha", "texto": texto,
                     "fragmento": f"{m['nombre']}: {m['descripcion']}"})
    if config.CORPUS_DIR.exists():
        for archivo in sorted(config.CORPUS_DIR.glob("*.md")):
            contenido = archivo.read_text(encoding="utf-8")
            modulos = re.findall(r"\bM\d{2}\b", contenido.split("\n", 3)[0] if contenido else "")
            docs.append({"doc_id": archivo.stem, "modulo": ",".join(modulos) or None, "tipo": "corpus",
                         "texto": contenido, "fragmento": contenido[:300]})
    return docs


class ArgsBuscarCatalogo(BaseModel):
    consulta: str = Field(description="Giro o necesidad del negocio en palabras simples")
    k: int = Field(default=5, description="Número máximo de resultados")


def buscar_catalogo(args: ArgsBuscarCatalogo) -> dict:
    consulta = _palabras(args.consulta)
    # Si el modelo pide módulos por id ("M07"), su ficha va primero (caso fonda del 26-nov).
    pedidos = re.findall(r"\bM\d{2}\b", args.consulta.upper())
    # Coincidir en una sola palabra de una consulta larga es ruido ("clientes" aparece en todo).
    minimo = 2 if len(consulta) >= 3 else 1
    puntuados = []
    for doc in _documentos():
        if doc["tipo"] == "ficha" and doc["modulo"] in pedidos:
            puntuados.append((100 - pedidos.index(doc["modulo"]), doc))
            continue
        puntos = len(consulta & _palabras(doc["texto"]))
        if puntos >= minimo:
            puntuados.append((puntos, doc))
    puntuados.sort(key=lambda x: -x[0])
    resultados = [{"doc_id": d["doc_id"], "modulo": d["modulo"], "fragmento": d["fragmento"],
                   "relevancia": p} for p, d in puntuados[: args.k]]
    return {"resultados": resultados,
            "nota": "Recomienda solo módulos que aparezcan aquí y cita su doc_id."
            if resultados else "Sin resultados: no inventes módulos; si la necesidad no existe, regístrala como solicitud especial."}


# ---------------------------------------------------------------- consultar_precios
class ArgsConsultarPrecios(BaseModel):
    modulos: list[str] = Field(description="Ids de módulos, por ejemplo ['M04', 'M05']")


def consultar_precios(args: ArgsConsultarPrecios) -> dict:
    lista = datos.precios()
    encontrados = {i: lista[i] for i in args.modulos if i in lista}
    no_existen = [i for i in args.modulos if i not in lista]
    return {"precios_mxn": encontrados, "no_existen": no_existen,
            "nota": "Los precios solo salen de esta lista; no los cambies ni apliques descuentos."}


# ---------------------------------------------------------------- resolver_dependencias
class ArgsResolverDependencias(BaseModel):
    modulos: list[str] = Field(description="Ids de los módulos que quieres recomendar")


def cerrar_dependencias(ids: list[str]) -> tuple[list[str], list[dict], list[str]]:
    """Devuelve (módulos con dependencias en cadena, agregados con su motivo, ids inexistentes)."""
    catalogo = datos.modulos()
    no_existen = [i for i in ids if i not in catalogo]
    finales: list[str] = []
    agregados: list[dict] = []

    def visitar(mid: str, pedido_por: str | None) -> None:
        if mid in finales:
            return
        for requisito in catalogo[mid]["requiere"]:
            visitar(requisito, mid)
        finales.append(mid)
        if pedido_por is not None and mid not in ids:
            agregados.append({"id": mid, "nombre": catalogo[mid]["nombre"], "requerido_por": pedido_por})

    for mid in ids:
        if mid in catalogo:
            visitar(mid, None)
    return finales, agregados, no_existen


def resolver_dependencias(args: ArgsResolverDependencias) -> dict:
    finales, agregados, no_existen = cerrar_dependencias(args.modulos)
    catalogo = datos.modulos()
    return {
        "modulos_adicionales": [m for m in finales if catalogo[m]["tipo"] != "base"],
        "base_incluidos": config.MODULOS_BASE,
        "agregados_por_dependencia": [a for a in agregados if catalogo[a["id"]]["tipo"] != "base"],
        "no_existen": no_existen,
    }
