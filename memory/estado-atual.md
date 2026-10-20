# Estado atual — Previsão Orçamentária

> Documento vivo. **Atualizar a cada mudança** (ver `CLAUDE.md`). Última atualização: 19/10/2026.
> Histórico detalhado de sessões antigas: `git log` e versões anteriores de `memory/`.

## O que é

Webapp interno da Porto Real Imóveis: transforma relatórios dos sistemas de
condomínio em previsão orçamentária anual (PDF para o síndico). Quem valida as
regras de negócio é o **José Henrique** (envia feedback por áudio).
IA classifica lançamentos ambíguos; aritmética é determinística; humano revisa.

## Stack e deploy

- Motor: `previsao.py` (parsers, regras, IA, receitas, inadimplência, cenários).
  Adaptadores: `parsers_alma.py`, `parsers_group.py`, `parsers_sistemas.py`, `ia_parser.py`.
- API: `webapp/backend/main.py` (FastAPI) + MySQL (`db.py`, sessões permanentes, arquivos em BLOB).
- PDF: `webapp/backend/relatorio_pdf.py` (Jinja2 + WeasyPrint; não roda no macOS, testar via Docker).
  XLSX: `gerador_previsao.py` (legado; não recebe as mudanças recentes do PDF).
- Frontend: React 19 + Vite + TS (`webapp/frontend/src`).
- Deploy: push no GitHub → **rebuild manual no EasyPanel** (serviço previsao). Push ≠ deploy:
  nunca dizer que está no ar sem confirmar.
- Banco prod: credenciais fora do repo (arquivo local da usuária); porta externa só aberta p/ uso pontual.
  Acesso direto do agente é bloqueado → usuária roda `! .venv/bin/python tmp/baixar_sessao.py [id]` (só leitura).\n  Desde 19/10 uploads recusados também ficam no banco (etapa/erro): pedir o protocolo mostrado na tela.
- IA: OpenAI exclusivamente (`PREVISAO_IA_PROVEDOR=openai`, modelo `gpt-6.1-sol`, reasoning `high`).
- Testes: `cd webapp/backend && PYTHONPATH=../.. ../../.venv/bin/python -m unittest discover -p 'test_*.py'`
  (4 falhas conhecidas em `test_classificacao_capital` — caso "projetor", pré-existentes).

## Sistemas e documentos aceitos hoje

- **Condo21 sozinho**: `balanual.xls`, `desbai06.xls`, `rec02.xls` obrigatórios; `dessin02.xls`, `inad01.xls` opcionais.
- **Group sozinho**: balancete anual, despesas detalhadas, receitas por unidade; inadimplência detalhada opcional.
- **Alma**: FIN00601 (XLSX despesas), Por período agrupado por contas (PDF), Contas a receber agrupado
  por conta (PDF), Inadimplência (PDF) ou checkbox "sem inadimplência". Plano de contas Alma é interno (`data/plano_contas_alma.json`).
- **Com o Alma no conjunto, o Alma prevalece**: Condo21 envia só `desbai06`; Group só despesas detalhadas.
  Receita atual e inadimplência vêm só do Alma. Demonstrativo do sistema anterior = soma dos pagamentos
  (`parsers_alma.balance_from_payments`). Alma ocupa os meses recentes, o outro sistema os anteriores.

## Regras de negócio vigentes

Resumo em `regras.md`. Decisões que não podem regredir:
- Aumento previsto fixo 10%; superávit mínimo R$ 2.000/mês (R$ 24.000/ano).
- Receita ordinária = taxa condominial (com desconto embutido) + fundo de reserva + receitas recorrentes
  identificadas (ex.: aluguel de antena). Fora: complemento, juros, multa, taxa extra, rendimentos, repasses.
- Seguro: última parcela da apólice vigente × total de parcelas ("Parcela N/M"), ÷12 no mensal.
- 13ª taxa de administração nunca aparece no texto público (valor continua no cálculo).
- Nome do condomínio é informado pela operação; nunca substituir pelo extraído do REC.
- Valores sempre rotulados como mensal ou anual.
- Não ajustar valores para bater artificialmente com a planilha do José.

## Último trabalho (19/10/2026)

- **Bug Forte Way (Condo21 + Alma):** upload travava com "Há meses com movimentação nos dois sistemas: 10/2025 … 08/2026".
  Causa: o demonstrativo Alma exportado para o ano todo lista zerados os meses antes da migração, e
  `consolidate_balances` contava todo mês do PDF como cobertura do Alma. Agora só conta da 1ª à última movimentação
  (mesma regra do fluxo Group + Alma). Teste novo em `test_mixed_import.py`; Santorini e Berlin idênticos.
  Commit local, **falta push + rebuild**. Hipótese não confirmada com os arquivos reais: a validação roda antes de
  salvar a sessão, então os arquivos do Forte Way não ficaram no banco.

- **Bug Aldeia das Asas (Group sozinho):** "Group: conta 1.1.6 repetida no balancete". Agora linhas com o mesmo
  código na mesma seção são somadas numa conta só, com aviso na análise; a conferência com o total da seção
  continua barrando cópia indevida. Confirmado com o arquivo real (ver abaixo).

- **Upload gravado antes de validar (pedido da usuária, 19/10):** `POST /api/sessao` grava sessão + arquivos no clique
  (`etapa='recebido'`), depois valida. Recusa → `etapa='erro_validacao'` + `erro`, e a tela mostra "(Protocolo <id>)".
  Análise grava `analisado`/`erro_analise`; sessões recusadas não podem ser analisadas (409). Colunas `etapa`/`erro`
  criadas pelo `_init_schema` na subida (testado em MySQL 8.4 com esquema antigo). `tmp/baixar_sessao.py` mostra etapa e erro.
- **Aldeia das Asas conferido com os arquivos reais:** 1.1.6 Taxa Extra e 1.1.8 Compl. Tx. Condomínio vêm em 2 linhas
  cada (uma de estornos negativos) → somadas. MAS o "Despesas detalhadas" veio filtrado em **Competência 08/2026**
  (R$ 131 mil de R$ 1,49 mi do balancete); reexportar com Competência: Todas.

- **Inadimplência no Group sozinho (pedido da usuária, 19/10):** novo upload opcional "Inadimplência detalhada"
  (`group_inad`, coluna `arquivo_group_inad`), lido por `parsers_group.parse_arrears` no formato comum do inad01 e
  tratado pela mesma R8 do Condo21. Confere total e nº de unidades do relatório (não traz nome do condomínio).
  Aldeia das Asas real: Águia-201 (13 meses) → abate R$ 472,23/mês. Corrigido junto: última parcela era escolhida
  comparando "MM/AAAA" como texto (12/2025 > 09/2026) — afetava também o Condo21. PDF não força mais
  "inadimplência não apurada" para todo Group. Com Alma no conjunto, o campo não aparece (inadimplência do Alma).

## Fase 2 (18/10/2026)

- Feedback José 13/10 e 17/10: seguro pela apólice vigente; considerações com maiúscula, "R$" e "etc.";
  R5 desligada (cartório em "Despesas Cartoriais e Honorários").
- **Fase 2 feita (no GitHub em 18/10; falta rebuild no EasyPanel):** com o Alma no conjunto, Condo21/Group só
  despesas detalhadas; inadimplência abate um boleto inteiro (taxa+fundo+água) da unidade que deve OS DOIS
  meses anteriores ao mês do relatório Alma (outubro → setembro e agosto); gráfico do PDF = despesa de cada mês × **receita atual** (legenda
  "Receita atual") em todos os modos.
- Prova real (`tmp/prova_codigo_novo.py`/`.txt`, dados de prod em `tmp/sessoes/`): Santorini só com
  desbai06 + Alma e Berlin só com despesas Group + Alma → subtotal, total e receita idênticos aos de antes.
  Inadimplência não exercitada com dado real (0 unidades na janela dos dois); coberta por teste unitário.

## Próximos passos

1. Reenviar Forte Way e Aldeia das Asas (despesas reexportadas sem filtro de competência) após o rebuild.\n   Avaliar com o José: bloquear quando as despesas detalhadas cobrem muito menos que o balancete (hoje só avisa). Se ainda acusar sobreposição, pedir os arquivos
   (o desbai06 teria pagamentos em meses que já são do Alma). Regerar PDFs (Berlin `b633bf8000b5`, Atlântico,
   Santorini) — sessões antigas mantêm o gráfico antigo até reanalisar.
2. Pedir ao José um caso real com inadimplente nos 2 últimos meses para validar o abatimento do boleto.
3. R4 ainda gera "Provisão para Laudo de Autovistoria" para contas não genéricas de Despesas Diversas
   (aparece no Berlin) — nome que o José não usa; avaliar com ele.
4. Santorini: R$ 9.000 de caminhões-pipa deduzidos pela estatística precisam de validação humana.
   FIN do Alma não traz tarifas bancárias (aviso de diferença aparece; o demonstrativo Alma cobre).
5. Segurança: revisar credenciais do banco e autenticação da API (pendência registrada fora do repo).

## Arquivos locais (fora do git)

`tmp/` (backups de prod, ex.: substituição Berlin 13/10 com manifest SHA-256), `output/`, `outputs/`
(PDF/CSV de conferência Santorini). Contêm dados de clientes — nunca commitar.
