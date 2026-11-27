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
    assert orq.responder("s", "Tengo una estética; mi presupuesto es de $8,000").tipo == "pregunta"
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


# ------------------------------------------------------------------ coherencia del analista
def test_no_se_descarta_un_modulo_del_giro_y_se_obliga_a_preguntar():
    from modulab.agents.analista import revisar_coherencia
    p = Propuesta.model_validate(MODELO_SIMULADO["analista"][-1]["llamadas"][0]["args"])
    assert revisar_coherencia(p, preguntas_hechas=2) == []
    malo = Propuesta.model_validate({**p.model_dump(), "descartados": [{"id": "M06", "motivo": "Historial por cliente"}]})
    errores = revisar_coherencia(malo, preguntas_hechas=0)
    assert any("M06" in e for e in errores) and any("pregúntale" in e for e in errores)


def test_la_correccion_vuelve_al_analista_y_este_pregunta():
    import copy as _copy
    guion = _copy.deepcopy(MODELO_SIMULADO)
    mala = _copy.deepcopy(guion["analista"][-1]["llamadas"][0]["args"])
    mala["descartados"].append({"id": "M06", "motivo": "Historial por cliente"})
    guion["analista"] = [
        {"llamadas": [{"nombre": "buscar_catalogo", "args": {"consulta": "estética infantil"}}]},
        {"llamadas": [{"nombre": "entregar_propuesta", "args": mala}]},
        {"llamadas": [{"nombre": "preguntar_al_dueno", "args": {"pregunta": "¿Qué te importa más: guardar las "
                                                                "preferencias de cada niño o controlar tus productos?"}}]}]
    orq = _orquestador(guion)
    r = orq.responder("s", DUENO[0])
    assert r.tipo == "pregunta" and "preferencias" in r.texto


def test_fuera_de_presupuesto_debe_no_caber_de_verdad():
    from modulab.agents.analista import revisar_coherencia
    base = MODELO_SIMULADO["analista"][-1]["llamadas"][0]["args"]
    # Corrida real del 26 nov: solo Citas ($4,800 de $8,000) y todo lo demás "fuera por presupuesto".
    sobrecorregida = Propuesta.model_validate({**base, "modulos": [base["modulos"][1]], "descartados": [],
        "fuera_presupuesto": [{"id": m, "motivo": "después"} for m in ["M05", "M06", "M07", "M08"]]})
    errores = revisar_coherencia(sobrecorregida, preguntas_hechas=1)
    assert sum("sí cabe" in e for e in errores) == 4
    # Después de preguntar, descartar un módulo del giro que el dueño no quiere sí se permite.
    ok = Propuesta.model_validate({**base, "descartados": [{"id": "M08", "motivo": "El dueño dijo que no lo necesita"}]})
    assert revisar_coherencia(ok, preguntas_hechas=1) == []


def test_la_propuesta_no_se_pasa_del_presupuesto():
    from modulab.agents.analista import revisar_coherencia
    base = MODELO_SIMULADO["analista"][-1]["llamadas"][0]["args"]
    # Corrida real COT-2026-0007: Citas, Recordatorios, Expediente e Inventario = $8,900 de $8,000.
    excedida = Propuesta.model_validate({**base, "fuera_presupuesto": [],
        "modulos": base["modulos"] + [{"id": "M07", "motivo": "inventario", "doc_id": "FICHA-M07"}]})
    errores = revisar_coherencia(excedida, preguntas_hechas=1)
    assert any("te pasas por $900" in e for e in errores)
    con_mas_dinero = Propuesta.model_validate({**excedida.model_dump(), "presupuesto": 9000})
    assert revisar_coherencia(con_mas_dinero, preguntas_hechas=1) == []


def test_el_respaldo_y_la_cache_quedan_en_la_traza(tmp_path, monkeypatch):
    """Corrida real del 26-nov: con --modelo groq respondió Gemini y la traza no decía por qué."""
    from modulab import config
    from modulab.llm import ClienteLLM, ErrorLLM, RespuestaLLM
    from modulab.loop import ejecutar_agente
    from modulab.tracing import Trazador

    class Falla:
        nombre, modelo = "groq", "x"
        def chat(self, *a): raise ErrorLLM("401 llave inválida", reintentable=False)

    class Responde:
        nombre, modelo = "gemini", "y"
        def chat(self, *a): return RespuestaLLM(texto="hola", llamadas=[], modelo="gemini:y")

    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    cliente = ClienteLLM([Falla(), Responde()], usar_cache=True)
    tr = Trazador(carpeta=tmp_path)
    ejecutar_agente("analista", "s", [{"role": "user", "content": "hola"}], [], cliente, tr, 1)
    assert any(t.error and "respaldo" in t.error and "401" in t.error for t in tr.registros)
    # segunda vez: Groq vuelve a fallar y la respuesta de Gemini sale de la caché, marcada como tal
    ejecutar_agente("analista", "s", [{"role": "user", "content": "hola"}], [], cliente, tr, 1)
    assert any("(caché)" in (t.modelo or "") for t in tr.registros)


def test_casos_dev_revisa_la_propuesta_sin_emitir():
    from modulab.casos_dev import CASOS, correr
    from modulab.llm import ClienteLLM, ProveedorSimulado
    estetica = next(c for c in CASOS if c["id"] == "estetica")
    res = correr(estetica, ClienteLLM([ProveedorSimulado(MODELO_SIMULADO)], usar_cache=False))
    assert res["ok"], res["fallas"]
    assert res["modulos"] == ["M01", "M02", "M03", "M04", "M05", "M06"] and res["total"] == 7300
    # Si la propuesta se sale de lo esperado, el caso lo reporta como falla.
    exigente = {**estetica, "debe": ["M07"], "no_debe": ["M06"]}
    res = correr(exigente, ClienteLLM([ProveedorSimulado(MODELO_SIMULADO)], usar_cache=False))
    assert not res["ok"] and any("M07" in f for f in res["fallas"]) and any("M06" in f for f in res["fallas"])


# ------------------------------------------------------------------ casos de desarrollo del 26-nov
def test_buscar_por_id_de_modulo_devuelve_su_ficha():
    """Caso fonda (6399b1927af8): el analista buscó 'M10 catalogo modulo' y nunca obtuvo la ficha; gastó 8 pasos."""
    from modulab.tools.catalogo import ArgsBuscarCatalogo, buscar_catalogo
    assert buscar_catalogo(ArgsBuscarCatalogo(consulta="M10 catalogo modulo"))["resultados"][0]["doc_id"] == "FICHA-M10"
    ids = [r["doc_id"] for r in buscar_catalogo(ArgsBuscarCatalogo(consulta="fichas M07 M08 M09"))["resultados"][:3]]
    assert ids == ["FICHA-M07", "FICHA-M08", "FICHA-M09"]


def test_lo_que_cabe_cuenta_sus_dependencias():
    """Caso presupuesto bajo (698928515145): 'M05 sí cabe' ignoraba que M05 requiere M04 y llevó el total a $5,800."""
    from modulab.agents.analista import revisar_coherencia
    base = MODELO_SIMULADO["analista"][-1]["llamadas"][0]["args"]
    solo_base = Propuesta.model_validate({**base, "presupuesto": 4000, "modulos": [], "descartados": [],
        "fuera_presupuesto": [{"id": "M04", "motivo": "no alcanza"}, {"id": "M05", "motivo": "no alcanza"}]})
    assert revisar_coherencia(solo_base, preguntas_hechas=1) == []


def test_cotizador_que_responde_sin_herramienta_recibe_otra_oportunidad():
    """Caso estética (7424f2803d39): el cotizador respondió vacío en el paso 5 y la conversación terminó en error."""
    import copy as _copy
    guion = _copy.deepcopy(MODELO_SIMULADO)
    guion["cotizador"].insert(len(guion["cotizador"]) - 1, {"texto": None, "llamadas": []})
    orq = _orquestador(guion)
    for texto in DUENO:
        r = orq.responder("s", texto)
    assert r.cotizacion is not None and r.cotizacion.total == 7300


def test_si_se_pasa_del_presupuesto_pregunta_al_dueno_en_vez_de_recortar_solo():
    """Casos estética (d396fbe9932f) y presupuesto bajo (81b1026f21ba): al pasarse, el analista quitó lo que
    la dueña había pedido (Recordatorios) o entregó excedido. La primera vez debe preguntarle qué deja fuera."""
    import copy as _copy
    from modulab.agents.analista import revisar_coherencia
    base = MODELO_SIMULADO["analista"][-1]["llamadas"][0]["args"]
    excedida = {**base, "fuera_presupuesto": [],
                "modulos": base["modulos"] + [{"id": "M07", "motivo": "inventario", "doc_id": "FICHA-M07"}]}
    errores = revisar_coherencia(Propuesta.model_validate(excedida), 1, preguntar_recorte=True)
    assert any("te pasas por $900" in e and "pregúntale al dueño" in e for e in errores)

    guion = _copy.deepcopy(MODELO_SIMULADO)
    guion["analista"] = [
        {"llamadas": [{"nombre": "entregar_propuesta", "args": excedida}]},
        {"llamadas": [{"nombre": "preguntar_al_dueno", "args": {"pregunta": "¿Qué prefieres dejar para después?"}}]}]
    orq = _orquestador(guion)
    r = orq.responder("s", DUENO[0] + " " + DUENO[1])
    assert r.tipo == "pregunta" and orq.sesiones["s"].recorte_consultado


def test_analista_que_escribe_la_propuesta_como_texto_debe_entregarla_con_su_herramienta():
    """Caso presupuesto bajo (97e3cd523c35): 4 de sus 6 'preguntas' eran la propuesta escrita como texto."""
    import copy as _copy
    guion = _copy.deepcopy(MODELO_SIMULADO)
    entrega = guion["analista"][-1]
    pregunta = {"llamadas": [{"nombre": "preguntar_al_dueno", "args": {"pregunta": "¿Anotas qué corte le gusta?"}}]}
    guion["analista"] = [{"texto": "Con tu presupuesto te propongo: Citas, Recordatorios y Expediente.", "llamadas": []},
                         pregunta, entrega]
    orq = _orquestador(guion)
    r = orq.responder("s", DUENO[0] + " " + DUENO[1])
    assert r.tipo == "pregunta" and "corte" in r.texto and orq.sesiones["s"].preguntas == 1  # el texto no contó
    r = orq.responder("s", DUENO[2])
    assert r.propuesta is not None and r.cotizacion.total == 7300


# ------------------------------------------------------------------ casos de desarrollo del 27-nov
def test_el_revisor_dice_cuanto_queda_despues_de_la_base():
    """Caso presupuesto bajo (106c9257c74a): el modelo creía que con Citas ($1,800) de $4,000 'quedaban $2,200'."""
    from modulab.agents.analista import revisar_coherencia
    base = MODELO_SIMULADO["analista"][-1]["llamadas"][0]["args"]
    solo_citas = Propuesta.model_validate({**base, "presupuesto": 4000, "descartados": [], "fuera_presupuesto": [],
        "modulos": [{"id": "M04", "motivo": "agenda", "doc_id": "FICHA-M04"}]})
    errores = revisar_coherencia(solo_citas, 2)
    assert any("La base ($3,000) siempre cuenta" in e and "quedan $1,000" in e for e in errores)


def test_el_analista_no_inventa_presupuesto():
    """Caso presupuesto bajo (106c9257c74a): subió el presupuesto a $4,800 sin que la dueña lo dijera."""
    from modulab.agents.analista import montos_en, revisar_coherencia
    assert montos_en("Solo tengo $4,000.") == {4000.0}
    assert {8000.0, 15.0} <= montos_en("Atendemos 15 cortes; mi presupuesto es de 8 mil pesos")
    base = MODELO_SIMULADO["analista"][-1]["llamadas"][0]["args"]
    inventada = Propuesta.model_validate({**base, "presupuesto": 9000})
    errores = revisar_coherencia(inventada, 2, montos_dueno={8000.0, 15.0})
    assert any("nunca dijo $9,000" in e for e in errores)
    assert not any("nunca dijo" in e for e in revisar_coherencia(Propuesta.model_validate(base), 2, montos_dueno={8000.0}))


def test_prompts_congelados():
    """Congelados el 27-nov tras 6/6 casos de desarrollo: cambiarlos exige versión nueva y entrada en CHANGELOG."""
    import hashlib
    from modulab import config
    congelados = {"analista_v2.md": "31ff3f07bf3dec149ad29a143a5ed327",
                  "cotizador_v1.md": "573af3e4ab193d87685adbaa3d36511d"}
    for nombre, md5 in congelados.items():
        assert hashlib.md5((config.PROMPTS_DIR / nombre).read_bytes()).hexdigest() == md5, f"{nombre} cambió"


def test_en_el_ultimo_paso_el_agente_solo_puede_cerrar():
    """Caso fonda (8bc7e3c80fc5): el analista necesitaba 9 pasos y llegó al tope de 8 sin entregar."""
    from modulab.llm import LlamadaHerramienta, RespuestaLLM
    from modulab.loop import ejecutar_agente
    from modulab.tools import HERRAMIENTAS_ANALISTA
    from modulab.tracing import Trazador

    class SiempreBusca:
        nombre, modelo = "falso", "x"
        def __init__(self): self.ofrecidas = []
        def chat(self, system, mensajes, herramientas):
            nombres = [h["nombre"] for h in herramientas]
            self.ofrecidas.append(nombres)
            if "buscar_catalogo" in nombres:  # mientras pueda, sigue buscando
                return RespuestaLLM(texto=None, modelo="falso", llamadas=[LlamadaHerramienta(
                    id=f"b{len(self.ofrecidas)}", nombre="buscar_catalogo", args={"consulta": "fonda"})])
            return RespuestaLLM(texto=None, modelo="falso", llamadas=[LlamadaHerramienta(
                id="q", nombre="preguntar_al_dueno", args={"pregunta": "¿Qué te urge más?"})])

    falso = SiempreBusca()
    r = ejecutar_agente("analista", "s", [{"role": "user", "content": "fonda"}], HERRAMIENTAS_ANALISTA,
                        ClienteLLM([falso], usar_cache=False), Trazador(carpeta=config.OUTPUTS_DIR / "trazas_pruebas"), 8)
    assert r.terminal == "preguntar_al_dueno" and r.pasos == 8 and not r.agotado
    assert set(falso.ofrecidas[-1]) == {"preguntar_al_dueno", "entregar_propuesta"}
