import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import ts from 'typescript'
async function load(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  const compiled = ts.transpileModule(source.replaceAll('import.meta.env.DEV', 'false'), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
}
const { formatarValorMensal, parseValorMensal } = await load('../src/utils/valorMensal.ts')
const { salvarDecisoes, previewDocumento } = await load('../src/api.ts')
test('valor mensal aceita formato brasileiro sem confundir milhares com centavos', () => {
  for (const [texto, valor] of [['1.234,56',1234.56],['R$ 150,00',150],['1.000',1000],['100.25',100.25],['100',100]]) {
    assert.equal(parseValorMensal(texto), valor)
  }
  for (const texto of ['', '0', '-10', 'NaN', '0,001', '1,2,3', '1.234.56', '1e3']) assert.equal(parseValorMensal(texto),null)
})
test('API preserva valores mensais e remoção', async t => {
  const requests=[]
  t.mock.method(globalThis,'fetch',async (url,options) => {
    requests.push({url,body:JSON.parse(options.body)})
    return new Response(JSON.stringify({ok:true,cenarios:{com_fundo:{receita_anual:1200}}}))
  })
  const payload={extraordinarias:{},revisar:{},inadimplencia:{},lancamentos:{},
    itens_manuais:[{id:'r',tipo:'receita',nome:'Locação',valor:1234.56}]}
  await salvarDecisoes('teste',payload)
  const r=await previewDocumento('teste',payload)
  assert.equal(requests[0].body.itens_manuais[0].valor,1234.56)
  assert.equal(r.cenarios.com_fundo.receita_anual,1200)
  await salvarDecisoes('teste',{...payload,itens_manuais:[]})
  assert.deepEqual(requests[2].body.itens_manuais,[])
})

test('máscara insere centavos e milhares e mantém o valor ao editar ou colar', () => {
  for (const [entrada, esperado] of [['1','0,01'],['12','0,12'],['123','1,23'],
    ['123456','1.234,56'],['R$ 1.234,56','1.234,56'],['1000.00','1.000,00'],
    ['000123456','1.234,56'],['',''],['0','0,00']]) {
    assert.equal(formatarValorMensal(entrada), esperado)
  }
  for (const valor of [0.01, 100, 1234.56, 1000000000]) {
    assert.equal(parseValorMensal(formatarValorMensal(valor.toFixed(2))), valor)
  }
})
