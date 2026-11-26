# Decisiones y versiones descartadas

## 2026-11-25
- Bucle propio sobre llamadas a funciones nativas (sin LangGraph), según la ficha.
- Los agentes cierran turno con herramientas terminales (`preguntar_al_dueno`, `entregar_propuesta`, `entregar_cotizacion`) en lugar de texto libre: así el orquestador sabe qué pasó sin interpretar texto.
- Los precios y el total los arma el código desde el CSV; el modelo solo elige módulos.
- `buscar_catalogo` provisional por palabras exige al menos 2 palabras en común en consultas largas: con 1 sola, "programa de puntos" devolvía módulos sin relación.

## 2026-11-26
- Base de datos en SQL Server con un usuario propio de la app (`modulab_app`) que tiene `DENY UPDATE, DELETE` sobre `cotizaciones_emitidas`: la inmutabilidad la garantiza la base de datos, no el código.
- La contraseña de `modulab_app` la genera `sql/crear_base.py` y vive solo en `.env`.
- Confirmación: token de un solo uso ligado a la acción y al hash del contenido mostrado. La interfaz lo crea con `Orquestador.confirmar`; escribir "confirmo" no crea nada.
- `guardar_perfil` y `emitir_cotizacion` no se dan a los agentes: los ejecuta el orquestador.
- Cliente nuevo: el perfil se crea justo antes de emitir, para ligar la cotización a su código NEG.
- Guardrails con expresiones regulares antes del modelo; "guarda mis datos para la próxima vez" se permite, guardar instrucciones no.
- Descartada: analista v1 (ver CHANGELOG de prompts).

## 26-nov · Groq: cambio de modelo de respaldo
- `llama-3.3-70b-versatile` se dio de baja en Groq (16-ago-2026) y respondía 404. La traza lo mostró
  gracias al registro del respaldo. Se usa `openai/gpt-oss-120b`, el reemplazo que recomienda Groq.
