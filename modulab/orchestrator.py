"""Orquestador (patrón orquestador–trabajadores).

Recibe cada mensaje del dueño, se lo pasa al Analista de giro y decide:
- si el analista preguntó, devuelve la pregunta (máximo 6 por conversación);
- si entregó la propuesta, la valida, llama al Cotizador/Configurador,
  valida la cotización y devuelve el resumen con los archivos generados.
Si el validador rechaza algo, el trabajador que falló reintenta (máx. 2).

`Orquestador.responder(sesion, texto)` es la interfaz que usa app.py (Gustavo)
y la demo de consola.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import config, validator
from .agents import analista, cotizador
from .llm import ClienteLLM
from .schemas import Cotizacion, Propuesta, Respuesta
from .tools import datos
from .tracing import Trazador


@dataclass
class EstadoSesion:
    sesion: str
    carpeta: Path
    trazador: Trazador
    mensajes_analista: list[dict] = field(default_factory=list)
    preguntas: int = 0
    propuesta: Optional[Propuesta] = None
    cotizacion: Optional[Cotizacion] = None
    archivos: dict[str, str] = field(default_factory=dict)


class Orquestador:
    def __init__(self, cliente: ClienteLLM, trazas_en_consola: bool = False):
        self.cliente = cliente
        self.trazas_en_consola = trazas_en_consola
        self.sesiones: dict[str, EstadoSesion] = {}

    def _estado(self, sesion: str) -> EstadoSesion:
        if sesion not in self.sesiones:
            trazador = Trazador(en_consola=self.trazas_en_consola)
            carpeta = config.OUTPUTS_DIR / f"{sesion}_{trazador.ejecucion_id}"
            self.sesiones[sesion] = EstadoSesion(sesion, carpeta, trazador)
        return self.sesiones[sesion]

    def responder(self, sesion: str, texto: str) -> Respuesta:
        estado = self._estado(sesion)
        marca = datos.carpeta_sesion.set(estado.carpeta)
        try:
            return self._responder(estado, texto)
        finally:
            datos.carpeta_sesion.reset(marca)

    # ------------------------------------------------------------------ flujo
    def _responder(self, estado: EstadoSesion, texto: str) -> Respuesta:
        if estado.cotizacion is not None:
            return Respuesta(tipo="propuesta", texto="Tu propuesta ya está lista. Para otra propuesta inicia una sesión nueva.",
                             propuesta=estado.propuesta, cotizacion=estado.cotizacion, archivos=estado.archivos,
                             preguntas_hechas=estado.preguntas)

        estado.mensajes_analista.append(
            {"role": "user", "content": f"<mensaje_del_dueno>\n{texto}\n</mensaje_del_dueno>"})

        propuesta = None
        for intento in range(config.MAX_REINTENTOS_VALIDADOR + 1):
            puede_preguntar = estado.preguntas < config.MAX_PREGUNTAS
            if not puede_preguntar:
                estado.mensajes_analista.append({"role": "user", "content":
                    "[orquestador] Ya hiciste el máximo de preguntas. Entrega la propuesta con lo que sabes."})
            r = analista.ejecutar(estado.mensajes_analista, self.cliente, estado.trazador, puede_preguntar)

            if r.error:
                return self._error(estado, f"No pude consultar el modelo: {r.error}")
            if r.agotado:
                return self._error(estado, "El analista llegó al tope de pasos sin terminar.")
            if r.terminal == "preguntar_al_dueno":
                estado.preguntas += 1
                return Respuesta(tipo="pregunta", texto=r.args.pregunta, preguntas_hechas=estado.preguntas)
            if r.terminal is None:  # respondió con texto: aclaración, rechazo o pregunta sin herramienta
                estado.preguntas += 1
                return Respuesta(tipo="pregunta", texto=r.texto or "", preguntas_hechas=estado.preguntas)

            propuesta = r.args
            errores = validator.validar_propuesta(propuesta)
            if not errores:
                break
            estado.trazador.registrar(agente="validador", paso=intento + 1, error="; ".join(errores))
            if intento == config.MAX_REINTENTOS_VALIDADOR:
                return self._error(estado, "La propuesta no pasó la validación: " + "; ".join(errores))
            estado.mensajes_analista.append({"role": "user", "content":
                "[validador] Tu propuesta tiene errores, corrígela y vuelve a entregarla: " + "; ".join(errores)})

        estado.propuesta = propuesta
        return self._cotizar(estado, propuesta)

    def _cotizar(self, estado: EstadoSesion, propuesta: Propuesta) -> Respuesta:
        correcciones = None
        for intento in range(config.MAX_REINTENTOS_VALIDADOR + 1):
            r = cotizador.ejecutar(propuesta, self.cliente, estado.trazador, correcciones)
            if r.error or r.agotado or r.terminal != "entregar_cotizacion":
                motivo = r.error or "el cotizador no entregó la cotización"
                return self._error(estado, f"No pude preparar la cotización: {motivo}")
            cot = cotizador.armar_cotizacion(r.args.modulos, propuesta)
            errores = validator.validar_cotizacion(cot, propuesta)
            if not errores:
                break
            estado.trazador.registrar(agente="validador", paso=intento + 1, error="; ".join(errores))
            if intento == config.MAX_REINTENTOS_VALIDADOR:
                return self._error(estado, "La cotización no pasó la validación: " + "; ".join(errores))
            correcciones = "; ".join(errores)

        estado.cotizacion = cot
        estado.archivos = self._archivos(estado.carpeta)
        return Respuesta(tipo="propuesta", texto=formatear_resumen(propuesta, cot), propuesta=propuesta,
                         cotizacion=cot, archivos=estado.archivos, preguntas_hechas=estado.preguntas)

    @staticmethod
    def _archivos(carpeta: Path) -> dict[str, str]:
        nombres = {"config": "config.json", "maqueta": "maqueta.html", "borrador": "cotizacion_borrador.txt"}
        return {k: str(carpeta / v) for k, v in nombres.items() if (carpeta / v).exists()}

    @staticmethod
    def _error(estado: EstadoSesion, texto: str) -> Respuesta:
        return Respuesta(tipo="error", texto=texto, preguntas_hechas=estado.preguntas)


def _pesos(valor: float) -> str:
    return f"${valor:,.0f}"


def formatear_resumen(p: Propuesta, c: Cotizacion) -> str:
    catalogo = datos.modulos()
    lineas = [f"Propuesta para tu negocio ({p.giro})", "",
              "Incluido siempre: " + ", ".join(catalogo[m]["nombre"] for m in config.MODULOS_BASE) + ".", "",
              "Te recomiendo:"]
    for m in p.modulos:
        lineas.append(f"  • {catalogo.get(m.id, {}).get('nombre', m.id)}: {m.motivo} (fuente: {m.doc_id})")
    if p.descartados:
        lineas += ["", "No te hace falta:"]
        lineas += [f"  • {catalogo.get(d.id, {}).get('nombre', d.id)}: {d.motivo}" for d in p.descartados]
    if c.fuera_presupuesto:
        motivos = {f.id: f.motivo for f in p.fuera_presupuesto}
        lineas += ["", "Lo dejé fuera por presupuesto (lo puedes agregar después):"]
        lineas += [f"  • {l.nombre} ({_pesos(l.precio)}): {motivos.get(l.id, '')}" for l in c.fuera_presupuesto]
    if p.fuera_catalogo:
        lineas += ["", "No está en el catálogo (lo registré para que el desarrollador te lo cotice aparte):"]
        lineas += [f"  • {n}" for n in p.fuera_catalogo]
    lineas += ["", "Cotización (borrador):"]
    lineas += [f"  {l.nombre:<34} {_pesos(l.precio):>8}" for l in c.lineas]
    total = f"  {'Total':<34} {_pesos(c.total):>8}"
    if c.presupuesto:
        total += f"  (presupuesto: {_pesos(c.presupuesto)}" + (", EXCEDE)" if c.excede_presupuesto else ")")
    lineas += [total, "", "¿Confirmas que emita la cotización con folio y vigencia de 15 días?"]
    return "\n".join(lineas)
