# Estado atual — Previsão Orçamentária

> Documento vivo. **Atualizar a cada mudança** (ver `CLAUDE.md`). Última atualização: 29/10/2026.
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
- PDF: `webapp/backend/relatorio_pdf.py` (Jinja2 + WeasyPrint; no Mac roda com `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` — pango/cairo do Homebrew;
  conferir páginas com `pdftoppm -r 50 -png`).
  XLSX: `gerador_previsao.py` (legado; não recebe as mudanças recentes do PDF).
- Frontend: React 19 + Vite + TS (`webapp/frontend/src`).
- Deploy: push no GitHub → **rebuild manual no EasyPanel** (serviço previsao). Push ≠ deploy:
  nunca dizer que está no ar sem confirmar.
- Banco prod: credenciais fora do repo (arquivo local da usuária); porta externa só aberta p/ uso pontual.
  Acesso direto do agente é bloqueado → usuária roda `! .venv/bin/python tmp/baixar_sessao.py [id]` (só leitura).\n  Desde 19/10 uploads recusados também ficam no banco (etapa/erro): pedir o protocolo mostrado na tela.
- IA: em 21/10 a usuária migrou p/ Claude via variáveis no EasyPanel (`PREVISAO_IA_PROVEDOR=anthropic`, `PREVISAO_IA_MODELO=claude-opus-5-5`,
  `ANTHROPIC_API_KEY`). ID certo é `claude-opus-5-5` (com ponto dá 404 e, sem provedor fixado, cai silenciosamente na OpenAI `gpt-6.1-sol`).
  `_anthropic_chat` não usa thinking (OpenAI usava reasoning high). Conferir `modelo_ia` da sessão nova. Defaults de `.env.example`/compose/README ainda dizem OpenAI.
- Testes: `cd webapp/backend && PYTHONPATH=../.. ../../.venv/bin/python -m unittest discover -p 'test_*.py'`
  (4 falhas conhecidas em `test_classificacao_capital` — 'projetor' voltou a CAPITAL_KW em 07/10; ver próximos passos).

## Sistemas e documentos aceitos hoje

- **Condo21 sozinho**: `balanual.xls`, `desbai06.xls`, `rec02.xls` obrigatórios; `dessin02.xls`, `inad01.xls` opcionais.
- **Group sozinho**: balancete anual, despesas detalhadas, receitas por unidade; inadimplência detalhada opcional.
- **Alma**: FIN00601 (XLSX despesas; Status opcional), Por período agrupado por contas (PDF), Contas a receber agrupado
  por conta (PDF) **ou** Rateio por Unidade (XLSX), Inadimplência (PDF) ou checkbox "sem inadimplência". Plano de contas Alma é interno (`data/plano_contas_alma.json`).
- **Com o Alma no conjunto, o Alma prevalece**: Condo21 envia só `desbai06`; Group só despesas detalhadas.
  Receita atual e inadimplência vêm só do Alma. Demonstrativo do sistema anterior = soma dos pagamentos
  (`parsers_alma.balance_from_payments`). Alma ocupa os meses recentes, o outro sistema os anteriores;
  no Condo21 + Alma, mês com lançamento nos dois é somado por conta (aviso na tela).

## Regras de negócio vigentes

Resumo em `regras.md`. Decisões que não podem regredir:
- Aumento previsto fixo 10%; superávit mínimo R$ 2.000/mês (R$ 24.000/ano).
- Receita ordinária = taxa condominial (com desconto embutido) + fundo de reserva + receitas recorrentes
  identificadas (ex.: aluguel de antena). **Água cobrada das unidades sempre entra** (média
  dos meses com receita no balancete; usuária 23/10/2026), assim como receitas adicionadas à mão. Fora: complemento, juros, multa, taxa extra, rendimentos, repasses.
- Seguro: última parcela da apólice vigente × total de parcelas ("Parcela N/M"), ÷12 no mensal.
- 13ª taxa de administração nunca aparece no texto público (valor continua no cálculo).
- Nome do condomínio é informado pela operação; nunca substituir pelo extraído do REC.
- Valores sempre rotulados como mensal ou anual.
- Não ajustar valores para bater artificialmente com a planilha do José.

## Último trabalho (29/10/2026) — feedback José 28/10 (vale p/ todos, PDF/DOCX/XLSX)

- **Bug seguro Alma (Chateau Canões `0973588a1d80`):** relatório saiu com Seguro de Incêndio R$ 68,89/mês
  (826,67 × 1 ÷ 12). A coluna Parcela do FIN Alma vem "01/01" (lançamento sem parcelamento), e a apólice está na
  descrição ("PARCELA 04/06", Allianz). `_total_parcelas_seguro` agora ignora coluna 1/1 → 826,67 × 6 = R$ 4.960,02/ano
  = R$ 413,34/mês. Vale p/ qualquer Alma. Após o rebuild: abrir a sessão e salvar a revisão (recalcula do cache) ou
  reanalisar; regerar o relatório. Conferir outras sessões Alma (Forte Way, Santorini, Berlin) com o mesmo padrão.
- **Conclusão sem a frase "O resultado mensal é de … (DÉFICIT/SUPERÁVIT)"**: fica só média dos N meses + inadimplência
  como redução da receita. O título colorido (superávit/déficit) continua. No XLSX a conclusão virou texto fixo.
- **Gás unificado nas considerações:** "Manutenção do Sistema de Gás" (Alma) e "Manutenção de Gás" (Condo21) saem
  como um item só, "Manutenção de Gás" (`_nome_na_composicao`). Berlin conferido. Só o texto muda; valores não.
- **Reajuste = texto do José, SEMPRE (usuária 29/10: "em ambos casos, sempre"):** "Caso os valores arrecadados para a
  constituição do Fundo de Reserva sejam utilizados… — prática não recomendada —, sugerimos um reajuste de X% … No
  entanto, caso os recursos do Fundo de Reserva sejam preservados…, recomendamos um reajuste de Y% … para os próximos
  12 meses." X = receitas com fundo, Y = sem fundo; percentuais só em número. Sem fundo (ex.: Berlin) X = Y (5,9% e
  5,9%); com aluguel o texto usa só as 2 opções sem aluguel (lista a)/b)/c) acabou); sem reajuste a parte diz "não é
  necessário reajuste da taxa condominial".
- No GitHub em 29/10 (5adfa30); **falta rebuild no EasyPanel** (inclui 21–26/10).

## Trabalho de 26/10/2026 — relatório em Excel com fórmulas, mesmo desenho do PDF

- **Gráfico de evolução mensal retirado dos 3 formatos** (usuária: "tire o gráfico de evolução mensal… de todos, não
  será mais preciso"), junto com o cálculo (`_fluxo_mensal_balanco`, `fluxo_mensal` no estado, SVG/PNG/série do Excel).
- **Sem espaços longos:** tirada a página nova forçada antes da Conclusão (PDF/DOCX/XLSX); assinatura presa ao último
  item (PDF `.fecho`, DOCX keep_with_next); espaçamentos do PDF apertados (pizza 180px, seções 14px). Santorini, Berlin
  e Aldeia saem em 2 páginas no PDF. No XLSX: pizza menor e alturas das considerações recalibradas (150 car./linha).

- **Terceiro formato: XLSX** (`relatorio_xlsx.py`, XlsxWriter; rota `POST /api/sessao/{sid}/relatorio-xlsx`; opção
  "Excel" no modal). Usuária: "tem que ser no MESMO design do DOCX e do PDF, o intuito é EXPORTAR". Uma aba, A4, mesma
  ordem/cores/logo do PDF, quebras antes da pizza e da conclusão; dados da pizza na aba "Dados do
  gráfico" (à direita da folha saíam na impressão do Numbers e encolhiam o relatório — usuária: "na hora de imprimir
  ficou estranho"). Contas são células; total, SUBTOTAL, aumento (% editável), TOTAL, quadro de leitura, pizza, conclusão e
  considerações de suficiência/opções são fórmulas. Fundo = `SUMIF(..,"*fundo de reserva*")` (SUMPRODUCT/SEARCH não
  calcula no Numbers). Cada fórmula leva o resultado em cache (prévia do Finder/WhatsApp mostrava R$ 0,00 com openpyxl).
- `montar_contexto_relatorio` agora expõe `valores` (números crus + índices das considerações dinâmicas).
- Conferido: Santorini e Berlin exportados pelo Numbers (gráficos e valores batem com o PDF). Numbers ignora a área de
  impressão/quebras; Excel de verdade ainda não foi aberto → conferir.
- **Rebuild do EasyPanel instala `xlsxwriter`** (novo no requirements).

## Trabalho de 23/10/2026 — feedback José 22/10 (Aldeia das Asas, vale p/ todos)

- **Considerações:** avisos de importação (mês não fechado, receita fixa baseada em, diferenças balancete × pagamentos)
  saíram do PDF/DOCX — documento vai ao condomínio. Ficam só na tela de análise.
- **Provisão eliminada 100% (pedido da usuária, 23/10):** não existe mais `prov_laudo`/`prov_incendio` no motor, API,
  PDF/DOCX, XLSX legado nem frontend. R4 mantém toda conta de Despesas Diversas na própria linha (menos extraordinários).
  No Aldeia vinha da "13º Taxa de Administração" lançada em Diversas (R$ 750); no Berlin, Contribuição Assistencial + 13ª
  (R$ 975,83). Sessões antigas se corrigem sozinhas: PDF/DOCX chama `recalcular` do cache, que descarta as chaves velhas.
- **Forte Way (áudio José 22/10):** Condo21 + Alma com lançamentos nos dois sistemas em 07 e 08/2026 (tarifa) não trava
  mais: `consolidate_balances` soma por conta, cobertura vira `condo21+alma` e a tela mostra aviso com o valor de cada
  sistema. Só no fluxo Condo21 + Alma; Group + Alma continua exigindo o mês de mudança.
  Testado com os arquivos reais (sessão `9e46c8126497`, recusada em 22/10): 08/2026 no Condo21 = só Tarifas Bancárias
  R$ 102,24; 07/2026 no Alma = receitas antecipadas + tarifa R$ 8,52. Depois disso apareceram mais 2 travas:
  - FIN Alma do Forte Way vem **sem coluna Status** (só pagas) e com **pagamento dividido** (partes sem data + linha
    "TOTAL" com data/fornecedor). `read_fin` agora aceita os dois; testes novos em `test_mixed_import.py`.
  - **Contas a receber exportado sem filtro de Data Vencimento** → recusa correta ("selecione um único mês").
    Resolvido com o **Rateio por Unidade (XLSX)**, aceito no MESMO campo do Contas a receber (um OU outro;
    `read_receivables` reconhece pelo conteúdo, `read_unit_apportionment` lê o XML direto porque o openpyxl recusa os
    estilos do arquivo). Forte Way: totais idênticos ao PDF (taxa 38.377,18; fundo 3.978,85; chamada de capital
    4.401,60 fica fora da receita ordinária). Análise completa local passou (receita ordinária R$ 42.356,03/mês).
- **Gráfico mensal + água na receita (decisão da usuária 23/10: "água é receita, sempre conta"):** a receita deixava
  de fora a água cobrada das unidades (Aldeia: Group 1.1.36 Água ≈ R$ 363 mil/ano vs despesa ≈ R$ 366 mil/ano), então
  a despesa ficava acima o ano todo e o déficit inflava. Agora `receitas_consumo` soma a água (média dos meses com
  receita) em `analisar`, `recalcular` e no fallback do balanço; a barra de receita do gráfico (PDF/DOCX) = total da
  tabela de receitas (taxa, fundo se marcado, água, recorrentes, **receitas manuais**, menos inadimplência); opções de
  custeio nomeiam as receitas ("Taxa de Condomínio + Água + …", não "Só Taxa"). Aldeia (cópia local, sem IA): receita
  R$ 123.417,79/mês, gráfico 6/12 meses com receita ≥ despesa (balancete real: 7/12), reajuste 61% → 20,0% / 11,8%.
  Santorini: água R$ 1.830,82/mês. Berlin e Forte Way sem receita de água (nada muda).
- **Gráfico redesenhado (usuária 23/10, vale p/ todos os condomínios):** diferença por mês, verde acima / vermelho abaixo, rótulos com ≈ (ver `regras.md`).
  PDF real do Aldeia (sessão `8b5d1beb366a`, com 5 receitas manuais do José) renderizado e conferido: 3 páginas.
- **Opções/quadro de leitura com nomes curtos:** "Receitas sem fundo de reserva" / "Receitas com fundo de reserva"
  (antes listava Taxa + Água + cada receita manual).
- **Conclusão + Considerações juntas numa página nova** (PDF e DOCX); antes a Conclusão ficava sozinha numa página.
  Considerações longas podem continuar na página seguinte, mas nenhum item é partido.
- **Lista de condomínios:** selo "Em revisão" retirado (só "Gerado" aparece).
- **Topo da aplicação:** logo branca (`public/assets/logo-branca.png`; azul virou branco, amarelo mantido) e botão
  branco "← Menu principal" no cabeçalho (upload e revisão), no lugar do "Voltar" cinza que não aparecia.
  `logo.png` (azul) continua sendo a do PDF — não trocar.
- **Aprendizado REMOVIDO (usuária 23/10: "só nos trouxe problema"):** memórias da revisão generalizavam
  entre condomínios (Nautillus XIV → Forte Way: PartnerBank, água Prolagos, gás CEG excluídos). `aprendizado.py`,
  gravação, aplicação e importação no startup saíram; tabela `aprendizado_despesas` ficou no banco, sem uso
  (nada apagado). Sessões já analisadas guardam o que ele marcou: Aldeia `8b5d1beb366a` 55 exclusões, Forte Way 6
  → decidir com o José (revisar na tela ou reanalisar, que perde as decisões já feitas na sessão).
  Scripts só leitura: `tmp/consultar_aprendizado.py <texto>`, `tmp/simular_aprendizado.py`.
- No GitHub em 23/10 (testes: só as 4 falhas conhecidas); **falta rebuild no EasyPanel** (inclui o trabalho de 21/10).

## Trabalho de 21/10/2026

- **Fundo de reserva "Não" no PDF:** o flag `com_fundo` só afetava o quadro de resultado. Agora também tira o fundo da tabela de
  receitas, das opções de custeio e da consideração do reajuste (`relatorio_pdf.py`, vale p/ todos os sistemas).
- **"Outras despesas" nunca é linha do relatório:** o resíduo sem categoria soma em "Gastos com conservação" (mantém o total;
  `test_itens_manuais` exige isso). Se o José quiser o valor FORA do total, a mudança é no motor.
- **Relatório em PDF ou Word (DOCX):** `relatorio_docx.py` (python-docx; gráficos como PNG via Pillow) consome
  `montar_contexto_relatorio` (contexto único PDF/DOCX). Rota `POST /api/sessao/{sid}/relatorio-docx`; modal escolhe o formato.
  DOCX nunca foi visto renderizado no Word (sem Word/LibreOffice no Mac) → conferir.
- **Tela de revisão:** removidos "pago/deduzido/dedução mensal equivalente" dos grupos e classes (confundiam o José).
- **Aldeia das Asas (sessão `0112033b4f75`, ano completo reexportado):** 42 lançamentos em revisão, todos da IA, ~R$ 40 mil;
  33 por descrição fraca (só nome do favorecido), resto reparo pontual vs rotina. Honorários (9 itens, ~R$ 16 mil) e a parte
  Fundo de Reserva (R$ 2.084,83) de extintores precisam de decisão do José — não confirmado se o fundo entra no total.
  Ideia pendente: regra de recorrência por favorecido / dar histórico do favorecido à IA.
- Acesso ao banco prod pelo agente funcionou em 21/10 (leitura via `tmp/baixar_sessao.py`) quando a usuária pediu explicitamente.
- Tudo no GitHub; **falta rebuild no EasyPanel** (instala `python-docx`; o XLSX usa openpyxl, já instalado).

## Trabalho de 19/10/2026

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

- **Inadimplência no Group sozinho (usuária, 19/10):** upload opcional "Inadimplência detalhada" (`group_inad`, coluna
  `arquivo_group_inad`), `parsers_group.parse_arrears` com a **regra do Alma**: mês do relatório = data de Emissão; unidade
  com boleto em aberto (sem Recebimento) nos 2 meses anteriores → abate o boleto inteiro mais recente (taxa+fundo+água,
  sem juros/multa; boleto só de acordo não conta). Confere total e nº de unidades (relatório não traz o nome do condomínio).
  Aldeia das Asas real (emissão 19/10): só Águia-201 deve 08 e 09 → abate R$ 690,50/mês.
  Corrigido junto: (a) item do Alma ("Boleto…") era descartado na montagem da tela pelo filtro "condom" — o abatimento
  Alma nunca chegava à tela/PDF (não apareceu porque Santorini/Berlin tinham 0 unidades); (b) última parcela Condo21
  escolhida comparando "MM/AAAA" como texto; (c) PDF forçava "inadimplência não apurada" para todo Group.

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

1. Forte Way (`9e46c8126497`): sessão preparada no banco com o Rateio; após o rebuild, abrir na lista → a aplicação
   reanalisa sozinha (IA de produção). Conferir números e `modelo_ia`.
   Reenviar Aldeia das Asas (despesas reexportadas sem filtro de competência) após o rebuild.\n   Avaliar com o José: bloquear quando as despesas detalhadas cobrem muito menos que o balancete (hoje só avisa). Se ainda acusar sobreposição, pedir os arquivos
   (o desbai06 teria pagamentos em meses que já são do Alma). Regerar PDFs (Berlin `b633bf8000b5`, Atlântico,
   Santorini) — sessões antigas mantêm o gráfico antigo até reanalisar.
2. Pedir ao José um caso real com inadimplente nos 2 últimos meses para validar o abatimento do boleto.
3. Confirmar com o José: "projetor" (refletor LED) é despesa normal? `previsao.py` CAPITAL_KW tem 'projetor' desde
   07/10 (261ec09), contrariando a correção de 05/10 (b26c1db) — são as 4 falhas de `test_classificacao_capital`.
4. Santorini: R$ 9.000 de caminhões-pipa deduzidos pela estatística precisam de validação humana.
   FIN do Alma não traz tarifas bancárias (aviso de diferença aparece; o demonstrativo Alma cobre).
5. Segurança: revisar credenciais do banco e autenticação da API (pendência registrada fora do repo).

## Arquivos locais (fora do git)

`tmp/` (backups de prod, ex.: substituição Berlin 13/10 com manifest SHA-256), `output/`, `outputs/`
(PDF/CSV de conferência Santorini). Contêm dados de clientes — nunca commitar.
