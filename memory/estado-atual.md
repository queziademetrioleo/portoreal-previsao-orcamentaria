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

- **Condo21**: `balanual.xls`, `desbai06.xls`, `rec02.xls` obrigatórios; `dessin02.xls`, `inad01.xls` opcionais.
- **Group**: balancete anual, despesas detalhadas, receitas por unidade.
- **Alma**: FIN00601 (XLSX despesas), Por período agrupado por contas (PDF), Contas a receber agrupado
  por conta (PDF), Inadimplência (PDF) ou checkbox "sem inadimplência". Plano de contas Alma é interno (`data/plano_contas_alma.json`).
- **Misto** (Condo21+Alma ou Group+Alma): Alma ocupa os meses recentes, o outro sistema os anteriores, sem duplicar.
  Receita e inadimplência vêm **só do Alma** (valor atual).

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

## Último trabalho (18/10/2026) — feedback José 13/10 e 17/10

Feito (commit desta data):
- Seguro pela apólice vigente (Atlântico: 652,90 × 6 = 3.917,40/ano = 326,45/mês).
- Considerações: inicial maiúscula por frase, "R$" maiúsculo; conservação sem "Outras despesas" e com ", etc.".
- R5 desligada: cartório fica em "Despesas Cartoriais e Honorários" (José não tinha a "Provisão para
  Sistema de Incêndio/Registro" na planilha; era registro de ata + reconhecimento de firma).

## Próximos passos

1. **Fase 2 — menos documentos no modo misto com Alma** (pedido do José, 17/10):
   Condo21/Group só precisam das despesas detalhadas (Condo21: `desbai06`); Alma: FIN00601 (despesas) +
   FIN00801 (taxa, fundo de reserva e inadimplência atuais, equivale ao rec02). Dispensar balanual, dessin,
   rec/inad do sistema antigo e o "Por período agrupado" do Alma. Exemplo real: sessão "Forte Way" no banco
   (nome exato não encontrado com LIKE '%fort%'; listar sessões com `tmp/baixar_sessao.py`). Falta um FIN00801.
   Atenção: hoje o balanual define cobertura de meses e confere totais — substituir pelas datas de pagamento.
2. Deploy no EasyPanel de tudo desde `892a54a` e regerar PDFs (Berlin `b633bf8000b5`, Atlântico).
3. R4 ainda gera "Provisão para Laudo de Autovistoria" para contas não genéricas de Despesas Diversas
   (nome que o José também não usa) — avaliar desligar se ele estranhar.
4. Santorini: R$ 9.000 de caminhões-pipa deduzidos pela estatística precisam de validação humana;
   R$ 55,38 de tarifas no demonstrativo Alma ausentes do FIN (mantidos na base).
5. Segurança: revisar credenciais do banco e autenticação da API (pendência registrada fora do repo).

## Arquivos locais (fora do git)

`tmp/` (backups de prod, ex.: substituição Berlin 13/10 com manifest SHA-256), `output/`, `outputs/`
(PDF/CSV de conferência Santorini). Contêm dados de clientes — nunca commitar.
