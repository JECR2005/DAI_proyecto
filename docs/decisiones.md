# Decisiones y versiones descartadas

## 2026-11-25
- Bucle propio sobre llamadas a funciones nativas (sin LangGraph), según la ficha.
- Los agentes cierran turno con herramientas terminales (`preguntar_al_dueno`, `entregar_propuesta`, `entregar_cotizacion`) en lugar de texto libre: así el orquestador sabe qué pasó sin interpretar texto.
- Los precios y el total los arma el código desde el CSV; el modelo solo elige módulos.
- `buscar_catalogo` provisional por palabras exige al menos 2 palabras en común en consultas largas: con 1 sola, "programa de puntos" devolvía módulos sin relación.
