"""Acceso a datos: SQL Server (real) y memoria (pruebas y demo simulada).

Todo el código habla con un `Repositorio`; nadie más escribe SQL. Las
consultas van siempre parametrizadas: el texto del dueño nunca se concatena.

    repo = db.repositorio()            # según MODULAB_DB en .env: sqlserver | memoria
"""
from __future__ import annotations

import json
import secrets
import string
import threading
from datetime import date, datetime, timedelta
from typing import Optional, Protocol

from . import config
from .schemas import Perfil

_ALFABETO = string.ascii_uppercase + string.digits


def nuevo_codigo() -> str:
    return "NEG-" + "".join(secrets.choice(_ALFABETO) for _ in range(5))


def formatear_folio(numero: int, anio: Optional[int] = None) -> str:
    return config.FORMATO_FOLIO.format(anio=anio or date.today().year, numero=numero)


class ErrorPermiso(Exception):
    """La base de datos rechazó la operación por permisos (lo esperado al intentar
    modificar o borrar una cotización emitida)."""


class Repositorio(Protocol):
    def leer_perfil(self, codigo: str) -> Optional[Perfil]: ...
    def crear_perfil(self, perfil: Perfil) -> str: ...
    def sobrescribir_perfil(self, perfil: Perfil) -> None: ...
    def registrar_solicitud(self, descripcion: str, giro: Optional[str], sesion: Optional[str],
                            codigo_negocio: Optional[str]) -> int: ...
    def emitir_cotizacion(self, modulos: list[str], total: float, hash_contenido: str,
                          codigo_negocio: Optional[str]) -> dict: ...
    def cotizaciones(self) -> list[dict]: ...
    def guardar_mensaje(self, sesion: str, rol: str, contenido: str, codigo_negocio: Optional[str] = None) -> None: ...


# ------------------------------------------------------------------ memoria
class RepositorioMemoria:
    """Mismo comportamiento que SQL Server, sin base de datos. Para pruebas y la demo simulada."""

    def __init__(self):
        self._lock = threading.Lock()
        self.perfiles: dict[str, Perfil] = {}
        self.historial: list[dict] = []
        self.solicitudes: list[dict] = []
        self._cotizaciones: list[dict] = []
        self.mensajes: list[dict] = []
        self._folio = 0

    def leer_perfil(self, codigo):
        p = self.perfiles.get(codigo.strip().upper())
        return p.model_copy(deep=True) if p else None

    def crear_perfil(self, perfil):
        with self._lock:
            codigo = nuevo_codigo()
            while codigo in self.perfiles:
                codigo = nuevo_codigo()
            self.perfiles[codigo] = perfil.model_copy(update={"codigo_negocio": codigo}, deep=True)
            return codigo

    def sobrescribir_perfil(self, perfil):
        with self._lock:
            anterior = self.perfiles[perfil.codigo_negocio]
            self.historial.append({"codigo_negocio": perfil.codigo_negocio, "perfil": anterior.model_dump()})
            self.perfiles[perfil.codigo_negocio] = perfil.model_copy(deep=True)

    def registrar_solicitud(self, descripcion, giro, sesion, codigo_negocio):
        with self._lock:
            self.solicitudes.append({"id": len(self.solicitudes) + 1, "descripcion": descripcion, "giro": giro,
                                     "sesion": sesion, "codigo_negocio": codigo_negocio})
            return len(self.solicitudes)

    def emitir_cotizacion(self, modulos, total, hash_contenido, codigo_negocio):
        with self._lock:
            self._folio += 1
            hoy = datetime.now()
            fila = {"folio": formatear_folio(self._folio, hoy.year), "codigo_negocio": codigo_negocio,
                    "fecha": hoy.isoformat(timespec="seconds"),
                    "vigencia": (hoy.date() + timedelta(days=config.VIGENCIA_DIAS)).isoformat(),
                    "modulos": list(modulos), "total": float(total), "hash_contenido": hash_contenido,
                    "estado": "emitida"}
            self._cotizaciones.append(fila)
            return dict(fila)

    def cotizaciones(self):
        return [dict(c) for c in self._cotizaciones]

    def modificar_cotizacion(self, folio, **cambios):
        raise ErrorPermiso("Las cotizaciones emitidas no se pueden modificar.")

    def guardar_mensaje(self, sesion, rol, contenido, codigo_negocio=None):
        self.mensajes.append({"sesion": sesion, "rol": rol, "contenido": contenido, "codigo_negocio": codigo_negocio})


# ------------------------------------------------------------------ SQL Server
def cadena_conexion(base: Optional[str] = None, admin: bool = False) -> str:
    import pyodbc
    drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
    driver = "ODBC Driver 18 for SQL Server" if "ODBC Driver 18 for SQL Server" in drivers else (drivers or ["SQL Server"])[-1]
    if admin or not config.DB_USER:
        auth = "Trusted_Connection=yes"  # cuenta de Windows (administrador local)
    else:
        auth = f"UID={config.DB_USER};PWD={{{config.DB_PASSWORD}}}"
    base = base or config.DB_NAME
    return (f"DRIVER={{{driver}}};SERVER={config.DB_SERVER};DATABASE={base};{auth};"
            "Encrypt=yes;TrustServerCertificate=yes")


def conectar(base: Optional[str] = None, admin: bool = False, autocommit: bool = False):
    import pyodbc
    return pyodbc.connect(cadena_conexion(base, admin), autocommit=autocommit, timeout=5)


def _es_permiso(e: Exception) -> bool:
    texto = str(e)
    return "229" in texto or "permission was denied" in texto.lower() or "permiso" in texto.lower()


class RepositorioSQLServer:
    def __init__(self, base: Optional[str] = None):
        self.base = base or config.DB_NAME
        self._local = threading.local()

    def _con(self):
        con = getattr(self._local, "con", None)
        if con is None:
            con = conectar(self.base)
            self._local.con = con
        return con

    def _ejecutar(self, sql: str, *params, commit: bool = True):
        con = self._con()
        cur = con.cursor()
        try:
            cur.execute(sql, *params)
            filas = cur.fetchall() if cur.description else None
            if commit:
                con.commit()
            return filas
        except Exception as e:
            con.rollback()
            if _es_permiso(e):
                raise ErrorPermiso(str(e)) from e
            raise

    @staticmethod
    def _perfil(fila) -> Perfil:
        return Perfil(codigo_negocio=fila[0], giro=fila[1], tamano=fila[2],
                      presupuesto=float(fila[3]) if fila[3] is not None else None,
                      necesidades=json.loads(fila[4]), modulos_previos=json.loads(fila[5]),
                      notas_no_confiables=fila[6])

    def leer_perfil(self, codigo):
        filas = self._ejecutar(
            "SELECT codigo_negocio, giro, tamano, presupuesto, necesidades, modulos_previos, notas_no_confiables "
            "FROM dbo.perfiles WHERE codigo_negocio = ?", codigo.strip().upper(), commit=False)
        return self._perfil(filas[0]) if filas else None

    def crear_perfil(self, perfil):
        for _ in range(5):
            codigo = nuevo_codigo()
            try:
                self._ejecutar(
                    "INSERT INTO dbo.perfiles (codigo_negocio, giro, tamano, presupuesto, necesidades, "
                    "modulos_previos, notas_no_confiables) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    codigo, perfil.giro, perfil.tamano, perfil.presupuesto,
                    json.dumps(perfil.necesidades, ensure_ascii=False),
                    json.dumps(perfil.modulos_previos, ensure_ascii=False), perfil.notas_no_confiables)
                return codigo
            except ErrorPermiso:
                raise
            except Exception as e:  # código repetido (muy improbable): se intenta otro
                if "PRIMARY KEY" not in str(e) and "2627" not in str(e):
                    raise
        raise RuntimeError("No se pudo generar un código de negocio único.")

    def sobrescribir_perfil(self, perfil):
        anterior = self.leer_perfil(perfil.codigo_negocio)
        con = self._con()
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO dbo.perfiles_historial (codigo_negocio, perfil_json) VALUES (?, ?)",
                        perfil.codigo_negocio, anterior.model_dump_json())
            cur.execute(
                "UPDATE dbo.perfiles SET giro = ?, tamano = ?, presupuesto = ?, necesidades = ?, modulos_previos = ?, "
                "notas_no_confiables = ?, actualizado = SYSDATETIME() WHERE codigo_negocio = ?",
                perfil.giro, perfil.tamano, perfil.presupuesto, json.dumps(perfil.necesidades, ensure_ascii=False),
                json.dumps(perfil.modulos_previos, ensure_ascii=False), perfil.notas_no_confiables,
                perfil.codigo_negocio)
            con.commit()
        except Exception:
            con.rollback()
            raise

    def registrar_solicitud(self, descripcion, giro, sesion, codigo_negocio):
        filas = self._ejecutar(
            "INSERT INTO dbo.solicitudes_especiales (descripcion, giro, sesion, codigo_negocio) "
            "OUTPUT INSERTED.id VALUES (?, ?, ?, ?)", descripcion[:500], giro, sesion, codigo_negocio)
        return int(filas[0][0])

    def emitir_cotizacion(self, modulos, total, hash_contenido, codigo_negocio):
        con = self._con()
        cur = con.cursor()
        try:
            numero = cur.execute("SELECT NEXT VALUE FOR dbo.seq_folios").fetchone()[0]
            hoy = datetime.now()
            folio = formatear_folio(int(numero), hoy.year)
            vigencia = hoy.date() + timedelta(days=config.VIGENCIA_DIAS)
            cur.execute(
                "INSERT INTO dbo.cotizaciones_emitidas (folio, codigo_negocio, vigencia, modulos, total, hash_contenido) "
                "VALUES (?, ?, ?, ?, ?, ?)", folio, codigo_negocio, vigencia,
                json.dumps(list(modulos)), total, hash_contenido)
            con.commit()
        except Exception as e:
            con.rollback()
            if _es_permiso(e):
                raise ErrorPermiso(str(e)) from e
            raise
        return {"folio": folio, "codigo_negocio": codigo_negocio, "fecha": hoy.isoformat(timespec="seconds"),
                "vigencia": vigencia.isoformat(), "modulos": list(modulos), "total": float(total),
                "hash_contenido": hash_contenido, "estado": "emitida"}

    def cotizaciones(self):
        filas = self._ejecutar("SELECT folio, codigo_negocio, fecha, vigencia, modulos, total, estado "
                               "FROM dbo.cotizaciones_emitidas ORDER BY fecha", commit=False) or []
        return [{"folio": f[0], "codigo_negocio": f[1], "fecha": str(f[2]), "vigencia": str(f[3]),
                 "modulos": json.loads(f[4]), "total": float(f[5]), "estado": f[6]} for f in filas]

    def modificar_cotizacion(self, folio, **cambios):
        """Solo existe para demostrar que el permiso está negado: siempre debe fallar."""
        self._ejecutar("UPDATE dbo.cotizaciones_emitidas SET total = total WHERE folio = ?", folio)

    def guardar_mensaje(self, sesion, rol, contenido, codigo_negocio=None):
        self._ejecutar("INSERT INTO dbo.conversaciones (sesion, codigo_negocio, rol, contenido) VALUES (?, ?, ?, ?)",
                       sesion, codigo_negocio, rol, contenido)


# ------------------------------------------------------------------ fábrica
_REPO: Optional[Repositorio] = None


def repositorio() -> Repositorio:
    global _REPO
    if _REPO is None:
        _REPO = RepositorioSQLServer() if config.BASE_DATOS == "sqlserver" else RepositorioMemoria()
    return _REPO


def usar(repo: Repositorio) -> None:
    """Fija el repositorio (pruebas, demo simulada)."""
    global _REPO
    _REPO = repo
