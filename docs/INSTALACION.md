# Instalar ModuLab en tu computadora

Guía paso a paso para Windows 10 u 11, con PowerShell. Toma unos 30 minutos la primera vez, casi todo en descargas. Al terminar tendrás las pruebas pasando, la demo de consola y la interfaz en Streamlit con la base de datos en SQL Server.

Si algo falla, busca el mensaje en [Problemas frecuentes](#problemas-frecuentes) al final.

## 1. Lo que necesitas instalar

| Programa | Para qué | Dónde |
| --- | --- | --- |
| Git | Descargar el repositorio y subir tus cambios | https://git-scm.com/download/win |
| Python 3.12 | Correr el sistema (es la versión con la que se probó) | https://www.python.org/downloads/ |
| SQL Server 2022 o 2025, edición **Developer** (gratuita) | La base de datos | https://www.microsoft.com/sql-server/sql-server-downloads |
| ODBC Driver 18 for SQL Server | Que Python hable con SQL Server | https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server |
| SQL Server Management Studio (SSMS), opcional | Ver las tablas y cambiar el modo de autenticación | https://learn.microsoft.com/sql/ssms/download-sql-server-management-studio-ssms |

Al instalar **Python**, marca la casilla **"Add python.exe to PATH"** en la primera pantalla.

Al instalar **SQL Server Developer**, elige la instalación **Básica**. Deja el nombre de instancia por defecto (`MSSQLSERVER`). Tu cuenta de Windows queda como administradora, y eso es lo que necesitan los scripts.

Comprueba en una ventana nueva de PowerShell:

```powershell
git --version
py -3.12 --version
```

## 2. Tus llaves de los modelos

Cada quien usa **sus propias llaves**. Son gratuitas, pero tienen cuota diaria. Nunca las pegues en el chat del equipo, en un commit ni en un documento.

- **Gemini** (modelo principal): entra a https://aistudio.google.com/apikey con tu cuenta de Google y presiona *Create API key*.
- **Groq** (respaldo cuando Gemini se queda sin cuota): crea una cuenta en https://console.groq.com y genera una llave en *API Keys*.

Guárdalas un momento en un lugar seguro. En el paso 5 van al archivo `.env`.

## 3. Descargar el repositorio

El repositorio es público, así que no necesitas permisos para clonarlo. Para subir cambios, pídele a Jesús que te agregue como colaborador.

```powershell
cd $HOME\Documents
git clone https://github.com/JECR2005/DAI_proyecto.git
cd DAI_proyecto
git checkout jesus/rebanada-estetica
```

Mientras el PR #2 no esté fusionado, la versión `v1.0` vive en la rama `jesus/rebanada-estetica`. Cuando se fusione, basta con quedarse en `main` (`git checkout main` y `git pull`).

## 4. Entorno de Python

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Al activar el entorno debe aparecer `(.venv)` al inicio de la línea. **Cada vez que abras una ventana nueva de PowerShell**, entra a la carpeta y vuelve a correr `.venv\Scripts\activate`. Casi todos los errores de "No module named…" vienen de olvidar este paso.

## 5. Archivo `.env`

```powershell
copy .env.example .env
notepad .env
```

Llena solo estas dos líneas con tus llaves y guarda:

```
GEMINI_API_KEY=tu_llave_de_gemini
GROQ_API_KEY=tu_llave_de_groq
```

No toques `MODULAB_DB_USER` ni `MODULAB_DB_PASSWORD`: los llena el script del paso 7. El `.env` ya está en `.gitignore`, así que Git nunca lo sube.

## 6. Primera prueba, sin base de datos

Esto comprueba que Python y las dependencias están bien antes de tocar SQL Server:

```powershell
python -m pytest -q
python -m modulab.demo --simulado --trazas
```

- Las pruebas deben pasar todas. Las de SQL Server se omiten (`skipped`) mientras no exista la base.
- La demo simulada recorre el caso de la estética completo sin red y sin base. Debe terminar con una cotización de $7,300.

## 7. Base de datos en SQL Server

Primero comprueba la conexión con tu cuenta de Windows:

```powershell
python sql\verificar_conexion.py
```

Debe decir:

- `Conectado a localhost con ODBC Driver 18 for SQL Server`
- `Autenticación: mixta (Windows y SQL Server)`. Si dice **solo Windows**, sigue el recuadro de abajo.
- `Tu usuario es administrador (sysadmin): sí`

> **Si la autenticación es "solo Windows":** abre SSMS y conéctate a `localhost` con *Windows Authentication*. Da clic derecho en el servidor, ve a *Properties*, luego a *Security*, y elige **SQL Server and Windows Authentication mode**. Acepta. Después reinicia el servicio: abre *Servicios* de Windows (`services.msc`), busca **SQL Server (MSSQLSERVER)** y elige *Reiniciar*. Vuelve a correr `verificar_conexion.py`.

Luego crea las bases y el usuario de la app:

```powershell
python sql\crear_base.py --reset-test
```

Debe terminar con estas dos líneas:

```
La app se conecta con su usuario limitado: OK
La app NO puede modificar cotizaciones emitidas (permiso denegado): OK
```

El script crea las bases `modulab` y `modulab_test` y el usuario `modulab_app`. Genera una contraseña nueva y la guarda solo en tu `.env`. Cada computadora tiene la suya: no la compartas ni la copies de otra máquina.

Vuelve a correr las pruebas. Ahora también corren las de SQL Server y no debe quedar ninguna omitida:

```powershell
python -m pytest -q
```

## 8. Correr el sistema

```powershell
python -m modulab.demo --guion --trazas     # caso de la estética con Gemini; la dueña responde sola
python -m modulab.demo                      # tú escribes como dueño (escribe "salir" para terminar)
python -m modulab.casos_dev                 # los 6 casos de desarrollo; deben pasar 6/6
streamlit run app.py                        # interfaz web en http://localhost:8501
```

- La primera vez que corres Streamlit te pide un correo. Déjalo vacío y presiona **Enter**.
- En la demo de consola, la cotización solo se emite si respondes `s` a la confirmación. En Streamlit, solo con el botón **Confirmar**. Para pruebas usa **Cancelar**, así no gastas folios.
- Para usar Groq como principal: `python -m modulab.demo --modelo groq --guion --trazas`.
- Para trabajar sin SQL Server: agrega `--memoria` a la demo, o pon `MODULAB_DB=memoria` en tu `.env` (Streamlit lo respeta).

Las salidas quedan en `outputs\<sesión>\` (configuración, maqueta, cotización) y las trazas en `outputs\trazas\*.jsonl`. La carpeta `outputs` no se sube a GitHub.

## 9. Cómo trabajar con el repositorio

```powershell
git checkout jesus/rebanada-estetica
git pull
git checkout -b carlos/validador          # una rama por tarea, con tu nombre
# ... cambios ...
python -m pytest -q                       # antes de cada commit
git add -A
git commit -m "Validador: V1–V3"
git push -u origin carlos/validador
```

Después abre un PR en GitHub hacia `jesus/rebanada-estetica` (o hacia `main`, si el PR #2 ya está fusionado) y pide la revisión a tu apoyo.

- **Prompts:** `analista_v2`, `cotizador_v2` y `configurador_v1` están congelados. `test_prompts_congelados` falla si cambias alguno.
- **Lo que te toca:** está en la sección *Pendientes del equipo* del README.

## Problemas frecuentes

| Mensaje | Causa | Solución |
| --- | --- | --- |
| `No module named 'pydantic'` (o cualquier módulo) | El entorno no está activado | `.venv\Scripts\activate` y vuelve a intentar |
| `...activate cannot be loaded because running scripts is disabled` | PowerShell bloquea los scripts | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, responde `S` y vuelve a activar |
| `py` no se reconoce | Python no está en el PATH | Reinstala Python marcando *Add python.exe to PATH* |
| `PermissionError: [WinError 5]` en pytest | Permisos de la carpeta temporal de Windows | Ya está resuelto en `pytest.ini`; corre pytest desde la carpeta del proyecto |
| `Data source name not found` / `IM002` | Falta el ODBC Driver 18 | Instálalo (tabla del paso 1) y abre una ventana nueva |
| `Login failed for user 'modulab_app'` | Autenticación solo Windows, o `.env` de otra máquina | Activa el modo mixto (paso 7) y vuelve a correr `crear_base.py` |
| `429 RESOURCE_EXHAUSTED` en la traza | Se acabó tu cuota diaria de Gemini | No es error: responde Groq. Es más lento; la cuota se renueva al día siguiente |
| `se usó el modelo de respaldo` en la traza | Gemini falló y respondió Groq | Normal; la traza dice el motivo |
| Streamlit pide un correo | Primer arranque | Presiona Enter |
| La maqueta no cambia después de actualizar el código | Streamlit conserva el código viejo en memoria | `Ctrl+C` y vuelve a correr `streamlit run app.py` |
