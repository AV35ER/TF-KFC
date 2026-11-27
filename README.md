# TF-KFC

## Analizador de Pedidos KFC

Proyecto de Teoría de la Computación (USIL). Aplicación web en Flask que:

1. Muestra el enunciado del proyecto.
2. Recibe el lenguaje inicial (digitado o subiendo un `.txt`).
3. Genera los **TOKENS** y **LEXEMAS** (PRODUCTO, CANTIDAD, PAGO).
4. Genera la **Expresión Regular** de cada lexema.
5. Construye el **AFND** (método de Thompson).
6. Lo convierte a **AFD** (construcción de subconjuntos).
7. Muestra la **tabla de transiciones**.
8. Lista las **transiciones** δ.
9. Muestra la **quíntupla** M = (Q, Σ, δ, q0, F).
10. Valida cada pedido con un **analizador sintáctico LR (SLR)**: gramática, tabla LR, pasos del análisis, derivación y **árbol sintáctico**.
11. Transpila los pedidos aceptados a SQL demostrativo desde el AST y permite descargar un **reporte PDF A4**.

Los gráficos de los autómatas se generan desde el código (lenguaje DOT) y se dibujan en el navegador con viz.js.
La salida SQL es una representación académica; no se ejecuta y no se conecta al POS, a la cocina ni a bases de datos o sistemas internos de KFC.

## Archivos

- `app.py` — servidor Flask (rutas y formulario)
- `automatas.py` — análisis léxico, ER, AFND, AFD, tabla y quíntupla
- `sintactico.py` — gramática, colección LR(0), tabla SLR, análisis LR y árbol sintáctico
- `traductor.py` — transpilación segura desde el AST aceptado a SQL demostrativo
- `reporte_pdf.py` — generación del reporte descargable en formato A4
- `pruebas/test_traduccion_pdf.py` — pruebas de traducción, seguridad e integridad PDF
- `pruebas/analizador-kfc.postman_collection.json` — 20 casos de prueba automatizados (Postman / Newman)
- `templates/index.html` — interfaz
- `static/estilos.css` — estilos
- `ejemplo.txt` — archivo de prueba

## Ejecutar en local

En Windows PowerShell, crea un entorno virtual e instala las dependencias de la aplicación:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Abrir http://127.0.0.1:8080

## Publicar en Render

El Blueprint usa `runtime: docker` y construye la imagen desde `Dockerfile`. En Render, importa este repositorio y aplica el Blueprint de `render.yaml`; no configures comandos de build o inicio adicionales. El contenedor inicia Gunicorn y escucha en el puerto indicado por `PORT`.

## Pruebas automatizadas (Postman / Newman)

```
npx newman run pruebas/analizador-kfc.postman_collection.json
```

La API `POST /api/analizar` recibe `{"texto": "POLLO 2 EFECTIVO"}` y devuelve lexemas, tokens, expresiones regulares, AFD y validez de cada pedido.

La suite de traducción y PDF se ejecuta con:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m unittest pruebas.test_validacion_tecnica pruebas.test_traduccion_pdf -v
```

## Pruebas E2E de interfaz (Playwright)

La suite `pruebas/test_interfaz_e2e.cjs` recorre escritorio (1440×900 y 1366×768) y móvil (390×844 y 360×800), valida formularios, errores, reemplazo de resultados, TXT, gráficos, tabla SLR y descargas. Produce `pruebas/reporte-e2e-ui.json` y capturas en `pruebas/evidencias/`. Playwright y Chromium se mantienen en `.tools/e2e`, sin agregarse a las dependencias de producción.

En PowerShell, inicia Flask en una terminal:

```powershell
.\.venv\Scripts\python.exe -c "import app; app.app.run(host='127.0.0.1', port=8080, debug=False)"
```

En otra terminal, ejecuta la suite:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path (Resolve-Path '.tools\e2e').Path 'browsers')
node pruebas\test_interfaz_e2e.cjs
```

Para preparar el entorno local de pruebas por primera vez (requiere Node.js y npm):

```powershell
npm.cmd install --prefix .tools\e2e playwright
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path (Resolve-Path '.tools\e2e').Path 'browsers')
& '.tools\e2e\node_modules\.bin\playwright.cmd' install chromium
```

## Ejecutar con Docker

Docker no es necesario para ejecutar la aplicación; proporciona un entorno aislado y repetible. Con Docker Engine y Docker Compose instalados:

    docker compose up --build

Abre http://127.0.0.1:8080. Para detener el servicio:

    docker compose down

También puedes construir y ejecutar la imagen directamente:

    docker build -t analizador-kfc .
    docker run --rm -p 8080:8080 -e PORT=8080 analizador-kfc

## GitHub y despliegue

Este repositorio contiene una aplicación Flask con páginas renderizadas en servidor, formularios de análisis y descarga PDF. PORT es la única variable de entorno que lee el servidor; por defecto usa 8080. No requiere secretos, base de datos ni credenciales. El navegador carga Viz.js desde jsDelivr para dibujar autómatas y árboles.

### Netlify

El proyecto usa Netlify Server con Node.js 24 y ejecuta la misma aplicación Flask mediante Pyodide (Python en WebAssembly). El despliegue incluye la interfaz, el análisis por formulario o archivo, la API JSON y las descargas PDF y JFLAP. `netlify.toml` prepara los archivos estáticos y empaqueta el entorno de Python, por lo que el servidor no necesita descargar dependencias al recibir solicitudes.

Para probar el adaptador localmente con Node.js 24 y Netlify CLI 27.17 o posterior:

```sh
npm ci
node scripts/preparar-netlify.mjs
npm test
netlify dev --port 8889
```

El PDF de Netlify usa ReportLab 5.0.0 por compatibilidad con la versión de Pillow disponible en Pyodide. El despliegue de Flask en Docker/Render continúa usando las dependencias de `requirements.txt`.
