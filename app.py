"""Interfaz web de ModuLab (Streamlit): chat, maqueta en vivo y confirmación con botón.

    streamlit run app.py
    MODELO=simulado en .env -> sin red ni SQL Server (el caso de la estética con guion)

VERSIÓN FUNCIONAL INICIAL (Jesús) para congelar el mínimo. Gustavo es dueño de
la interfaz: puede rediseñarla, pero el flujo con el orquestador debe quedar así:
    r = orq.responder(sesion, texto)
    si r.requiere_confirmacion -> botones Confirmar / Cancelar -> orq.confirmar(sesion, aprobado)
El botón es el ÚNICO camino para emitir una cotización o sobrescribir un perfil.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from modulab import config, db
from modulab.confirmation import ProveedorConfirmacion
from modulab.guion_estetica import MODELO_SIMULADO
from modulab.llm import ClienteLLM, ProveedorSimulado
from modulab.orchestrator import Orquestador

st.set_page_config(page_title="ModuLab", page_icon="🧩", layout="wide")


# ------------------------------------------------------------------ estado de la sesión del navegador
def _cliente() -> ClienteLLM:
    # MODELO=simulado en .env: sin red ni SQL Server, reproduce el caso de la estética (para diseñar la interfaz).
    if config.MODELO == "simulado":
        db.usar(db.RepositorioMemoria())
        return ClienteLLM([ProveedorSimulado(MODELO_SIMULADO)], usar_cache=False)
    return ClienteLLM.desde_config()


def _nueva_sesion() -> None:
    st.session_state.orq = Orquestador(_cliente(), ProveedorConfirmacion("ui"))
    st.session_state.sesion = "web-" + uuid.uuid4().hex[:8]
    st.session_state.chat = []          # [(rol, texto)]
    st.session_state.ultima = None      # última Respuesta del orquestador


if "orq" not in st.session_state:
    _nueva_sesion()

orq: Orquestador = st.session_state.orq
sesion: str = st.session_state.sesion


def _atender(funcion, *args) -> None:
    try:
        with st.spinner("Pensando…"):
            r = funcion(*args)
    except Exception as e:  # que un fallo del modelo o de la base no tumbe la página
        st.session_state.chat.append(("assistant", f"Ocurrió un problema: {e}"))
        return
    st.session_state.ultima = r
    st.session_state.chat.append(("assistant", r.texto))


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.title("ModuLab")
    st.caption("Asistente que recomienda y cotiza los módulos de la plataforma web de tu negocio.")
    st.write(f"Modelo: **{config.MODELO}** · Base: **{config.BASE_DATOS}**")
    if st.button("Nueva conversación"):
        _nueva_sesion()
        st.rerun()
    st.divider()
    st.caption("¿Ya tienes código de negocio? Escríbelo en el chat (NEG-XXXXX) para retomar tu propuesta.")
    st.caption("No escribas nombres, teléfonos ni datos de tus clientes.")

izquierda, derecha = st.columns([3, 2], gap="large")

# ------------------------------------------------------------------ chat
with izquierda:
    st.subheader("Conversación")
    if not st.session_state.chat:
        st.info("Cuéntame de tu negocio: a qué se dedica, cómo trabajas hoy (citas, ventas, productos) "
                "y cuál es tu presupuesto.")
    for rol, texto in st.session_state.chat:
        with st.chat_message(rol):
            if rol == "assistant":
                st.text(texto)  # conserva la alineación de la cotización
            else:
                st.write(texto)

    r = st.session_state.ultima
    if r is not None and r.requiere_confirmacion:
        with st.container(border=True):
            if r.accion_pendiente == "emitir_cotizacion":
                st.markdown("**¿Emito la cotización con folio?** Una vez emitida no se puede modificar.")
            else:
                st.markdown("**¿Actualizo tu perfil guardado?** La versión anterior queda en el historial.")
                if r.diferencia_perfil:
                    st.json(r.diferencia_perfil, expanded=False)
            c1, c2 = st.columns(2)
            if c1.button("Confirmar", type="primary"):
                st.session_state.chat.append(("user", "[Presionó Confirmar]"))
                _atender(orq.confirmar, sesion, True)
                st.rerun()
            if c2.button("Cancelar"):
                st.session_state.chat.append(("user", "[Presionó Cancelar]"))
                _atender(orq.confirmar, sesion, False)
                st.rerun()

    texto = st.chat_input("Escribe aquí…")
    if texto:
        st.session_state.chat.append(("user", texto))
        _atender(orq.responder, sesion, texto)
        st.rerun()

# ------------------------------------------------------------------ vista previa, cotización y archivos
with derecha:
    r = st.session_state.ultima
    if r is not None and r.folio:
        st.success(f"Cotización **{r.folio}** emitida · vigente hasta {r.vigencia}  \n"
                   f"Tu código de negocio: **{r.codigo_negocio}**")
    st.subheader("Vista previa de tu sitio")
    maqueta = r.archivos.get("maqueta") if r is not None else None
    if maqueta and Path(maqueta).exists():
        components.html(Path(maqueta).read_text(encoding="utf-8"), height=420, scrolling=True)
    else:
        st.caption("Aquí aparecerá la maqueta con los módulos que te recomiende.")

    if r is not None and r.cotizacion:
        st.subheader("Cotización")
        filas = [{"Módulo": l.nombre, "Precio (MXN)": f"${l.precio:,.0f}"} for l in r.cotizacion.lineas]
        filas.append({"Módulo": "Total", "Precio (MXN)": f"${r.cotizacion.total:,.0f}"})
        st.table(filas)
        if r.cotizacion.fuera_presupuesto:
            st.caption("Fuera por presupuesto: " + ", ".join(
                f"{l.nombre} (${l.precio:,.0f})" for l in r.cotizacion.fuera_presupuesto))

    if r is not None and r.archivos:
        st.subheader("Archivos")
        etiquetas = {"cotizacion_oficial": "Cotización oficial", "borrador": "Cotización borrador",
                     "config": "Configuración (JSON)", "maqueta": "Maqueta (HTML)"}
        for clave, etiqueta in etiquetas.items():
            ruta = r.archivos.get(clave)
            if ruta and Path(ruta).exists():
                st.download_button(etiqueta, Path(ruta).read_bytes(), file_name=Path(ruta).name,
                                   key=f"dl-{clave}")

    estado = orq.sesiones.get(sesion)
    if estado and estado.trazador.registros:
        with st.expander(f"Traza ({len(estado.trazador.registros)} pasos)"):
            st.dataframe([{"agente": t.agente, "paso": t.paso, "herramienta": t.herramienta or "",
                           "ms": t.latencia_ms, "modelo": t.modelo or "", "nota": (t.error or "")[:120]}
                          for t in estado.trazador.registros], hide_index=True)
