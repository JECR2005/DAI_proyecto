"""Demo de consola de la rebanada vertical (caso estética infantil).

    python -m modulab.demo                 # tú escribes como dueño; modelo y base según .env
    python -m modulab.demo --guion         # respuestas de la dueña automáticas; modelo y base reales
    python -m modulab.demo --simulado      # todo sin red ni base de datos: modelo y dueña con guion
    python -m modulab.demo --memoria       # usa la base en memoria en lugar de SQL Server
    python -m modulab.demo --trazas        # muestra cada paso de la traza
    python -m modulab.demo --modelo groq   # usa Groq como principal (Gemini queda de respaldo)

Para regresar como cliente, escribe tu código NEG-XXXXX en el chat.
"""
from __future__ import annotations

import argparse
import sys

from . import config, db
from .confirmation import ProveedorConfirmacion
from .guion_estetica import CONFIRMACION_FALSA, DUENO, MODELO_SIMULADO
from .llm import ClienteLLM, ProveedorSimulado
from .orchestrator import Orquestador


def _mostrar(r) -> None:
    print(f"\nModuLab> {r.texto}\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Demo de consola de ModuLab")
    p.add_argument("--guion", action="store_true", help="usar las respuestas de la dueña de la estética")
    p.add_argument("--simulado", action="store_true", help="sin red ni base de datos")
    p.add_argument("--memoria", action="store_true", help="base de datos en memoria")
    p.add_argument("--trazas", action="store_true", help="mostrar la traza de cada paso")
    p.add_argument("--modelo", choices=["gemini", "groq"], help="modelo principal (sin tocar .env)")
    a = p.parse_args(argv)
    if a.modelo:
        config.MODELO = a.modelo

    if a.simulado or config.MODELO == "simulado":
        cliente = ClienteLLM([ProveedorSimulado(MODELO_SIMULADO)], usar_cache=False)
        a.guion, a.memoria = True, True
    else:
        cliente = ClienteLLM.desde_config()
    if a.memoria:
        db.usar(db.RepositorioMemoria())
    orq = Orquestador(cliente, ProveedorConfirmacion("ui"), trazas_en_consola=a.trazas)
    print(f"ModuLab · asistente para armar tu plataforma web (base: {'memoria' if a.memoria else 'SQL Server'}). "
          "Escribe 'salir' para terminar.\n")

    respuestas = iter(DUENO) if a.guion else None
    while True:
        if respuestas is not None:
            texto = next(respuestas, None)
            if texto is None:
                break
            print(f"Dueña> {texto}")
        else:
            try:
                texto = input("Tú> ").strip()
            except EOFError:
                break
            if texto.lower() in ("salir", "exit"):
                break
            if not texto:
                continue
        r = orq.responder("demo", texto)
        _mostrar(r)

        if r.requiere_confirmacion and a.guion:
            # Demostración: escribir "confirmo" en el chat NO emite nada.
            print(f"Dueña> {CONFIRMACION_FALSA}")
            _mostrar(orq.responder("demo", CONFIRMACION_FALSA))
        while r.requiere_confirmacion:
            if a.guion:
                print("[La dueña presiona el botón Confirmar]")
                aprobado = True
            else:
                aprobado = input("¿Confirmar? [s/n] ").strip().lower().startswith("s")
            r = orq.confirmar("demo", aprobado)
            _mostrar(r)

        if r.tipo in ("emitida", "error") or (r.tipo == "propuesta" and not r.requiere_confirmacion and r.cotizacion):
            for nombre, ruta in r.archivos.items():
                print(f"  {nombre}: {ruta}")
            estado = orq.sesiones["demo"]
            print(f"\n  Traza: {estado.trazador.archivo}")
            print(f"  Preguntas: {r.preguntas_hechas} · llamadas reales al modelo: {cliente.llamadas_reales}")
            if r.folio:
                print(f"  Folio: {r.folio} · vigente hasta {r.vigencia} · código de negocio: {r.codigo_negocio}")
            return 0 if r.tipo != "error" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
