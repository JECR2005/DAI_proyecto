# ModuLab · Agentes Bond

Agente consultor que entrevista al dueño de un negocio, recomienda los módulos web que le convienen según su giro, presupuesto y dependencias, y emite la cotización. Caso principal (rebanada vertical): una estética infantil.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # y llena GEMINI_API_KEY y GROQ_API_KEY
```

## Base de datos (SQL Server)

```bash
python sql/verificar_conexion.py          # comprueba la conexión con tu cuenta de Windows
python sql/crear_base.py --reset-test     # crea modulab y modulab_test, el usuario modulab_app y sus permisos
```

`crear_base.py` genera la contraseña de `modulab_app` y la guarda solo en tu `.env`. La app no puede modificar ni borrar cotizaciones emitidas (`DENY UPDATE, DELETE`).

## Correr la rebanada vertical

```bash
python -m modulab.demo --simulado --trazas   # sin red: verifica que el flujo completo funciona
python -m modulab.demo --guion --trazas      # caso de la estética con Gemini (respuestas de la dueña automáticas)
python -m modulab.demo                       # tú escribes como dueño
python -m modulab.demo --memoria             # sin SQL Server (base en memoria)
python -m pytest -q                          # pruebas sin modelo (las de SQL Server se saltan si no hay base)
```

Salidas en `outputs/<sesión>/` (config.json, maqueta.html, cotización borrador) y trazas en `outputs/trazas/*.jsonl`.

## Estado (jue 26 nov)

| Pieza | Responsable | Estado |
| --- | --- | --- |
| Bucle, orquestador, analista (prompt v2), cotizador, `llm.py` | Jesús | Listo; probado con gemini-3.5-flash-lite |
| SQL Server: `sql/schema.sql`, `crear_base.py`, `db.py` | Jesús | Listo; correr `crear_base.py` en cada máquina |
| Confirmación por token, `emitir_cotizacion` con folio y vigencia | Jesús | Listo |
| Perfil con código NEG, cliente que regresa, sobrescritura confirmada | Jesús | Listo |
| Guardrails (inyección, precios, memoria, propósito) | Jesús | Listo |
| `buscar_catalogo`, catálogo, precios, maqueta, PDF, `app.py` | Gustavo | Provisionales funcionales: reemplazar sin cambiar firmas |
| `validator.py` V1–V9, `tracing.py`, casos y evaluación | Carlos | Provisionales: completar |

### Para `app.py` (Gustavo)

```python
orq = Orquestador(ClienteLLM.desde_config(), ProveedorConfirmacion("ui"))
r = orq.responder(sesion, texto)          # Respuesta: tipo, texto, archivos, folio, codigo_negocio...
if r.requiere_confirmacion:               # mostrar botones Confirmar / Cancelar
    r = orq.confirmar(sesion, aprobado)   # único camino para emitir o sobrescribir
```

## Uso de asistentes de IA

Se declara aquí y en el PDF final qué asistentes se usaron y para qué.
