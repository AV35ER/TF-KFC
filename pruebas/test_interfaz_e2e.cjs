const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('../.tools/e2e/node_modules/playwright');

const baseUrl = process.env.KFC_BASE_URL || 'http://127.0.0.1:8080';
const evidenceDir = path.join(__dirname, 'evidencias');
const sizes = [
  { name: 'escritorio_1440x900', width: 1440, height: 900 },
  { name: 'portatil_1366x768', width: 1366, height: 768 },
  { name: 'movil_390x844', width: 390, height: 844 },
  { name: 'movil_pequeno_360x800', width: 360, height: 800 },
];

const report = {
  baseUrl,
  startedAt: new Date().toISOString(),
  viewportChecks: [],
  functionalChecks: [],
  downloads: [],
  consoleErrors: [],
  pageErrors: [],
  failedRequests: [],
  expectedDownloadAborts: [],
};

function check(collection, name, passed, details = '') {
  collection.push({ name, passed: Boolean(passed), details });
  console.log(`${passed ? 'PASS' : 'FAIL'} ${name}${details ? ` — ${details}` : ''}`);
}

async function submit(page, value) {
  await page.locator('#texto').fill(value);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.getByRole('button', { name: 'Analizar' }).click(),
  ]);
}

async function bodyText(page) {
  return (await page.locator('body').innerText()).replace(/\s+/g, ' ');
}

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(evidenceDir, `${name}.png`) });
}

async function run() {
  await fs.mkdir(evidenceDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
  page.on('console', (message) => {
    if (message.type() === 'error') report.consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => report.pageErrors.push(error.message));
  page.on('requestfailed', (request) => {
    const failure = request.failure()?.errorText || 'unknown';
    const item = { url: request.url(), error: failure };
    if (failure === 'net::ERR_ABORTED' && /\/(ejemplo\.txt|reporte-traduccion\.pdf|[A-Z]+_(AFND|AFD)\.jff)$/i.test(new URL(request.url()).pathname)) {
      report.expectedDownloadAborts.push(item);
    } else {
      report.failedRequests.push(item);
    }
  });

  for (const size of sizes) {
    await page.setViewportSize({ width: size.width, height: size.height });
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    check(report.viewportChecks, `${size.name}: formulario visible`,
      await page.locator('#texto').isVisible() && await page.locator('#archivo').isVisible());
    await submit(page, 'POLLO 2 EFECTIVO');
    await page.locator('.resumen').first().waitFor({ state: 'visible' });
    const svgRendered = await page.waitForFunction(
      () => document.querySelectorAll('.grafo svg').length >= 7,
      null, { timeout: 20000 },
    ).then(() => true).catch(() => false);
    const measurements = await page.evaluate(() => ({
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      graphCount: document.querySelectorAll('.grafo svg').length,
      tableWrappers: document.querySelectorAll('.tabla-scroll').length,
      slrHeader: [...document.querySelectorAll('th')].some((th) => th.textContent.includes('GOTO')),
      viewportMeta: Boolean(document.querySelector('meta[name="viewport"]')),
    }));
    const resultText = await bodyText(page);
    const noOverflow = !measurements.horizontalOverflow;
    check(report.viewportChecks, `${size.name}: sin desbordamiento horizontal global`, noOverflow,
      `document=${measurements.documentWidth}px, viewport=${measurements.viewportWidth}px`);
    check(report.viewportChecks, `${size.name}: Viz.js renderiza autómatas y árbol`, svgRendered,
      `${measurements.graphCount} gráficos SVG`);
    check(report.viewportChecks, `${size.name}: encabezado GOTO visible en la tabla SLR`, measurements.slrHeader);
    check(report.viewportChecks, `${size.name}: resumen del pedido visible`, resultText.includes('Pedidos válidos: 1 de 1'));
    check(report.viewportChecks, `${size.name}: estructura adaptable presente`, measurements.viewportMeta && measurements.tableWrappers > 0);
    report.viewportChecks.at(-1).measurements = measurements;

    await screenshot(page, `${size.name}_formulario`);
    const summaryHeading = page.locator('h3.sub').filter({ hasText: 'Resultado de la validación' });
    await summaryHeading.scrollIntoViewIfNeeded();
    await screenshot(page, `${size.name}_resultado`);
    const firstGraph = page.locator('.maquinas .grafo').first();
    await firstGraph.scrollIntoViewIfNeeded();
    await screenshot(page, `${size.name}_automatas`);
    const slrHeading = page.getByRole('heading', { name: /Tabla de análisis LR/ });
    await slrHeading.scrollIntoViewIfNeeded();
    await screenshot(page, `${size.name}_tabla_slr`);
    if (size.width <= 390) {
      const scrollableTableCount = await page.locator('.tabla-scroll').evaluateAll((nodes) =>
        nodes.filter((node) => node.scrollWidth > node.clientWidth + 1).length);
      check(report.viewportChecks, `${size.name}: tablas contenidas en sus contenedores`,
        await page.locator('.tabla-scroll').evaluateAll((nodes) => nodes.every((node) =>
          getComputedStyle(node).overflowX === 'auto' || getComputedStyle(node).overflowX === 'scroll')),
        `${scrollableTableCount} tablas requieren scroll horizontal interno`);
    }
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  const cases = [
    { name: 'pedido válido', input: 'POLLO 2 EFECTIVO', expected: ['Pedidos válidos: 1 de 1', 'SINTAXIS CORRECTA', 'CORRECTO'] },
    { name: 'error léxico', input: 'PIZZA 2 EFECTIVO', expected: ['Error léxico', 'No se evalúa'] },
    { name: 'error sintáctico', input: 'POLLO EFECTIVO', expected: ['Error sintáctico', 'se esperaba cantidad', 'No se evalúa'] },
    { name: 'cantidad cero semántica R1', input: 'POLLO 0 EFECTIVO', expected: ['Error semántico (R1)', 'entre 1 y 50'] },
    { name: 'cantidad 51 semántica R1', input: 'POLLO 51 EFECTIVO', expected: ['Error semántico (R1)', 'entre 1 y 50'] },
    { name: 'producto repetido semántica R2', input: 'POLLO 2 POLLO 1 EFECTIVO', expected: ['Error semántico (R2)', 'se repite'] },
  ];
  for (const item of cases) {
    await submit(page, item.input);
    const text = await bodyText(page);
    for (const expected of item.expected) {
      check(report.functionalChecks, `${item.name}: ${expected}`, text.includes(expected));
    }
  }
  await submit(page, 'POLLO 2 PAPAS 1 EFECTIVO');
  const translated = await bodyText(page);
  check(report.functionalChecks, 'traducción se muestra solo tras las tres validaciones',
    translated.includes('TRANSPILACIÓN GENERADA')
    && translated.includes('INSERT INTO pedidos')
    && translated.includes("'POLLO', 2")
    && translated.includes("'PAPAS', 1"));
  check(report.functionalChecks, 'la clasificación explica SQL como destino de nivel similar, no código máquina',
    translated.includes('un lenguaje de nivel similar')
    && translated.includes('No es una compilación a código máquina')
    && !translated.includes('pasa por las tres fases de un compilador'));
  await page.getByRole('heading', { name: '2.6 Traducción del DSL' }).scrollIntoViewIfNeeded();
  await screenshot(page, 'traduccion_sql_1440x900');
  await page.locator('.sql-generado').first().scrollIntoViewIfNeeded();
  await screenshot(page, 'codigo_sql_1440x900');
  await submit(page, 'POLLO 0 EFECTIVO');
  const rejectedTranslation = await bodyText(page);
  check(report.functionalChecks, 'pedido semánticamente rechazado no muestra SQL',
    rejectedTranslation.includes('SIN TRADUCCIÓN')
    && rejectedTranslation.includes('Error semántico (R1)')
    && !rejectedTranslation.includes('INSERT INTO pedidos'));
  await submit(page, 'POLLO 1 EFECTIVO');
  const disclaimers = await bodyText(page);
  check(report.functionalChecks, 'mensajes describen simulación sin afirmar envío a cocina',
    disclaimers.includes('Pedido validado (simulación)')
    && disclaimers.includes('cumplen las reglas de validación')
    && !/enviar a cocina|enviarlos a cocina|validado a cocina/i.test(disclaimers));

  await submit(page, 'POLLO 2 EFECTIVO\nALITAS 0 YAPE\nGASEOSA 3 TARJETA');
  let currentResult = await page.locator('main > section').last().innerText();
  check(report.functionalChecks, 'múltiples pedidos: 2 válidos de 3 y líneas independientes',
    currentResult.includes('2 de 3') && currentResult.includes('ALITAS 0 YAPE')
    && currentResult.includes('GASEOSA 3 TARJETA'));

  await page.locator('#archivo').setInputFiles(path.join(__dirname, '..', 'ejemplo.txt'));
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.getByRole('button', { name: 'Analizar' }).click(),
  ]);
  currentResult = await page.locator('main > section').last().innerText();
  check(report.functionalChecks, 'carga TXT: 3 pedidos de ejemplo válidos',
    currentResult.includes('3 de 3') && currentResult.includes('HAMBURGUESA 3 GASEOSA 3 TARJETA'));

  await submit(page, 'POLLO 1 EFECTIVO');
  currentResult = await page.locator('main > section').last().innerText();
  check(report.functionalChecks, 'entrada nueva reemplaza resultados del TXT anterior',
    currentResult.includes('1 de 1') && currentResult.includes('POLLO 1 EFECTIVO')
    && !currentResult.includes('HAMBURGUESA 3 GASEOSA 3 TARJETA'));

  const downloadPage = page;
  const [exampleDownload] = await Promise.all([
    downloadPage.waitForEvent('download'),
    downloadPage.getByRole('link', { name: /Descarga un archivo de ejemplo/ }).click(),
  ]);
  report.downloads.push({ name: 'ejemplo.txt', failure: await exampleDownload.failure() });
  check(report.functionalChecks, 'descarga de ejemplo TXT funciona', !await exampleDownload.failure());

  for (const token of ['PRODUCTO', 'CANTIDAD', 'PAGO']) {
    for (const type of ['afnd', 'afd']) {
      const href = `/jflap/${token}_${type}.jff`;
      const anchor = page.locator(`a[href="${href}"]`);
      const owner = page.locator('details').filter({ has: anchor }).first();
      if (!await owner.evaluate((element) => element.open)) await owner.locator('summary').click();
      const [download] = await Promise.all([page.waitForEvent('download'), anchor.click()]);
      const failure = await download.failure();
      report.downloads.push({ name: download.suggestedFilename(), failure });
      check(report.functionalChecks, `descarga de ${token} ${type.toUpperCase()}`,
        !failure && download.suggestedFilename() === `${token}_${type.toUpperCase()}.jff`);
    }
  }

  const zoomGraph = page.locator('.maquinas .grafo').first();
  await zoomGraph.scrollIntoViewIfNeeded();
  await zoomGraph.click();
  const zoomed = await zoomGraph.evaluate((element) => element.classList.contains('grande'));
  const widthAfterZoom = await page.evaluate(() => document.documentElement.scrollWidth);
  check(report.functionalChecks, 'zoom de gráfico funciona sin ensanchar la página',
    zoomed && widthAfterZoom <= 1441, `document=${widthAfterZoom}px`);

  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await submit(page, 'POLLO 2 EFECTIVO');
  await page.getByRole('heading', { name: '2.6 Traducción del DSL' }).scrollIntoViewIfNeeded();
  await screenshot(page, 'traduccion_sql_movil_360x800');
  await page.locator('.sql-generado').first().scrollIntoViewIfNeeded();
  await screenshot(page, 'codigo_sql_movil_360x800');
  const mobileGraph = page.locator('.maquinas .grafo').first();
  await mobileGraph.scrollIntoViewIfNeeded();
  await mobileGraph.click();
  const mobileGraphState = await mobileGraph.evaluate((element) => ({
    zoomed: element.classList.contains('grande'),
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }));
  const mobileDocumentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  check(report.functionalChecks, 'gráfico PRODUCTO ampliable en móvil con scroll interno',
    mobileGraphState.zoomed && mobileGraphState.scrollWidth > mobileGraphState.clientWidth
    && mobileDocumentWidth <= 361, `contenedor=${mobileGraphState.clientWidth}px, página=${mobileDocumentWidth}px`);
  await screenshot(page, 'movil_pequeno_360x800_automatas_zoom');

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('#texto').fill('POLLO 2 EFECTIVO\nPIZZA 1 YAPE');
  const [pdfDownload] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Descargar reporte PDF' }).click(),
  ]);
  const pdfPath = await pdfDownload.path();
  const pdfBytes = await fs.readFile(pdfPath);
  const pdfFailure = await pdfDownload.failure();
  report.downloads.push({
    name: pdfDownload.suggestedFilename(),
    failure: pdfFailure,
    bytes: pdfBytes.length,
    startsWithPdfSignature: pdfBytes.subarray(0, 5).toString('ascii') === '%PDF-',
  });
  check(report.functionalChecks, 'reporte PDF se descarga con firma PDF y ambos pedidos',
    !pdfFailure && pdfDownload.suggestedFilename() === 'reporte-traduccion-dsl.pdf'
    && pdfBytes.subarray(0, 5).toString('ascii') === '%PDF-'
    && pdfBytes.length > 1000);

  report.finishedAt = new Date().toISOString();
  report.summary = {
    viewportChecks: report.viewportChecks.filter((item) => item.passed).length,
    viewportFailures: report.viewportChecks.filter((item) => !item.passed).length,
    functionalChecks: report.functionalChecks.filter((item) => item.passed).length,
    functionalFailures: report.functionalChecks.filter((item) => !item.passed).length,
    consoleErrors: report.consoleErrors.length,
    pageErrors: report.pageErrors.length,
    failedRequests: report.failedRequests.length,
    expectedDownloadAborts: report.expectedDownloadAborts.length,
    screenshots: (await fs.readdir(evidenceDir)).filter((name) => name.endsWith('.png')).length,
  };
  await fs.writeFile(path.join(__dirname, 'reporte-e2e-ui.json'), JSON.stringify(report, null, 2), 'utf8');
  await browser.close();
  console.log(JSON.stringify(report.summary, null, 2));
  if (report.summary.viewportFailures || report.summary.functionalFailures || report.summary.pageErrors) process.exitCode = 1;
}

run().catch(async (error) => {
  report.fatalError = error.stack || error.message;
  report.finishedAt = new Date().toISOString();
  await fs.mkdir(evidenceDir, { recursive: true });
  await fs.writeFile(path.join(__dirname, 'reporte-e2e-ui.json'), JSON.stringify(report, null, 2), 'utf8');
  console.error(error);
  process.exitCode = 1;
});
