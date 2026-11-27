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

## 26-nov (noche) · sin cambio de prompt; correcciones en código por los casos de desarrollo
- Primera corrida de `python -m modulab.casos_dev` (Gemini): 3/6. Las tres fallas eran de código, no de prompt:
  - fonda (`6399b1927af8`): `buscar_catalogo` no devolvía la ficha al buscar por id ("M10") y el analista
    agotó los 8 pasos. Ahora un id en la consulta trae su ficha primero.
  - presupuesto bajo (`698928515145`): la regla "sí cabe" no contaba dependencias (M05 requiere M04) y empujó
    al modelo a pasarse a $5,800 de $4,000. Ahora el costo incluye lo que el módulo requiere.
  - estética (`7424f2803d39`): el cotizador respondió vacío y la conversación terminó en error. Ahora se le
    pide cerrar con `entregar_cotizacion` en lugar de terminar.
- Segunda corrida: 4/6. En estética y presupuesto bajo, al pasarse del presupuesto el analista recortó por su
  cuenta (quitó Recordatorios, que la dueña sí pidió) o entregó excedido. Ahora, la primera vez que se pasa,
  el orquestador le pide preguntarle a la dueña qué deja fuera o si puede gastar más (una vez por sesión).
- Tercera corrida: los 2 casos pasan, pero presupuesto bajo (`97e3cd523c35`) llegó a 6 preguntas porque 4 eran
  la propuesta escrita como texto. El analista ya no cierra su turno con texto suelto: pregunta con
  `preguntar_al_dueno` y entrega con `entregar_propuesta`, igual que el cotizador.

## 27-nov · sin cambio de prompt; correcciones en código por los casos de desarrollo
- Corrida del 26-nov 19:14: 4/6.
  - presupuesto bajo (`106c9257c74a`): el modelo no contaba la base ($3,000) dentro del presupuesto y, atrapado
    entre "no te pases" y "no quites lo que pidió", inventó un presupuesto de $4,800. Ahora el revisor dice cuánto
    queda después de la base, permite dejar fuera lo que no cabe aunque se haya pedido, y rechaza un presupuesto
    que el dueño no escribió.
  - fonda (`a7f1a716f23e`): el agente cerró tras una pregunta y nunca oyó la app de repartidores, que venía en el
    tercer mensaje del guion. Se corrigió el guion (la petición va en el primer mensaje), no el agente.

## 27-nov 14:30 · PROMPTS CONGELADOS
- `analista_v2.md` (md5 31ff3f07…) y `cotizador_v1.md` (md5 573af3e4…) quedan congelados tras 6/6 casos de
  desarrollo (`outputs/casos_dev/20261127_1423_gemini.json`). No cambian antes de la evaluación final de Carlos.
- `tests/test_rebanada.py::test_prompts_congelados` falla si se modifican. Cambiarlos exige una versión nueva
  (v3), su entrada aquí y volver a correr los 6 casos.

## 27-nov · rama `jesus/configurador`: Configurador como tercer agente
- `cotizador_v2.md`: igual a v1 sin el paso de configuración (v1 queda congelado e intacto).
- `configurador_v1.md`: nuevo. Adapta bienvenida, títulos, textos y orden de la maqueta al giro.
  El código rechaza secciones de módulos que el sitio no tendrá y cualquier precio en los textos;
  si el Configurador no entrega, se genera la maqueta genérica y queda en la traza.
- Entra a `v1.0` solo si pasan las pruebas y los 6 casos de desarrollo con el modelo real.
- Corrida 14:31 en la rama: 5/6. La fonda (`8bc7e3c80fc5`) necesitó 9 pasos y llegó al tope de 8 sin entregar
  (no era del Configurador; en la corrida anterior pasó de suerte). Se mantiene el tope de 8: en el último paso
  el agente solo recibe sus herramientas de cierre (preguntar o entregar), así el turno siempre termina.
- Corrida 14:36: 5/6. Fonda (`a3810526a3e4`): en el paso 8 Gemini llamó una herramienta que no se le ofreció.
  Ahora el bucle no la ejecuta, y si el analista agota sus 8 pasos el orquestador le da una sola vuelta más
  (otros 8) con la instrucción de entregar o preguntar. Cada vuelta respeta el tope.
