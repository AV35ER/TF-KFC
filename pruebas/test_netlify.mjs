import assert from 'node:assert/strict';
import { test } from 'node:test';
import handleRequest from '../netlify/server/index.mjs';

const request = (path, options) => handleRequest(new Request(`https://example.com${path}`, options));
const order = 'POLLO 2 EFECTIVO';

test('publica el formulario y el CSS', async () => {
  const [page, css] = await Promise.all([request('/'), request('/static/estilos.css')]);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /<textarea[^>]*name="texto"/);
  assert.equal(css.status, 200);
  assert.match(css.headers.get('content-type'), /^text\/css/);
});

test('analiza pedidos del formulario multipart y de la API JSON', async () => {
  const multipart = new FormData();
  multipart.set('archivo', new File([order], 'pedido.txt', { type: 'text/plain' }));
  const page = await request('/', { method: 'POST', body: multipart });
  assert.equal(page.status, 200);
  assert.match(await page.text(), /INSERT INTO pedidos/);

  const response = await request('/api/analizar', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ texto: `${order}\nPIZZA 1 EFECTIVO` }),
  });
  assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).resumen, { total: 2, validos: 1 });
});

test('descarga PDF, JFLAP y texto sin modificar los bytes', async () => {
  const pdf = await request('/reporte-traduccion.pdf', {
    method: 'POST', body: new URLSearchParams({ texto: order }),
  });
  assert.equal(pdf.status, 200);
  assert.equal(pdf.headers.get('content-type'), 'application/pdf');
  assert.match(pdf.headers.get('content-disposition'), /^attachment;/);
  const bytes = Buffer.from(await pdf.arrayBuffer());
  assert.equal(bytes.subarray(0, 5).toString(), '%PDF-');
  assert.match(bytes.subarray(-20).toString(), /%%EOF/);

  const jflap = await request('/jflap/PRODUCTO_afd.jff');
  assert.equal(jflap.status, 200);
  assert.match(await jflap.text(), /<automaton>/);

  const example = await request('/ejemplo.txt');
  assert.equal(example.status, 200);
  assert.match(await example.text(), /POLLO/);
});

test('mantiene los estados HTTP y omite el cuerpo en HEAD', async () => {
  const missing = await request('/ruta-inexistente');
  assert.equal(missing.status, 404);
  const head = await request('/', { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(await head.text(), '');
});
