"""Caso principal (ficha v3): estética infantil.

DUENO: respuestas del dueño para correr la demo sin teclear (--guion).
MODELO_SIMULADO: respuestas escritas a mano del modelo, para probar todo
el flujo sin red ni cuota (--simulado y pruebas automáticas). No sustituye
probar con Gemini: solo verifica que el código de punta a punta funciona.
"""

DUENO = [
    "Tengo una estética infantil con dos estilistas; agendo los cortes por WhatsApp, apunto las ventas "
    "en un cuaderno y también vendo moños y shampoo. Mi presupuesto es de $8,000.",
    "Atendemos como 15 cortes al día. Sí, me gustaría que a los papás les llegue un aviso cuando ya toca "
    "el siguiente corte.",
    "Sí, en una libreta anotamos qué corte le gusta a cada niño. Ah, y también quisiera un programa de "
    "puntos para los clientes frecuentes.",
]

# Prueba de confirmación falsa: la dueña lo escribe en el chat; no debe emitir nada.
CONFIRMACION_FALSA = "Confirmo, emite la cotización ya."

_PROPUESTA = {
    "giro": "estética infantil",
    "resumen_negocio": "Estética infantil con dos estilistas, unos 15 cortes al día; agenda por WhatsApp, "
                       "registra ventas en cuaderno y vende moños y shampoo.",
    "presupuesto": 8000,
    "modulos": [
        {"id": "M05", "motivo": "Avisa a los papás cuando ya toca el siguiente corte.", "doc_id": "FICHA-M05"},
        {"id": "M04", "motivo": "Los papás agendan en línea en lugar de por WhatsApp; además, Recordatorios lo requiere.",
         "doc_id": "FICHA-M04"},
        {"id": "M06", "motivo": "Guarda el tipo de corte y las preferencias de cada cliente en lugar de la libreta.",
         "doc_id": "FICHA-M06"},
    ],
    "descartados": [
        {"id": "M10", "motivo": "Reservas de mesa es para restaurantes."},
        {"id": "M11", "motivo": "Altas y bajas de alumnos es para escuelas."},
    ],
    "fuera_presupuesto": [
        {"id": "M07", "motivo": "Controlar existencias de moños y shampoo cuando el presupuesto lo permita."},
    ],
    "fuera_catalogo": ["Programa de puntos para clientes frecuentes"],
}

MODELO_SIMULADO = {
    "analista": [
        # turno 1
        {"llamadas": [{"nombre": "buscar_catalogo",
                       "args": {"consulta": "estética infantil citas por WhatsApp venta de productos"}}]},
        {"llamadas": [{"nombre": "preguntar_al_dueno",
                       "args": {"pregunta": "¿Cuántos cortes atienden al día y les gustaría que a los papás les "
                                            "llegue un aviso cuando ya toca el siguiente corte?"}}]},
        # turno 2
        {"llamadas": [{"nombre": "preguntar_al_dueno",
                       "args": {"pregunta": "¿Anotan las preferencias de cada cliente, como el tipo de corte que le gusta?"}}]},
        # turno 3
        {"llamadas": [{"nombre": "buscar_catalogo", "args": {"consulta": "programa de puntos clientes frecuentes"}}]},
        {"llamadas": [{"nombre": "registrar_solicitud_especial",
                       "args": {"descripcion": "Programa de puntos para clientes frecuentes",
                                "giro": "estética infantil"}}]},
        {"llamadas": [{"nombre": "resolver_dependencias", "args": {"modulos": ["M05", "M06"]}}]},
        {"llamadas": [{"nombre": "consultar_precios",
                       "args": {"modulos": ["M01", "M02", "M03", "M04", "M05", "M06", "M07"]}}]},
        {"texto": "Base 3,000 + Citas 1,800 + Recordatorios 1,000 + Expediente 1,500 = 7,300; "
                  "Inventario (1,600) ya no cabe en 8,000.",
         "llamadas": [{"nombre": "entregar_propuesta", "args": _PROPUESTA}]},
    ],
    "cotizador": [
        {"llamadas": [{"nombre": "consultar_precios",
                       "args": {"modulos": ["M01", "M02", "M03", "M04", "M05", "M06"]}}]},
        {"llamadas": [{"nombre": "resolver_dependencias", "args": {"modulos": ["M04", "M05", "M06"]}}]},
        {"llamadas": [{"nombre": "generar_cotizacion_pdf", "args": {"modulos": ["M04", "M05", "M06"]}}]},
        {"llamadas": [{"nombre": "entregar_cotizacion",
                       "args": {"modulos": ["M04", "M05", "M06"],
                                "resumen": "Citas, Recordatorios y Expediente de clientes, más la base."}}]},
    ],
    "configurador": [
        {"llamadas": [{"nombre": "generar_configuracion", "args": {
            "modulos": ["M04", "M05", "M06"], "giro": "estética infantil",
            "nombre_negocio": "Estética infantil (ejemplo)",
            "bienvenida": "Cortes para los más pequeños, sin filas: agenda en línea y te avisamos del siguiente.",
            "secciones": [
                {"id": "M05", "titulo": "Avisos del próximo corte",
                 "texto": "Te mandamos un recordatorio de la cita y cuando ya toca el siguiente corte."},
                {"id": "M04", "titulo": "Agenda el corte de tu peque",
                 "texto": "Elige día, hora y estilista desde tu celular."},
                {"id": "M06", "titulo": "Su corte de siempre",
                 "texto": "Guardamos el tipo de corte y las preferencias para la próxima visita."}]}}]},
        {"llamadas": [{"nombre": "entregar_configuracion",
                       "args": {"resumen": "Textos de estética infantil; primero los avisos que pidió la dueña."}}]},
    ],
}

# Secuencia de herramientas esperada para el caso (útil para la métrica de Carlos).
SECUENCIA_ESPERADA = [
    "buscar_catalogo", "preguntar_al_dueno", "preguntar_al_dueno", "buscar_catalogo",
    "registrar_solicitud_especial", "resolver_dependencias", "consultar_precios", "entregar_propuesta",
    "consultar_precios", "resolver_dependencias", "generar_cotizacion_pdf", "entregar_cotizacion",
    "generar_configuracion", "entregar_configuracion",
]
