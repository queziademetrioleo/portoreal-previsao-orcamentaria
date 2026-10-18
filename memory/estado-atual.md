# Estado atual — Previsão Orçamentária

> Documento vivo. **Atualizar a cada mudança** (ver `CLAUDE.md`). Última atualização: 18/10/2026.
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
  Acesso direto do agente é bloqueado → usuária roda `! .venv/bin/python tmp/baixar_sessao.py [id]` (só leitura).
- IA: OpenAI exclusivamente (`PREVISAO_IA_PROVEDOR=openai`, modelo `gpt-6.1-sol`, reasoning `high`).
- Testes: `cd webapp/backend && PYTHONPATH=../.. ../../.venv/bin/python -m unittest discover -p 'test_*.py'`
  (4 falhas conhecidas em `test_classificacao_capital` — caso "projetor", pré-existentes).

## Sistemas e documentos aceitos hoje

- **Condo21 sozinho**: `balanual.xls`, `desbai06.xls`, `rec02.xls` obrigatórios; `dessin02.xls`, `inad01.xls` opcionais.
- **Group sozinho**: balancete anual, despesas detalhadas, receitas por unidade.
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

## Último trabalho (18/10/2026)

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

1. Rebuild no EasyPanel (GitHub já tem tudo até `5532eb9`); regerar PDFs (Berlin `b633bf8000b5`, Atlântico,
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
