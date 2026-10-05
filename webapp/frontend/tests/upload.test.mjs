import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import ts from 'typescript'

async function load(relativePath) {
  const source = await readFile(new URL(relativePath, import.meta.url), 'utf8')
  const compiled = ts.transpileModule(source.replaceAll('import.meta.env.DEV', 'false'), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
}

const { validarArquivo, MAX_UPLOAD_BYTES } = await load('../src/utils/upload.ts')
const { criarSessao } = await load('../src/api.ts')

test('aceita os formatos reais de cada relatório, inclusive extensão maiúscula', () => {
  for (const [name, accept] of [['bal anual.xls', '.xls'], ['FIN00601.XLSX', '.xlsx'], ['Inadimplência.PDF', '.pdf']]) {
    assert.equal(validarArquivo({ name, size: 100 }, accept), null)
  }
})

test('recusa formato errado, arquivo vazio e tamanho acima do limite do backend', () => {
  assert.match(validarArquivo({ name: 'FIN.xls', size: 100 }, '.xlsx'), /Formato inválido/)
  assert.match(validarArquivo({ name: 'relatório.pdf', size: 0 }, '.pdf'), /vazio/)
  assert.match(validarArquivo({ name: 'relatório.pdf', size: MAX_UPLOAD_BYTES + 1 }, '.pdf'), /20 MB/)
  assert.equal(validarArquivo({ name: 'relatório.pdf', size: MAX_UPLOAD_BYTES }, '.pdf'), null)
})

test('envia documentos de cada sistema nos campos corretos sem inadimplência antiga no modo misto', async (t) => {
  let request
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    request = { url, ...options }
    return new Response(JSON.stringify({ sessao_id: 'teste' }))
  })
  const file = (name) => new File(['dados'], name)
  await criarSessao({
    nome: 'Santorini', ano: 2026, origemSistema: 'misto',
    balanual: file('balanual.xls'), desbai: file('desbai06.xls'), rec: file('rec02.xls'),
    inad: file('inad01.xls'), almaBal: file('período.pdf'), almaFin: file('FIN.xlsx'),
    almaRec: file('receber.pdf'), almaInad: file('inad.pdf'), semInadAlma: true,
    periodoInicio: '2025-09', periodoFim: '2026-08',
  })
  assert.equal(request.url, '/api/sessao')
  assert.equal(request.method, 'POST')
  assert.equal(request.headers, undefined, 'o navegador precisa definir o boundary multipart')
  assert.equal(request.body.get('alma_fin').name, 'FIN.xlsx')
  assert.equal(request.body.get('alma_bal').name, 'período.pdf')
  assert.equal(request.body.get('alma_rec').name, 'receber.pdf')
  assert.equal(request.body.get('origem_sistema'), 'misto')
  assert.equal(request.body.get('sem_inadimplencia_alma'), 'true')
  assert.equal(request.body.get('periodo_inicio'), '2025-09')
  assert.equal(request.body.get('inad'), null)
  assert.equal(request.body.get('alma_inad'), null)
})

test('preserva inadimplência no Condo21 e envia relatório Alma quando há inadimplentes', async (t) => {
  const forms = []
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    forms.push(options.body)
    return new Response(JSON.stringify({ sessao_id: 'teste' }))
  })
  const file = new File(['dados'], 'relatório.xls')
  const base = { nome: 'Teste', ano: 2026, balanual: file, desbai: file, rec: file, inad: file }
  await criarSessao(base)
  assert.equal(forms[0].get('inad').name, file.name)
  await criarSessao({ ...base, origemSistema: 'misto', almaInad: new File(['dados'], 'inad.pdf') })
  assert.equal(forms[1].get('alma_inad').name, 'inad.pdf')
  assert.equal(forms[1].get('inad'), null)
})
