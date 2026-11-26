"""Pruebas sin modelo real: la rebanada vertical de la estética y las piezas de Jesús."""
import json

import pytest
from pydantic import BaseModel

from modulab import config, db
from modulab.guion_estetica import DUENO, MODELO_SIMULADO, SECUENCIA_ESPERADA
from modulab.llm import ClienteLLM, ProveedorSimulado, _esquema_gemini
from modulab.loop import Herramienta, ejecutar_agente, esquema_plano
from modulab.orchestrator import Orquestador
from modulab.schemas import Propuesta
from modulab.tools import catalogo as cat
from modulab.tracing import Trazador


@pytest.fixture(autouse=True)
def salidas_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "TRAZAS_DIR", tmp_path / "outputs" / "trazas")
    db.usar(db.RepositorioMemoria())


def _orquestador(guion=MODELO_SIMULADO):
    return Orquestador(ClienteLLM([ProveedorSimulado(guion)], usar_cache=False))


# ------------------------------------------------------------------ rebanada vertical
def test_caso_estetica_de_punta_a_punta(tmp_path):
    orq = _orquestador()
    r1 = orq.responder("s1", DUENO[0])
    r2 = orq.responder("s1", DUENO[1])
    r3 = orq.responder("s1", DUENO[2])

    assert (r1.tipo, r2.tipo) == ("pregunta", "pregunta")
    assert r3.tipo == "propuesta" and r3.preguntas_hechas == 2
    assert r3.requiere_confirmacion and r3.accion_pendiente == "emitir_cotizacion"
    assert {m.id for m in r3.propuesta.modulos} == {"M04", "M05", "M06"}
    assert [l.id for l in r3.cotizacion.lineas] == ["M01", "M02", "M03", "M04", "M05", "M06"]
    assert r3.cotizacion.total == 7300 and not r3.cotizacion.excede_presupuesto
    assert [l.id for l in r3.cotizacion.fuera_presupuesto] == ["M07"]
    assert db.repositorio().solicitudes[0]["descripcion"].startswith("Programa de puntos")
    assert db.repositorio().cotizaciones() == []  # nada emitido sin confirmar
    for ruta in r3.archivos.values():
        assert (tmp_path / "outputs").exists() and ruta and open(ruta, encoding="utf-8").read()
    assert orq.sesiones["s1"].trazador.herramientas_usadas == SECUENCIA_ESPERADA


def test_traza_en_disco_tiene_un_registro_por_paso():
    orq = _orquestador()
    for texto in DUENO:
        orq.responder("s1", texto)
    trazador = orq.sesiones["s1"].trazador
    lineas = trazador.archivo.read_text(encoding="utf-8").strip().splitlines()
    assert len(lineas) == len(trazador.registros) == len(SECUENCIA_ESPERADA)
    assert all(json.loads(l)["ejecucion_id"] == trazador.ejecucion_id for l in lineas)


def test_ningun_precio_sale_del_modelo():
    guion = json.loads(json.dumps(MODELO_SIMULADO))
    guion["cotizador"][-1]["llamadas"][0]["args"]["resumen"] = "Total con descuento: $100"
    orq = _orquestador(guion)
    for texto in DUENO:
        r = orq.responder("s1", texto)
    assert r.cotizacion.total == 7300


# ------------------------------------------------------------------ herramientas
def test_resolver_dependencias_en_cadena():
    r = cat.resolver_dependencias(cat.ArgsResolverDependencias(modulos=["M05"]))
    assert r["modulos_adicionales"] == ["M04", "M05"]
    assert r["agregados_por_dependencia"] == [{"id": "M04", "nombre": "Citas", "requerido_por": "M05"}]


def test_resolver_dependencias_sin_duplicados_e_inexistentes():
    r = cat.resolver_dependencias(cat.ArgsResolverDependencias(modulos=["M04", "M05", "M06", "M99"]))
    assert r["modulos_adicionales"] == ["M04", "M05", "M06"]
    assert r["no_existen"] == ["M99"]


def test_buscar_catalogo_encuentra_citas_para_estetica():
    r = cat.buscar_catalogo(cat.ArgsBuscarCatalogo(consulta="estética infantil citas por WhatsApp"))
    assert "FICHA-M04" in [x["doc_id"] for x in r["resultados"]]


def test_buscar_catalogo_no_inventa_programa_de_puntos():
    r = cat.buscar_catalogo(cat.ArgsBuscarCatalogo(consulta="programa de puntos clientes frecuentes"))
    # Ninguna ficha de módulo cubre esa necesidad; solo puede aparecer un caso que diga que no existe.
    assert not [x for x in r["resultados"] if x["doc_id"].startswith("FICHA-")]


def test_consultar_precios_reporta_inexistentes():
    r = cat.consultar_precios(cat.ArgsConsultarPrecios(modulos=["M04", "M99"]))
    assert r["precios_mxn"]["M04"]["precio"] == 1800 and r["no_existen"] == ["M99"]


# ------------------------------------------------------------------ bucle ReAct
class _Args(BaseModel):
    n: int


def _herramientas():
    return [Herramienta("doble", "Duplica n", _Args, lambda a: {"valor": a.n * 2}),
            Herramienta("fin", "Termina", _Args, terminal=True)]


def _correr(pasos, max_pasos=8):
    cliente = ClienteLLM([ProveedorSimulado({"prueba": pasos})], usar_cache=False)
    mensajes = [{"role": "user", "content": "hola"}]
    r = ejecutar_agente("prueba", "sistema", mensajes, _herramientas(), cliente, Trazador(), max_pasos)
    return r, mensajes


def test_argumentos_invalidos_vuelven_como_observacion():
    r, mensajes = _correr([
        {"llamadas": [{"nombre": "doble", "args": {"n": "no es número"}}]},
        {"llamadas": [{"nombre": "doble", "args": {"n": 2}}]},
        {"llamadas": [{"nombre": "fin", "args": {"n": 4}}]}])
    assert r.terminal == "fin" and r.args.n == 4
    observaciones = [m["content"] for m in mensajes if m["role"] == "tool"]
    assert "error" in observaciones[0] and observaciones[1] == {"valor": 4}


def test_herramienta_inexistente_no_rompe_el_bucle():
    r, mensajes = _correr([
        {"llamadas": [{"nombre": "borrar_todo", "args": {}}]},
        {"llamadas": [{"nombre": "fin", "args": {"n": 1}}]}])
    assert r.terminal == "fin"
    assert "no existe" in mensajes[2]["content"]["error"]


def test_tope_de_pasos():
    r, _ = _correr([{"llamadas": [{"nombre": "doble", "args": {"n": 1}}]}] * 3, max_pasos=3)
    assert r.agotado and r.pasos == 3


def test_tope_de_preguntas(monkeypatch):
    monkeypatch.setattr(config, "MAX_PREGUNTAS", 1)
    pregunta = {"llamadas": [{"nombre": "preguntar_al_dueno", "args": {"pregunta": "¿Algo más?"}}]}
    guion = {"analista": [pregunta, {"llamadas": [{"nombre": "preguntar_al_dueno", "args": {"pregunta": "¿Y?"}}]},
                          {"llamadas": [{"nombre": "entregar_propuesta",
                                         "args": MODELO_SIMULADO["analista"][-1]["llamadas"][0]["args"]}]}],
             "cotizador": MODELO_SIMULADO["cotizador"]}
    orq = _orquestador(guion)
    assert orq.responder("s", "Tengo una estética").tipo == "pregunta"
    # Sin la herramienta de preguntar, el intento de preguntar de nuevo es rechazado y el agente entrega.
    assert orq.responder("s", "Sí").tipo == "propuesta"


# ------------------------------------------------------------------ esquemas
def test_esquemas_sin_referencias_y_validos_para_gemini():
    plano = esquema_plano(Propuesta)
    texto = json.dumps(plano)
    assert "$ref" not in texto and "$defs" not in texto and "anyOf" not in texto
    gemini = _esquema_gemini(plano)
    assert gemini["type"] == "OBJECT"
    assert gemini["properties"]["modulos"]["items"]["type"] == "OBJECT"


# ------------------------------------------------------------------ respaldo entre proveedores
class _Falla:
    nombre, modelo = "gemini", "modelo-retirado"

    def chat(self, *a):
        from modulab.llm import ErrorLLM
        raise ErrorLLM("404 NOT_FOUND: modelo no disponible", reintentable=False, codigo=404)


class _Responde:
    nombre, modelo = "groq", "respaldo"

    def chat(self, *a):
        from modulab.llm import RespuestaLLM
        return RespuestaLLM(texto="hola desde el respaldo", modelo="groq:respaldo")


def test_error_no_reintentable_pasa_al_siguiente_proveedor():
    cliente = ClienteLLM([_Falla(), _Responde()], usar_cache=False)
    r = cliente.chat("sistema", [{"role": "user", "content": "hola"}], [])
    assert r.modelo == "groq:respaldo" and cliente.llamadas_reales == 1


def test_si_todos_fallan_se_reporta_el_motivo():
    from modulab.llm import ErrorLLM
    cliente = ClienteLLM([_Falla()], usar_cache=False)
    with pytest.raises(ErrorLLM, match="404"):
        cliente.chat("sistema", [{"role": "user", "content": "hola"}], [])
