"""Demo de consola de la rebanada vertical.

    python -m modulab.demo                 # tú escribes como dueño; modelo según .env
    python -m modulab.demo --guion         # respuestas del dueño automáticas (estética); modelo real
    python -m modulab.demo --simulado      # todo sin red: dueño y modelo con guion
    python -m modulab.demo --trazas        # muestra cada paso de la traza en consola
"""
from __future__ import annotations

import argparse
import sys

from . import config
from .guion_estetica import DUENO, MODELO_SIMULADO
from .llm import ClienteLLM, ProveedorSimulado
from .orchestrator import Orquestador


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Demo de consola de ModuLab")
    p.add_argument("--guion", action="store_true", help="usar las respuestas de la dueña de la estética")
    p.add_argument("--simulado", action="store_true", help="sin red: modelo y dueño con guion")
    p.add_argument("--trazas", action="store_true", help="mostrar la traza de cada paso")
    a = p.parse_args(argv)

    if a.simulado or config.MODELO == "simulado":
        cliente = ClienteLLM([ProveedorSimulado(MODELO_SIMULADO)], usar_cache=False)
        a.guion = True
    else:
        cliente = ClienteLLM.desde_config()
    orq = Orquestador(cliente, trazas_en_consola=a.trazas)

    print("ModuLab · asistente para armar tu plataforma web. Escribe 'salir' para terminar.\n")
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
        print(f"\nModuLab> {r.texto}\n")
        if r.tipo in ("propuesta", "error"):
            for nombre, ruta in r.archivos.items():
                print(f"  {nombre}: {ruta}")
            estado = orq.sesiones["demo"]
            print(f"\n  Traza: {estado.trazador.archivo}")
            print(f"  Preguntas: {r.preguntas_hechas} · llamadas reales al modelo: {cliente.llamadas_reales}")
            print("  (Emitir con folio se habilita el jue 26 con el token de confirmación.)")
            return 0 if r.tipo == "propuesta" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
