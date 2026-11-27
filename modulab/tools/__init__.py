"""Registro de herramientas: las 9 de la ficha + las terminales de control.

Cada agente recibe solo su subconjunto (ver HERRAMIENTAS_ANALISTA y
HERRAMIENTAS_COTIZADOR y HERRAMIENTAS_CONFIGURADOR). La descripción es lo que lee el modelo: si la
cambias, anótalo en prompts/CHANGELOG.md como cualquier prompt.
"""
from __future__ import annotations

from ..loop import Herramienta
from . import catalogo, control, emision, perfil, salidas, solicitudes

BUSCAR_CATALOGO = Herramienta(
    "buscar_catalogo",
    "Busca en el catálogo de módulos y documentos del desarrollador los que sirven para un giro o una necesidad. "
    "Devuelve fragmentos con doc_id. Úsala antes de recomendar cualquier módulo.",
    catalogo.ArgsBuscarCatalogo, catalogo.buscar_catalogo)

CONSULTAR_PRECIOS = Herramienta(
    "consultar_precios",
    "Devuelve el precio en pesos de cada módulo según la lista oficial. Úsala para saber qué cabe en el presupuesto.",
    catalogo.ArgsConsultarPrecios, catalogo.consultar_precios)

RESOLVER_DEPENDENCIAS = Herramienta(
    "resolver_dependencias",
    "Recibe los módulos que quieres recomendar y agrega los que estos requieren para funcionar "
    "(por ejemplo, Recordatorios requiere Citas). Úsala antes de entregar la propuesta.",
    catalogo.ArgsResolverDependencias, catalogo.resolver_dependencias)

LEER_PERFIL = Herramienta(
    "leer_perfil",
    "Recupera el perfil guardado de un negocio que ya usó el asistente, a partir de su código NEG-XXXXX.",
    perfil.ArgsLeerPerfil, perfil.leer_perfil)

GUARDAR_PERFIL = Herramienta(
    "guardar_perfil",
    "Guarda el perfil del negocio (sin datos personales). Si ya existe, requiere confirmación del dueño.",
    perfil.ArgsGuardarPerfil, perfil.guardar_perfil)

REGISTRAR_SOLICITUD = Herramienta(
    "registrar_solicitud_especial",
    "Registra una necesidad que NO existe en el catálogo para que el desarrollador la cotice aparte. Nunca le pongas precio.",
    solicitudes.ArgsSolicitudEspecial, solicitudes.registrar_solicitud_especial)

GENERAR_CONFIGURACION = Herramienta(
    "generar_configuracion",
    "Genera el config.json y la maqueta HTML del sitio con los módulos elegidos (los 3 base se agregan solos). "
    "Acepta una bienvenida y, por módulo, un título y un texto en el lenguaje del negocio, en el orden deseado.",
    salidas.ArgsGenerarConfiguracion, salidas.generar_configuracion)

GENERAR_COTIZACION_PDF = Herramienta(
    "generar_cotizacion_pdf",
    "Genera la cotización en borrador (sin folio) con los precios oficiales de los módulos elegidos.",
    salidas.ArgsGenerarCotizacionPdf, salidas.generar_cotizacion_pdf)

EMITIR_COTIZACION = Herramienta(  # no se entrega a agentes: la ejecuta el código tras Confirmar
    "emitir_cotizacion",
    "Emite la cotización oficial con folio y vigencia. Requiere token de confirmación.",
    emision.ArgsEmitirCotizacion, emision.emitir_cotizacion)

# --- terminales ---------------------------------------------------------------
PREGUNTAR_AL_DUENO = Herramienta(
    "preguntar_al_dueno",
    "Hace UNA pregunta al dueño y termina tu turno hasta que conteste. Úsala solo si te falta un dato que cambia la recomendación.",
    control.ArgsPreguntar, terminal=True)

ENTREGAR_PROPUESTA = Herramienta(
    "entregar_propuesta",
    "Entrega la propuesta final de módulos con su motivo y doc_id, lo descartado, lo que queda fuera por presupuesto "
    "y lo que no existe en el catálogo. Termina tu trabajo.",
    control.ArgsEntregarPropuesta, terminal=True)

ENTREGAR_COTIZACION = Herramienta(
    "entregar_cotizacion",
    "Entrega la lista final de módulos adicionales cotizados. Los precios los pone el sistema desde la lista oficial.",
    control.ArgsEntregarCotizacion, terminal=True)

ENTREGAR_CONFIGURACION = Herramienta(
    "entregar_configuracion",
    "Entrega la configuración del sitio ya generada con generar_configuracion. Termina tu trabajo.",
    control.ArgsEntregarConfiguracion, terminal=True)

DE_DOMINIO = [BUSCAR_CATALOGO, CONSULTAR_PRECIOS, RESOLVER_DEPENDENCIAS, LEER_PERFIL, GUARDAR_PERFIL,
              REGISTRAR_SOLICITUD, GENERAR_CONFIGURACION, GENERAR_COTIZACION_PDF, EMITIR_COTIZACION]

HERRAMIENTAS_ANALISTA = [BUSCAR_CATALOGO, CONSULTAR_PRECIOS, RESOLVER_DEPENDENCIAS, LEER_PERFIL,
                         REGISTRAR_SOLICITUD, PREGUNTAR_AL_DUENO, ENTREGAR_PROPUESTA]

HERRAMIENTAS_COTIZADOR = [CONSULTAR_PRECIOS, RESOLVER_DEPENDENCIAS, GENERAR_COTIZACION_PDF, ENTREGAR_COTIZACION]

HERRAMIENTAS_CONFIGURADOR = [GENERAR_CONFIGURACION, ENTREGAR_CONFIGURACION]
