"""Crea (o actualiza) las bases modulab y modulab_test, el usuario de la app y sus permisos.

    python sql/crear_base.py               # crea todo; se puede correr varias veces
    python sql/crear_base.py --reset-test  # además deja vacía modulab_test

Se conecta con tu cuenta de Windows (debes ser administrador de SQL Server).
La contraseña del usuario de la app se genera al azar y se guarda SOLO en tu
.env (MODULAB_DB_USER / MODULAB_DB_PASSWORD); nunca se imprime ni se sube al repo.
"""
from __future__ import annotations

import argparse
import re
import secrets
import string
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from modulab import config  # noqa: E402

APP_USER = "modulab_app"


def _contrasena() -> str:
    # Cumple la política de contraseñas de SQL Server y evita caracteres que estorban en cadenas ODBC.
    simbolos = "!#%*+-=?@^_"
    base = [secrets.choice(string.ascii_uppercase), secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits), secrets.choice(simbolos)]
    base += [secrets.choice(string.ascii_letters + string.digits + simbolos) for _ in range(20)]
    secrets.SystemRandom().shuffle(base)
    return "".join(base)


def _guardar_en_env(usuario: str, contrasena: str) -> None:
    ruta = RAIZ / ".env"
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    valores = {"MODULAB_DB_USER": usuario, "MODULAB_DB_PASSWORD": contrasena}
    vistos = set()
    for i, linea in enumerate(lineas):
        clave = linea.split("=", 1)[0].strip()
        if clave in valores:
            lineas[i] = f"{clave}={valores[clave]}"
            vistos.add(clave)
    lineas += [f"{k}={v}" for k, v in valores.items() if k not in vistos]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def _lotes(sql: str) -> list[str]:
    return [b.strip() for b in re.split(r"^\s*GO\s*$", sql, flags=re.MULTILINE | re.IGNORECASE) if b.strip()]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--reset-test", action="store_true")
    a = p.parse_args()

    try:
        import pyodbc
    except ImportError:
        sys.exit("Falta pyodbc: pip install pyodbc")
    from modulab.db import conectar

    contrasena = config.DB_PASSWORD if config.DB_USER == APP_USER and config.DB_PASSWORD else _contrasena()
    literal = contrasena.replace("'", "''")

    master = conectar("master", admin=True, autocommit=True)
    cur = master.cursor()
    existe = cur.execute("SELECT 1 FROM sys.server_principals WHERE name = ?", APP_USER).fetchone()
    if existe:
        cur.execute(f"ALTER LOGIN [{APP_USER}] WITH PASSWORD = N'{literal}', CHECK_EXPIRATION = OFF")
    else:
        cur.execute(f"CREATE LOGIN [{APP_USER}] WITH PASSWORD = N'{literal}', CHECK_POLICY = ON, "
                    "CHECK_EXPIRATION = OFF")
    print(f"Login {APP_USER}: {'actualizado' if existe else 'creado'}")
    _guardar_en_env(APP_USER, contrasena)
    print("Usuario y contraseña de la app guardados en .env")

    esquema = (RAIZ / "sql" / "schema.sql").read_text(encoding="utf-8").replace("{APP_USER}", APP_USER)
    for base in (config.DB_NAME, f"{config.DB_NAME}_test"):
        if not cur.execute("SELECT DB_ID(?)", base).fetchone()[0]:
            cur.execute(f"CREATE DATABASE [{base}]")
            print(f"Base {base}: creada")
        else:
            print(f"Base {base}: ya existía")
        con = conectar(base, admin=True, autocommit=True)
        c = con.cursor()
        if not c.execute("SELECT 1 FROM sys.database_principals WHERE name = ?", APP_USER).fetchone():
            c.execute(f"CREATE USER [{APP_USER}] FOR LOGIN [{APP_USER}]")
        for lote in _lotes(esquema):
            c.execute(lote)
        if a.reset_test and base.endswith("_test"):
            for lote in _lotes((RAIZ / "sql" / "reset_test.sql").read_text(encoding="utf-8")):
                c.execute(lote)
            print(f"Base {base}: vaciada")
        con.close()
        print(f"Base {base}: esquema y permisos aplicados")
    master.close()

    # Verificación con el usuario de la app (relee .env con los valores nuevos)
    config.DB_USER, config.DB_PASSWORD = APP_USER, contrasena
    con = conectar(config.DB_NAME)
    con.cursor().execute("SELECT COUNT(*) FROM dbo.perfiles").fetchone()
    print("La app se conecta con su usuario limitado: OK")
    try:
        con.cursor().execute("UPDATE dbo.cotizaciones_emitidas SET total = total WHERE 1 = 0")
        con.commit()
        print("ATENCIÓN: la app pudo hacer UPDATE en cotizaciones_emitidas; revisa los permisos.")
        return 1
    except pyodbc.Error:
        con.rollback()
        print("La app NO puede modificar cotizaciones emitidas (permiso denegado): OK")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
