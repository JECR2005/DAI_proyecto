# ModuLab · Agentes Bond

Agente consultor que entrevista al dueño de un negocio, recomienda los módulos web que le convienen según su giro, presupuesto y dependencias, y emite la cotización. Caso principal (rebanada vertical): una estética infantil.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # y llena GEMINI_API_KEY y GROQ_API_KEY
```

## Correr la rebanada vertical

```bash
python -m modulab.demo --simulado --trazas   # sin red: verifica que el flujo completo funciona
python -m modulab.demo --guion --trazas      # caso de la estética con Gemini (respuestas de la dueña automáticas)
python -m modulab.demo                       # tú escribes como dueño
python -m pytest -q                          # pruebas sin modelo
```

Salidas en `outputs/<sesión>/` (config.json, maqueta.html, cotización borrador) y trazas en `outputs/trazas/*.jsonl`.

## Estado (mié 25 nov)

| Pieza | Responsable | Estado |
| --- | --- | --- |
| `schemas.py`, `config.py`, `llm.py`, `loop.py`, `orchestrator.py`, agentes, prompts v1 | Jesús | Listo; falta probar con Gemini y Groq reales |
| `resolver_dependencias`, `registrar_solicitud_especial` (en memoria) | Jesús | Listo |
| `leer_perfil`, `guardar_perfil`, `emitir_cotizacion`, `confirmation.py`, SQL Server | Jesús | Jue 26 |
| `buscar_catalogo` (búsqueda por palabras), `catalogo.json`, `precios.csv` | Gustavo | Provisionales: reemplazar por ChromaDB y datos oficiales sin cambiar firmas |
| `generar_configuracion`, `generar_cotizacion_pdf` | Gustavo | Stubs funcionales: reemplazar por Jinja2 y ReportLab |
| `validator.py`, `tracing.py` | Carlos | Provisionales: completar V1–V9 y visor |

## Uso de asistentes de IA

Se declara aquí y en el PDF final qué asistentes se usaron y para qué.
