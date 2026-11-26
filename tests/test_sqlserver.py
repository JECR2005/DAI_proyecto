"""Integración con SQL Server real (base modulab_test).

Se salta si no hay SQL Server configurado. En tu computadora:
    python sql/crear_base.py --reset-test
    python -m pytest -q tests/test_sqlserver.py
"""
import pytest

from modulab import config, db
from modulab.schemas import Perfil


def _repo():
    try:
        import pyodbc  # noqa: F401
        if not config.DB_USER:
            pytest.skip("Sin usuario de la app en .env: corre sql/crear_base.py")
        repo = db.RepositorioSQLServer(base=f"{config.DB_NAME}_test")
        repo.cotizaciones()
        return repo
    except pytest.skip.Exception:
        raise
    except Exception as e:
        pytest.skip(f"SQL Server no disponible: {e}")


@pytest.fixture(scope="module")
def repo():
    return _repo()


def test_perfil_crear_leer_y_sobrescribir_con_historial(repo):
    codigo = repo.crear_perfil(Perfil(giro="estética infantil", presupuesto=8000, modulos_previos=["M04"],
                                      notas_no_confiables="dos estilistas"))
    leido = repo.leer_perfil(codigo.lower())
    assert leido.giro == "estética infantil" and leido.modulos_previos == ["M04"]
    leido.modulos_previos = ["M04", "M07"]
    repo.sobrescribir_perfil(leido)
    assert repo.leer_perfil(codigo).modulos_previos == ["M04", "M07"]


def test_emitir_da_folios_consecutivos(repo):
    a = repo.emitir_cotizacion(["M04"], 4800, "a" * 64, None)
    b = repo.emitir_cotizacion(["M05"], 4000, "b" * 64, None)
    assert a["folio"].startswith("COT-") and int(b["folio"][-4:]) == int(a["folio"][-4:]) + 1


def test_la_app_no_puede_modificar_cotizaciones(repo):
    folio = repo.emitir_cotizacion(["M04"], 4800, "c" * 64, None)["folio"]
    with pytest.raises(db.ErrorPermiso):
        repo.modificar_cotizacion(folio)


def test_solicitud_especial_y_mensajes(repo):
    assert repo.registrar_solicitud("Programa de puntos", "estética infantil", "s", None) > 0
    repo.guardar_mensaje("s", "dueno", "hola")
