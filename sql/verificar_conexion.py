"""Comprueba la conexión a SQL Server con la configuración del .env.

    python sql/verificar_conexion.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modulab import config  # noqa: E402

try:
    import pyodbc
except ImportError:
    sys.exit("Falta pyodbc: pip install pyodbc")

drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
print("Drivers ODBC:", drivers)
driver = "ODBC Driver 18 for SQL Server" if "ODBC Driver 18 for SQL Server" in drivers else drivers[-1]

if config.DB_USER:
    auth = f"UID={config.DB_USER};PWD={config.DB_PASSWORD}"
else:
    auth = "Trusted_Connection=yes"
cadena = f"DRIVER={{{driver}}};SERVER={config.DB_SERVER};{auth};TrustServerCertificate=yes;Encrypt=yes"

try:
    con = pyodbc.connect(cadena, timeout=5)
except pyodbc.Error as e:
    sys.exit(f"No se pudo conectar a {config.DB_SERVER}: {e}")

fila = con.execute("""
    SELECT CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(50)),
           CAST(SERVERPROPERTY('Edition') AS nvarchar(100)),
           CAST(SERVERPROPERTY('IsIntegratedSecurityOnly') AS int),
           IS_SRVROLEMEMBER('sysadmin'),
           DB_ID('modulab')
""").fetchone()
print(f"Conectado a {config.DB_SERVER} con {driver}")
print(f"Versión: {fila[0]} · Edición: {fila[1]}")
print("Autenticación:", "solo Windows" if fila[2] == 1 else "mixta (Windows y SQL Server)")
print("Tu usuario es administrador (sysadmin):", "sí" if fila[3] == 1 else "no")
print("Base 'modulab':", "ya existe" if fila[4] else "todavía no existe (se crea con sql/crear_base.py)")
