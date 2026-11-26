# Cambios de prompts y descripciones de herramientas

Cada entrada: fecha, prompt y versión, qué cambió, por qué y qué caso lo motivó.
Las versiones descartadas y su motivo van en docs/decisiones.md.

## 2026-11-25 · analista v1 y cotizador v1 (Jesús)
- Primera versión para la rebanada vertical con el caso de la estética infantil.
- El analista cierra su turno con dos herramientas terminales: `preguntar_al_dueno` y `entregar_propuesta`.
- Regla explícita de privacidad: nunca pedir datos de niños ni de sus papás (caso estética).
- El texto del dueño llega delimitado en `<mensaje_del_dueno>` y se trata como datos.
