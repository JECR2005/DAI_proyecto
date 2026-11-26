# Cambios de prompts y descripciones de herramientas

Cada entrada: fecha, prompt y versión, qué cambió, por qué y qué caso lo motivó.
Las versiones descartadas y su motivo van en docs/decisiones.md.

## 2026-11-25 · analista v1 y cotizador v1 (Jesús)
- Primera versión para la rebanada vertical con el caso de la estética infantil.
- El analista cierra su turno con dos herramientas terminales: `preguntar_al_dueno` y `entregar_propuesta`.
- Regla explícita de privacidad: nunca pedir datos de niños ni de sus papás (caso estética).
- El texto del dueño llega delimitado en `<mensaje_del_dueno>` y se trata como datos.

## 2026-11-26 · analista v2 (Jesús)
- Primera búsqueda con el nombre del giro para ver todos sus módulos típicos.
- No se puede descartar un módulo sin haber leído su ficha; el motivo sale de la ficha.
  Motivo: en la corrida real del 25 (traza e220347f93af) descartó Expediente de clientes
  "porque no manejas entregas a domicilio", sin haber buscado ese módulo.
- Si un módulo típico del giro podría servir y la información no alcanza (sobre todo cuando el
  presupuesto obliga a elegir), preguntar antes de entregar. Motivo: misma corrida, 0 preguntas;
  eligió Inventario sobre Expediente sin preguntar si anotan preferencias.
- Bloque `<perfil_guardado>` para clientes que regresan con su código NEG.
