"""Configurador (tercer agente): adapta la maqueta al giro sin tocar módulos ni precios."""
import copy

import pytest

from modulab import db
from modulab.guion_estetica import DUENO, MODELO_SIMULADO
from modulab.llm import ClienteLLM, ProveedorSimulado
from modulab.orchestrator import Orquestador
from modulab.tools import datos
from modulab.tools.salidas import ArgsGenerarConfiguracion, generar_configuracion


@pytest.fixture(autouse=True)
def _memoria(tmp_path):
    db.usar(db.RepositorioMemoria())
    marca = datos.carpeta_sesion.set(tmp_path)
    yield
    datos.carpeta_sesion.reset(marca)


def _correr(guion):
    orq = Orquestador(ClienteLLM([ProveedorSimulado(guion)], usar_cache=False))
    for texto in DUENO:
        r = orq.responder("s", texto)
    return orq, r


def test_la_maqueta_usa_los_textos_del_configurador_en_su_orden():
    orq, r = _correr(MODELO_SIMULADO)
    assert r.cotizacion.total == 7300
    maqueta = open(r.archivos["maqueta"], encoding="utf-8").read()
    assert "Agenda el corte de tu peque" in maqueta
    assert maqueta.index("Avisos del próximo corte") < maqueta.index("Agenda el corte de tu peque")
    assert orq.sesiones["s"].trazador.herramientas_usadas[-2:] == ["generar_configuracion", "entregar_configuracion"]


def test_el_configurador_no_puede_poner_precios_ni_modulos_ajenos():
    con_precio = generar_configuracion(ArgsGenerarConfiguracion(
        modulos=["M04"], giro="estética infantil",
        secciones=[{"id": "M04", "titulo": "Citas", "texto": "Agenda por solo $99 pesos"}]))
    assert "error" in con_precio and "precio" in con_precio["error"]
    ajeno = generar_configuracion(ArgsGenerarConfiguracion(
        modulos=["M04"], giro="estética infantil",
        secciones=[{"id": "M10", "titulo": "Reservas", "texto": "Reserva tu mesa"}]))
    assert "error" in ajeno and "M10" in ajeno["error"]


def test_si_el_configurador_falla_se_genera_la_maqueta_generica():
    guion = copy.deepcopy(MODELO_SIMULADO)
    guion["configurador"] = []  # el modelo no responde nada útil
    orq, r = _correr(guion)
    assert r.cotizacion.total == 7300 and "maqueta" in r.archivos
    assert any(t.agente == "configurador" and t.error for t in orq.sesiones["s"].trazador.registros)


def test_la_maqueta_trae_sus_propios_estilos_y_no_depende_del_tema():
    """En Streamlit con tema oscuro la maqueta salía con fondo transparente y texto negro (27-nov)."""
    res = generar_configuracion(ArgsGenerarConfiguracion(modulos=["M04"], giro="estética infantil",
                                                         bienvenida="Hola"))
    html = open(res["maqueta_html"], encoding="utf-8").read()
    assert "<style>" in html and "background" in html and "color-scheme: light" in html
