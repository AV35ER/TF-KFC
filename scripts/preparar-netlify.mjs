import { createHash } from 'node:crypto';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(import.meta.dirname, '..');
const pyodide = dirname(fileURLToPath(import.meta.resolve('pyodide')));
const runtime = join(root, 'netlify/server/runtime');
const staticDir = join(root, 'public/static');
const { version } = JSON.parse(await readFile(join(pyodide, 'package.json'), 'utf8'));
const { packages } = JSON.parse(await readFile(join(pyodide, 'pyodide-lock.json'), 'utf8'));

const core = ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'];
const pyodideWheels = ['charset-normalizer', 'click', 'jinja2', 'markupsafe', 'pillow'];
const appFiles = [
  'app.py', 'automatas.py', 'reporte_pdf.py', 'semantico.py', 'sintactico.py', 'traductor.py',
  'static/estilos.css', 'templates/index.html',
];
const pypiWheels = [
  ['ec/f9/7f9263c5695f4bd0023734af91bedb2ff8209e8de6ead162f35d8dc762fd/flask-3.1.2-py3-none-any.whl', 'ca1d8112ec8a6158cc29ea4858963350011b5c846a414cdb7a954aa9e967d03c'],
  ['93/8c/2e650f2afeb7ee576912636c23ddb621c91ac6a98e66dc8d29c3c69446e1/werkzeug-3.1.8-py3-none-any.whl', '63a77fb8892bf28ebc3178683445222aa500e48ebad5ec77b0ad80f8726b1f50'],
  ['04/96/92447566d16df59b2a776c0fb82dbc4d9e07cd95062562af01e408583fc4/itsdangerous-2.2.0-py3-none-any.whl', 'c6242fc49e35958c8b15141343aa660db5fc54d4f13a1db01a3f5891b98700ef'],
  ['10/cb/f2ad4230dc2eb1a74edf38f1a38b9b52277f75bef262d8908e60d957e13c/blinker-1.9.0-py3-none-any.whl', 'ba0efaa9080b619ff2f3459d1d500c57bddea4a6b424b60a91141db6fd2f08bc'],
  ['a3/07/70085c17a369605f15e301d10ab902115019b1126c7253d964afc230c7d6/reportlab-5.0.0-py3-none-any.whl', '9d5a3affa84919e1111ede580031266a570e93b1ce388219621347965ff1d93c'],
];

async function downloadWheel(url, sha256) {
  const filename = new URL(url).pathname.split('/').at(-1);
  const path = join(runtime, filename);
  const matches = (bytes) => createHash('sha256').update(bytes).digest('hex') === sha256;
  const cached = await readFile(path).catch(() => null);
  if (cached && matches(cached)) return;

  const response = await fetch(url, { signal: AbortSignal.timeout(30_000) });
  if (!response.ok) throw new Error(`No se pudo descargar ${filename}: HTTP ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (!matches(bytes)) throw new Error(`La suma SHA-256 no coincide: ${filename}`);
  await writeFile(path, bytes);
}

await Promise.all([
  mkdir(join(runtime, 'app/static'), { recursive: true }),
  mkdir(join(runtime, 'app/templates'), { recursive: true }),
  mkdir(staticDir, { recursive: true }),
]);
await Promise.all([
  ...core.map((file) => copyFile(join(pyodide, file), join(runtime, file))),
  ...appFiles.map((file) => copyFile(join(root, file), join(runtime, 'app', file))),
  ...pyodideWheels.map((name) => {
    const { file_name: file, sha256 } = packages[name];
    return downloadWheel(`https://cdn.jsdelivr.net/pyodide/v${version}/full/${file}`, sha256);
  }),
  ...pypiWheels.map(([file, sha256]) => downloadWheel(`https://files.pythonhosted.org/packages/${file}`, sha256)),
  copyFile(join(root, 'static/estilos.css'), join(staticDir, 'estilos.css')),
]);
await writeFile(join(runtime, 'manifest.json'), JSON.stringify({
  appFiles,
  pyodideWheels,
  pure: pypiWheels.map(([file]) => file.split('/').at(-1)),
}));
