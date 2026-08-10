# Projeto — Previsão Orçamentária de Condomínios

> Status atualizado em 10/08/2026. Repositório: `~/PrevisaoOrcamentaria`,
> branch `main`, remoto `queziademetrioleo/portoreal-previsao-orcamentaria`.

## Propósito

Webapp interno da Porto Real Imóveis / V.H.R. que transforma relatórios do
Condomínio21 em uma previsão orçamentária anual auditável. A IA ajuda a
classificar lançamentos ambíguos; as decisões financeiras e a aritmética ficam
nas regras determinísticas e na revisão humana.

Fluxo: upload dos relatórios `.xls` → análise R1–R8 + IA opcional → revisão
humana → planilha `Previsão.xlsx` e relatório PDF para o condomínio.

## Stack e operação

- **Backend:** Python 3.12, FastAPI e Uvicorn.
- **Frontend:** React 19, TypeScript e Vite.
- **Dados:** MySQL 8, com sessões, arquivos enviados e documentos gerados
  persistidos no banco.
- **Processamento:** `xlrd` para `.xls` legados, `openpyxl` para `.xlsx`,
  WeasyPrint/Jinja2 para PDF.
- **IA:** Anthropic como provedor preferencial e OpenAI como fallback; se os
  provedores falharem, o cálculo continua somente com regras.
- **Deploy:** Docker multi-stage (`webapp/Dockerfile`) + Docker Compose
  (`docker-compose.yml`); produção no EasyPanel/VPS, porta `8000`.

Variáveis relevantes: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`PREVISAO_IA_PROVEDOR`, `PREVISAO_IA_MODELO`, `PREVISAO_IA_MODELO_OPENAI` e
as variáveis `MYSQL_*`. Em desenvolvimento, backend em `:8000` e Vite em
`:5173`; em produção, o FastAPI serve o build estático do frontend.

## Arquivos-chave

- `previsao.py` — núcleo de parsers, regras R1–R9, IA e cálculo de receita /
  inadimplência; é a referência da lógica financeira.
- `ia_parser.py` — parsing assistido por IA, com fallback de código.
- `webapp/backend/main.py` — API, ciclo de sessão, reanálise, preview, geração
  de XLSX e entrega do PDF.
- `webapp/backend/gerador_previsao.py` — gera a planilha final de estrutura
  adaptativa.
- `webapp/backend/relatorio_pdf.py` — relatório entregue ao condomínio.
- `webapp/backend/db.py` — persistência MySQL.
- `webapp/frontend/src/components/TelaRevisao.tsx` — decisões humanas e
  cenários com/sem fundo de reserva.
- `webapp/frontend/src/components/TelaResultado.tsx` — resultado, downloads e
  seleção do cenário exibido.
- `webapp/frontend/src/api.ts` — cliente da API e URL parametrizada do PDF.
- `README.md` — operação, formato dos arquivos e visão do produto.

## Convenções que não podem regredir

- A IA classifica; o humano confirma; os números são determinísticos e
  auditáveis.
- Valores monetários precisam declarar **mensal** ou **anual** quando o
  contexto não os tornar inequívocos.
- A recomendação de reajuste mira a margem de segurança do sistema, nunca
  apenas o ponto de equilíbrio: superávit mínimo de R$ 2.000/mês
  (R$ 24.000/ano).
- Inadimplência crítica (3+ meses consecutivos) é risco de **receita**, não
  despesa. O abatimento é uma única taxa mensal da unidade inadimplente — não
  se multiplica pelo número de parcelas vencidas.
- Fundo de Reserva é um cenário: qualquer tela, XLSX ou PDF precisa respeitar
  a escolha atual **com fundo** / **sem fundo**, sem dupla contagem.
- Sessões são permanentes. Não restaurar limpeza automática por TTL no startup;
  `Recalcular` deve reanalisar os arquivos originais do zero, não só refazer
  preview de um estado antigo.

## Correções em três fases

### Fase 1 — precisão do PDF e clareza da interface (09–10/07)

Foram corrigidos o PDF e as telas para que leitura e cálculo coincidam:

- Quadro do PDF passou a usar valores mensais coerentes, numeração contínua
  das considerações e histórico real de meses analisados.
- A sugestão de reajuste passou a considerar a margem mínima de segurança.
- Rótulos anual/mensal foram explicitados; o tooltip Base − Dedução = Final foi
  reescrito em linguagem operacional.
- A aba técnica “Memória” foi removida do resultado; “Decisões” virou
  “Explicação das Despesas Extraordinárias”.

### Fase 2 — persistência e cenários de cálculo (10/08, início)

- Nome do condomínio é extraído do REC; a interface mostra a última parcela de
  inadimplência e oferece `Recalcular` imediato.
- O Fundo de Reserva entra no fallback do resultado e ganhou seleção com/sem
  fundo na revisão.
- A retenção de sessões subiu de 7 para 90 dias e, em seguida, a limpeza no
  startup foi removida: deploy não pode apagar previsões antigas.
- `POST /api/sessao/{sid}/reanalisar` refaz análise completa (regras + IA) a
  partir dos arquivos já enviados e substitui o antigo recálculo superficial.

### Fase 3 — consistência final de Fundo, PDF e inadimplência (10/08, hoje)

- “Previsão de inflação” foi renomeada para **“Aumento Previsto (Salários,
  tarifas, serviços) = X%”** no XLSX, fallback do relatório e revisão.
- O cenário sem fundo passou a usar a receita do cenário ativo; o fallback não
  duplica Fundo de Reserva e a aba PREVISÃO (2) recebe também o novo rótulo.
- O PDF passou a separar despesas em **SUBTOTAL → Aumento Previsto → TOTAL**,
  a exibir inadimplência como dedução de receita e a respeitar o cenário
  selecionado no quadro de leitura.
- O endpoint do PDF aceita `?com_fundo=0|1`; o link da tela envia o estado do
  toggle, impedindo que o PDF ignore a escolha feita no resultado.
- A correção financeira final limita o impacto da inadimplência à última taxa
  mensal da unidade (`tx_media`), sem multiplicá-la pela sequência em atraso.

Commits principais desta fase: `9f76f4f`, `6c2d81c`, `15aff0a`, `6e88d96`,
`4a04a49` e `620a34b`.

## Última sessão e próximo passo

A última sessão consolidou as correções de 10/08 e deixou o código em `main`;
há apenas o registro local não rastreado `previsao orçamentária.md`, que não
faz parte da aplicação. O próximo passo operacional é **Rebuild pendente no
EasyPanel, preferencialmente sem cache**, e a confirmação visual do PDF nos
dois cenários (com e sem Fundo de Reserva). Isso é necessário porque houve
precedente de o painel manter imagem antiga após deploy, apesar de o código
estar correto no repositório.
