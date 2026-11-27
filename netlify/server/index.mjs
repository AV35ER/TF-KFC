import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const runtime = join(import.meta.dirname, 'runtime');
export const config = {
  includedFiles: ['runtime/**', 'wsgi.py'],
};

async function startFlask() {
  const { loadPyodide } = await import(pathToFileURL(join(runtime, 'pyodide.mjs')).href);
  const pyodide = await loadPyodide({ indexURL: runtime });
  const { appFiles, pyodideWheels, pure } = JSON.parse(await readFile(join(runtime, 'manifest.json'), 'utf8'));
  await pyodide.loadPackage([...pyodideWheels, ...pure.map((file) => join(runtime, file))]);

  pyodide.FS.mkdirTree('/kfc/static');
  pyodide.FS.mkdirTree('/kfc/templates');
  await Promise.all(appFiles.map(async (file) => {
    pyodide.FS.writeFile(`/kfc/${file}`, await readFile(join(runtime, 'app', file)));
  }));
  pyodide.runPython(await readFile(join(import.meta.dirname, 'wsgi.py'), 'utf8'));
  return pyodide.globals.get('handle_request');
}

let flask;

export default async function handleRequest(request) {
  flask ??= startFlask().catch((error) => {
    flask = undefined;
    throw error;
  });
  const [handle, bytes] = await Promise.all([flask, request.arrayBuffer()]);
  const result = handle(JSON.stringify({
    url: request.url,
    method: request.method,
    headers: [...request.headers],
  }), new Uint8Array(bytes));
  try {
    const [status, headers, body] = result.toJs();
    const noBody = request.method === 'HEAD' || [204, 205, 304].includes(status);
    return new Response(noBody ? null : body, { status, headers });
  } finally {
    result.destroy();
  }
}
