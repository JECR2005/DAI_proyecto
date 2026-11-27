"""Casos de desarrollo del analista: 6 conversaciones con guion fijo, una por giro más dos difíciles.

Sirven para corregir prompts antes de congelarlos; NO son los 40 casos de evaluación de Carlos.
Corren con el modelo real, la base en memoria y sin emitir nada (se detienen en la propuesta).

    python -m modulab.casos_dev                    # los 6 casos con el modelo de .env
    python -m modulab.casos_dev --modelo groq      # con Groq como principal
    python -m modulab.casos_dev --caso escuela     # solo uno

Cada caso revisa: propuesta entregada, máximo 6 preguntas, cada módulo con un doc_id que existe,
total dentro del presupuesto, módulos que deben y no deben salir, y lo fuera de catálogo cuando aplica.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

from . import config, db
from .confirmation import ProveedorConfirmacion
from .guion_estetica import DUENO
from .llm import ClienteLLM
from .orchestrator import Orquestador
from .tools import datos

RESPUESTA_GENERICA = "No estoy segura; lo que tú me recomiendes con ese presupuesto."

CASOS = [
    {"id": "estetica", "giro": "estética infantil", "dueno": DUENO,
     "debe": ["M04", "M05"], "no_debe": ["M10", "M11", "M12"], "fuera_catalogo": True},
    {"id": "veterinaria", "giro": "veterinaria o consultorio",
     "dueno": ["Tengo un consultorio veterinario; las consultas las agendo por teléfono y el historial de cada "
               "mascota lo llevo en tarjetas de papel. Mi presupuesto es de $9,000.",
               "Damos unas 10 consultas al día. Sí, me gustaría avisar a los dueños cuando toca la siguiente vacuna.",
               "No vendemos productos, solo consultas."],
     "debe": ["M04", "M05", "M06"], "no_debe": ["M10", "M11", "M12"], "fuera_catalogo": False},
    {"id": "escuela", "giro": "escuela o academia",
     "dueno": ["Tengo una academia de inglés con unos 80 alumnos. Las inscripciones son en papel y las "
               "colegiaturas las cobro en efectivo y las anoto en un cuaderno. Tengo $7,000.",
               "Las clases tienen horario fijo, no necesito agendar citas.",
               "No vendo libros ni productos."],
     "debe": ["M11", "M12"], "no_debe": ["M05", "M06", "M10"], "fuera_catalogo": False},
    {"id": "tienda", "giro": "ferretería o tienda",
     "dueno": ["Tengo una ferretería de barrio. El inventario lo llevo en Excel y muchos clientes me preguntan "
               "por WhatsApp si tengo algo. Quisiera que pudieran ver mis productos y pedir en línea. Tengo $9,000.",
               "Manejo como 600 productos. Los pedidos los recogen en la tienda o los entrego cerca.",
               "No doy citas ni reservaciones."],
     "debe": ["M07", "M08"], "no_debe": ["M04", "M10", "M11"], "fuera_catalogo": False},
    {"id": "comida", "giro": "restaurante o venta de comida",
     "dueno": ["Tengo una fonda; los pedidos para llevar llegan por WhatsApp y los fines de semana la gente "
               "quiere reservar mesa. Mi presupuesto es de $6,000.",
               "Lo que más me urge son las reservas del fin de semana; los pedidos los puedo seguir por WhatsApp.",
               "También quisiera una app para repartidores, como las de las plataformas."],
     "debe": ["M10"], "no_debe": ["M04", "M11", "M12"], "fuera_catalogo": True},
    {"id": "presupuesto_bajo", "giro": "estética infantil",
     "dueno": ["Tengo una estética infantil pequeña, solo yo atiendo. Agendo por WhatsApp. Solo tengo $4,000.",
               "Me gustaría que los papás agendaran solos, pero no me alcanza para mucho.",
               "Entiendo, ¿qué me conviene con ese dinero?"],
     "debe": [], "no_debe": ["M10", "M11", "M12"], "fuera_catalogo": False},
]


def _doc_ids_validos() -> set[str]:
    ids = {m["doc_id"] for m in datos.modulos().values()}
    ids |= {p.stem for p in config.CORPUS_DIR.glob("*.md")}
    return ids


def correr(caso: dict, cliente: ClienteLLM) -> dict:
    """Conversa con el orquestador usando el guion del caso y revisa la propuesta resultante."""
    db.usar(db.RepositorioMemoria())  # nada de estos casos llega a SQL Server
    orq = Orquestador(cliente, ProveedorConfirmacion("ui"))
    sesion = f"dev_{caso['id']}"
    respuestas = iter(caso["dueno"])
    texto, r, inicio = next(respuestas), None, time.perf_counter()
    for _ in range(config.MAX_PREGUNTAS + 2):
        r = orq.responder(sesion, texto)
        if r.tipo != "pregunta":
            break
        texto = next(respuestas, RESPUESTA_GENERICA)
    estado = orq.sesiones[sesion]
    fallas: list[str] = []
    if r is None or r.propuesta is None or r.cotizacion is None:
        fallas.append(f"no entregó propuesta (terminó en '{r.tipo if r else '-'}': {(r.texto if r else '')[:120]})")
    else:
        p, c = r.propuesta, r.cotizacion
        en_cotizacion = {l.id for l in c.lineas}
        validos = _doc_ids_validos()
        for m in p.modulos:
            if m.doc_id not in validos:
                fallas.append(f"{m.id} cita un doc_id que no existe: {m.doc_id!r}")
        if p.presupuesto and c.total > p.presupuesto:
            fallas.append(f"total ${c.total:,.0f} excede el presupuesto ${p.presupuesto:,.0f}")
        faltan = [m for m in caso["debe"] if m not in en_cotizacion]
        if faltan:
            fallas.append("faltan módulos esperados: " + ", ".join(faltan))
        sobran = sorted(en_cotizacion & set(caso["no_debe"]))
        if sobran:
            fallas.append("incluyó módulos de otro giro: " + ", ".join(sobran))
        if caso["fuera_catalogo"] and not p.fuera_catalogo:
            fallas.append("no registró lo que está fuera de catálogo")
        if r.tipo == "emitida" or estado.folio:
            fallas.append("emitió una cotización sin el botón Confirmar")
    if estado.preguntas > config.MAX_PREGUNTAS:
        fallas.append(f"hizo {estado.preguntas} preguntas (máximo {config.MAX_PREGUNTAS})")
    registros = estado.trazador.registros
    return {
        "caso": caso["id"], "ok": not fallas, "fallas": fallas,
        "preguntas": estado.preguntas,
        "modulos": sorted(l.id for l in r.cotizacion.lineas) if r and r.cotizacion else [],
        "total": r.cotizacion.total if r and r.cotizacion else None,
        "correcciones_validador": sum(t.agente == "validador" for t in registros),
        "respaldos": sum(bool(t.error and "respaldo" in t.error) for t in registros),
        "segundos": round(time.perf_counter() - inicio, 1),
        "traza": estado.trazador.ejecucion_id,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Casos de desarrollo del analista (6 con guion fijo)")
    p.add_argument("--modelo", choices=["gemini", "groq"], help="modelo principal (sin tocar .env)")
    p.add_argument("--caso", choices=[c["id"] for c in CASOS], help="correr solo un caso")
    a = p.parse_args(argv)
    if a.modelo:
        config.MODELO = a.modelo
    cliente = ClienteLLM.desde_config()
    casos = [c for c in CASOS if not a.caso or c["id"] == a.caso]

    print(f"Casos de desarrollo · modelo: {config.MODELO} · base en memoria, sin emitir\n")
    resultados = []
    for caso in casos:
        print(f"- {caso['id']} ...", end=" ", flush=True)
        try:
            res = correr(caso, cliente)
        except Exception as e:  # un caso roto no detiene a los demás
            res = {"caso": caso["id"], "ok": False, "fallas": [f"excepción: {e}"]}
        resultados.append(res)
        print("OK" if res["ok"] else "FALLA", f"({res.get('segundos', '-')} s, {res.get('preguntas', '-')} preguntas, "
              f"total {res.get('total')}, módulos {res.get('modulos')}, traza {res.get('traza')})")
        for f in res["fallas"]:
            print(f"    · {f}")

    carpeta = config.OUTPUTS_DIR / "casos_dev"
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"{datetime.now():%Y%m%d_%H%M}_{config.MODELO}.json"
    archivo.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    aprobados = sum(r["ok"] for r in resultados)
    print(f"\n{aprobados}/{len(resultados)} casos pasan · resultados en {archivo}")
    return 0 if aprobados == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
