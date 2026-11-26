"""Configuración única del proyecto: todo lo ajustable vive aquí o en .env."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv es opcional
    load_dotenv = None

RAIZ = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(RAIZ / ".env")


def _env(nombre: str, defecto: str = "") -> str:
    return os.getenv(nombre, defecto).strip()


# --- Modelos -------------------------------------------------------------
# MODELO: "gemini", "groq" o "simulado" (sin red, para pruebas y depuración).
MODELO = _env("MODELO", "gemini")
# Verifiquen el nombre exacto disponible en su cuenta antes de usarlo.
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-3.5-flash-lite")
GROQ_MODEL = _env("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GROQ_API_KEY = _env("GROQ_API_KEY")
TEMPERATURA = 0.0
REINTENTOS_POR_PROVEEDOR = int(_env("REINTENTOS_POR_PROVEEDOR", "2"))
USAR_CACHE = _env("USAR_CACHE", "1") == "1"

# --- Topes del ciclo (ficha, sección 6) ----------------------------------
MAX_PASOS_POR_TURNO = 8
MAX_PREGUNTAS = 6
MAX_REINTENTOS_VALIDADOR = 2

# --- Reglas comerciales ---------------------------------------------------
MODULOS_BASE = ["M01", "M02", "M03"]
VIGENCIA_DIAS = 15
FORMATO_FOLIO = "COT-{anio}-{numero:04d}"

# --- Rutas ------------------------------------------------------------------
DATA_DIR = RAIZ / "data"
CATALOGO_PATH = DATA_DIR / "catalogo.json"
PRECIOS_PATH = DATA_DIR / "precios.csv"
CORPUS_DIR = DATA_DIR / "corpus"
PROMPTS_DIR = RAIZ / "modulab" / "prompts"
OUTPUTS_DIR = RAIZ / "outputs"
TRAZAS_DIR = OUTPUTS_DIR / "trazas"
CACHE_DIR = RAIZ / ".cache_llm"

# --- SQL Server (se usa desde el jue 26) -----------------------------------
DB_SERVER = _env("MODULAB_DB_SERVER", "localhost")
DB_NAME = _env("MODULAB_DB_NAME", "modulab")
DB_USER = _env("MODULAB_DB_USER")
DB_PASSWORD = _env("MODULAB_DB_PASSWORD")
