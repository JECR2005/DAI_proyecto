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
streamlit run app.py                         # interfaz web: chat, maqueta y botón Confirmar
python -m modulab.demo --simulado --trazas   # sin red: verifica que el flujo completo funciona
python -m modulab.demo --guion --trazas      # caso de la estética con Gemini (respuestas de la dueña automáticas)
python -m modulab.demo                       # tú escribes como dueño
python -m modulab.casos_dev                   # 6 casos de desarrollo del analista (no emite nada)
python -m modulab.demo --memoria             # sin SQL Server (base en memoria)
python -m pytest -q                          # pruebas sin modelo (las de SQL Server se saltan si no hay base)
```

Salidas en `outputs/<sesión>/` (config.json, maqueta.html, cotización borrador) y trazas en `outputs/trazas/*.jsonl`.

## Estado (vie 27 nov · versión `v1.0`)

El desarrollo del área de agentes terminó el viernes 27 de noviembre con la versión [`v1.0`](https://github.com/JECR2005/DAI_proyecto/releases/tag/v1.0): 72 pruebas pasan y los 6 casos de desarrollo pasan con Gemini. El trabajo está en la rama `jesus/rebanada-estetica` y entra a `main` con el [PR #2](https://github.com/JECR2005/DAI_proyecto/pull/2).

| Pieza | Responsable | Estado |
| --- | --- | --- |
| Bucle, orquestador, `llm.py` (Gemini + Groq de respaldo) | Jesús | Listo |
| Analista (`analista_v2`), Cotizador (`cotizador_v2`), Configurador (`configurador_v1`) | Jesús | Listos; prompts congelados |
| SQL Server: `sql/schema.sql`, `crear_base.py`, `db.py` | Jesús | Listo; correr `crear_base.py` en cada máquina |
| Confirmación por token, emisión con folio y vigencia | Jesús | Listo |
| Perfil con código NEG, cliente que regresa | Jesús | Listo |
| Guardrails (inyección, precios, memoria, propósito) | Jesús | Listo |
| Casos de desarrollo (`python -m modulab.casos_dev`) | Jesús | 6/6 |
| `app.py` (Streamlit) | Gustavo | Versión funcional de Jesús; Gustavo puede rediseñarla conservando `responder`/`confirmar` |
| `buscar_catalogo`, catálogo, precios, maqueta, PDF | Gustavo | Provisionales funcionales: reemplazar sin cambiar firmas |
| `validator.py` V1–V9, casos y evaluación | Carlos | Pendiente |

### Para `app.py` (Gustavo)

```python
orq = Orquestador(ClienteLLM.desde_config(), ProveedorConfirmacion("ui"))
r = orq.responder(sesion, texto)          # Respuesta: tipo, texto, archivos, folio, codigo_negocio...
if r.requiere_confirmacion:               # mostrar botones Confirmar / Cancelar
    r = orq.confirmar(sesion, aprobado)   # único camino para emitir o sobrescribir
```

## Pendientes del equipo

Carlos y Gustavo empiezan ahora que salió `v1.0`. Marquen cada casilla al terminar en su propio commit. Las dudas van como comentario en el PR #2.

**Prompts congelados.** `analista_v2`, `cotizador_v2` y `configurador_v1` no se cambian antes de la evaluación final. `test_prompts_congelados` falla si alguno cambia. Cambiar uno exige versión nueva, su entrada en `modulab/prompts/CHANGELOG.md` y volver a correr los 6 casos de desarrollo.

### Carlos · evaluación, seguridad y documentación

Lo más urgente es el validador y los 40 casos: sin ellos no hay evaluación final.

- [ ] Revisar y aprobar el [PR #2](https://github.com/JECR2005/DAI_proyecto/pull/2), incluido el Configurador.
- [ ] Escribir el validador V1–V9 en `modulab/validator.py` (hoy devuelve una lista vacía). Las reglas de `revisar_coherencia` en `modulab/agents/analista.py` revisan la calidad de la entrevista y el presupuesto; no sustituyen al validador.
- [ ] Armar los 40 casos de evaluación (desarrollo y prueba) y correr la evaluación final con trazas. Los 6 casos de `modulab/casos_dev.py` sirven de ejemplo de formato, pero no cuentan como evaluación.
- [ ] Escribir el análisis de fallas. Cada falla real está en `modulab/prompts/CHANGELOG.md` con su traza, su corrección y su prueba:
    - `e220347f93af`: descartó Expediente con un motivo inventado.
    - `bb37bba1ea02`: sobrecorrección, solo Citas por $4,800 de $8,000.
    - COT-2026-0005: al cliente que regresa se le volvió a cobrar la base.
    - COT-2026-0007: $8,900 con un presupuesto de $8,000.
    - `1580ef1a1683`: el modelo de Groq dado de baja; el respaldo a Gemini no dejaba rastro.
    - `6399b1927af8` y `a3810526a3e4`: la fonda agotó el tope de 8 pasos.
    - `698928515145`: "sí cabe" sin contar dependencias.
    - `7424f2803d39`: el cotizador respondió vacío.
    - `97e3cd523c35`: propuestas escritas como texto contadas como preguntas.
    - `106c9257c74a`: la base fuera del presupuesto y un presupuesto inventado.
- [ ] Revisar la seguridad:
    - guardrails (inyección, precios, memoria, propósito);
    - escribir "confirmo" no emite nada;
    - el bloqueo tras 3 códigos falsos;
    - `DENY UPDATE, DELETE` sobre cotizaciones emitidas;
    - el Configurador no acepta precios ni módulos ajenos en la maqueta.
- [ ] Confirmar que no se guardan datos de los niños ni de los papás en ninguna tabla ni traza.
- [ ] Escribir la sección de evaluación y seguridad del PDF final; revisar este README y `docs/decisiones.md`.

### Gustavo · datos, RAG y plataforma web

El cambio principal es sustituir la búsqueda provisional por el RAG sin tocar a los agentes.

- [ ] Reemplazar la búsqueda léxica de `buscar_catalogo` (`modulab/tools/catalogo.py`) por el RAG, con los mismos argumentos y el mismo formato de salida (fichas con `doc_id`). Debe seguir devolviendo primero la ficha cuando la consulta trae el id de un módulo (`test_buscar_por_id_de_modulo_devuelve_su_ficha`).
- [ ] Comprobar en una traza que, para la estética, `buscar_catalogo` devuelve las fichas de Citas, Recordatorios, Expediente e Inventario.
- [ ] Revisar el corpus `data/corpus/` (10 casos, 2 por giro); la primera línea de cada caso lista los módulos que cita.
- [ ] Revisar `data/catalogo.json` y `data/precios.csv`: nombres, dependencias, giros y precios.
- [ ] Si reemplaza la maqueta o `generar_configuracion` (`modulab/tools/salidas.py`), conservar:
    - los campos que llena el Configurador (`bienvenida`, `secciones` con `id`, `titulo`, `texto`);
    - el rechazo de precios y de módulos ajenos;
    - los estilos propios que la hacen legible con el tema oscuro de Streamlit.

  Las pruebas de `tests/test_configurador.py` lo vigilan.
- [ ] Revisar `sql/schema.sql` y correr `sql/crear_base.py` en su máquina; confirmar folios `COT-AAAA-NNNN` y vigencia de 15 días.
- [ ] Revisar o rediseñar `app.py` conservando `responder` y `confirmar`.

### Ambos

- [ ] Instalar: crear `.venv`, `pip install -r requirements.txt` y copiar `.env.example` a `.env` con sus propias llaves. El `.env` nunca se sube a GitHub ni se comparte por chat.
- [ ] Correr `python -m pytest -q` (las pruebas de SQL Server se omiten si no hay base) y `python -m modulab.casos_dev`.
- [ ] Probar `python -m modulab.demo --guion --trazas` y `streamlit run app.py` con el caso de la estética.
- [ ] Revisar la descripción de la estética en `modulab/guion_estetica.py`: sin datos de los niños ni de los papás.
- [ ] Pasarle a Jesús su usuario de GitHub para asignarlos como revisores.

## Uso de asistentes de IA

Se declara aquí y en el PDF final qué asistentes se usaron y para qué.
