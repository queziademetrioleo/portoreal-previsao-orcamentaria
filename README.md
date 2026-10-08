# 🏢 Previsão Orçamentária — Porto Real Imóveis

**Sistema inteligente de previsão orçamentária para condomínios.**  
Lê os relatórios do Condomínio21 (Group Software) e do Alma durante a migração, aplica regras de negócio aprendidas de anos de cálculos manuais, usa IA para classificar cada nota fiscal, e gera o relatório PDF após a revisão humana.

<p align="center">
  <img src="webapp/frontend/public/assets/logo.png" alt="Porto Real" height="80">
</p>

---

## 🎯 O que o sistema faz

```
Relatórios .xls  →  IA lê e entende  →  Aplica regras R1–R8  →  Humano revisa  →  PDF
(Condomínio21)     (Claude Opus 4.8)     (cálculo determinístico)   (interface web)   (relatório final)
```

1. **Upload** de 5 arquivos exportados do Condomínio21: `balanual.xls`, `desbai06.xls`, `rec02.xls` (obrigatórios), `dessin02.xls`, `inad01.xls` (opcionais)
2. **IA analisa** cada nota fiscal do desbai06, classificando como *Recorrente* ou *Extraordinária*
3. **Regras determinísticas** (R1 a R8) são aplicadas — deduções, provisões, anualizações
4. **Revisão humana** na interface web: o síndico aprova ou reprova cada item classificado
5. **Relatório em PDF** para entrega ao condomínio, com logo, receitas/despesas, quadro comparativo com/sem fundo de reserva, gráficos e as Considerações Importantes (item de reajuste sugerido calculado automaticamente)

---

## Seleção de sistemas

Na tela **Nova previsão**, marque **Condo21**, **Alma** e/ou **Group**. Pode
selecionar somente um ou combinar os sistemas usados pelo condomínio. Cada
seleção abre seus próprios campos de upload; arquivos de sistemas desmarcados
não são enviados. As seleções e os arquivos ficam preservados para reanálise.

Na combinação, cada mês deve ser coberto por uma única fonte. Sobreposições e
lacunas são recusadas antes de salvar a sessão. A receita fixa usa o relatório
de competência mais recente entre as fontes. O período pode ser escolhido na
tela; meses futuros zerados de Condo21/Group não completam cobertura no uso
conjunto. O leitor de cada plataforma extrai os valores antes da classificação
por IA, preservando a estrutura das contas.

No Alma isolado, o PDF de inadimplência pode agregar taxa, fundo e consumo. Se
não houver uma fonte legível de taxa por unidade, o sistema informa que o
abatimento não foi apurado, sem presumir inexistência de débitos. No uso
conjunto, as receitas por unidade Condo21/Group fornecem a taxa para a regra dos
dois últimos meses Alma. O fluxo Condo21 + Alma existente mantém suas regras.

## Upload Group

Na tela **Nova previsão**, selecione **Group** e envie os três XLSX exportados:

- **Balancete anual**: 12 meses consecutivos, com classes de conta e totais.
- **Despesas detalhadas por classe de conta**: pagamentos do mesmo período.
- **Receitas detalhadas por unidade/cliente**: competência mais recente disponível.

O leitor identifica as colunas pelos cabeçalhos e concilia pagamentos com o
balancete por código de conta e mês de pagamento. Usa o valor cobrado da taxa
condominial e do fundo de reserva, excluindo cobranças marcadas como
**Excluída**. O resumo do relatório pode incluir essas cobranças; por isso a
projeção lê os lançamentos das unidades e não soma novamente os subtotais.
Receitas de fornecedores não entram na cobrança fixa das unidades.

Meses não fechados, meses zerados, diferenças na conciliação e competência da
receita anterior ao fim do balancete aparecem na revisão. As limitações de
cobertura e da referência da receita também aparecem nas considerações do PDF.
Sem relatório específico de inadimplência Group, **não há abatimento calculado
por débitos**, nem declaração de ausência de inadimplência.

As sessões preservam os XLSX e a origem Group para reanálise, com colunas
dedicadas no banco adicionadas automaticamente pelo bootstrap. Sessões Group
criadas pelo formulário anterior continuam compatíveis. Os formatos exclusivos Condo21 e misto
Condo21 + Alma continuam com seus leitores próprios.

Testes locais com os exemplos privados: defina `GROUP_SAMPLE_DIR` para a pasta
dos arquivos Berlin e execute os testes `test_group_import` e `test_group_upload`
com a raiz e `webapp/backend` em `PYTHONPATH`. Os XLSX privados não são versionados.

## Upload conjunto Condo21 + Alma

Na tela **Nova previsão**, marque **Condo21** e **Alma**. Além dos relatórios Condo21, envie:

- Demonstrativo por período agrupado por contas do Alma: PDF.
- FIN00601 de despesas detalhadas: XLSX.
- Contas a receber agrupado por conta: PDF, com um único mês de vencimento.
- Inadimplência Alma: PDF; se não houver, marque **Não há inadimplência no Alma**.

O período de despesas pode ser escolhido por mês ou identificado automaticamente. Os pagamentos do FIN são selecionados pela **Data Pagto**. Meses com movimentação nas duas fontes ou sem cobertura são recusados para evitar duplicidade e lacunas. Meses futuros zerados do balanual Condo21 permitem cobertura pelo Alma.

O plano de contas fornecido pela Porto Real é contexto interno do sistema, versionado em `data/plano_contas_alma.json`; não precisa ser enviado em cada previsão. Ele associa classes aos grupos, inclusive classes novas. Pagamentos sem correspondência no demonstrativo permanecem na revisão; diferenças entre demonstrativo e pagamentos aparecem na tela, sem criar notas fictícias.

**Somente no uso conjunto:** a inadimplência considera os dois últimos meses da referência do relatório Alma, independentemente do período de despesas. Para cada unidade, entra a última taxa condominial vencida nesse intervalo. Se não houver títulos no intervalo ou não houver inadimplência Alma, o impacto é zero; o histórico Condo21 não é recuperado. Como o PDF Alma agrega taxa, fundo e consumo, a taxa por unidade é identificada no REC Condo21; divergência com a cobrança agregada atual é avisada para conferência.

Os arquivos de ambas as fontes e a seleção do período ficam salvos na sessão, inclusive para reanálise. O banco recebe as colunas necessárias automaticamente na inicialização do backend. O fluxo exclusivo Condo21 mantém sua regra de inadimplência existente.

## 🧠 Regras de cálculo (R1–R8)

A seção **Despesas** do PDF usa categorias consolidadas em ordem fixa. Classes
de pessoal e manutenção não aparecem soltas no fim da tabela; contratos
identificados pelo nome ficam juntos, mesmo que o grupo original seja genérico.
Nomes cortados só são completados quando há correspondência inequívoca; valores
homônimos são somados sem excluir pagamentos apenas porque têm o mesmo valor.
Tabela, gráfico e textos de composição usam a mesma classificação de apresentação.

Regra permanente de apresentação: nunca citar a **13ª taxa de administração** no texto de composição de **Despesas Administrativas** do relatório entregue ao condomínio. Seu valor permanece no cálculo e no total da categoria; a omissão é somente da menção textual.

Aprendidas por engenharia reversa dos arquivos `Previsão 20XX.xlsx` manuais (2022–2026, 4 condomínios):

| Regra | Descrição |
|-------|-----------|
| **R1** | Obras/Benfeitorias → desconsideradas integralmente |
| **R2** | Rescisão, indenização trabalhista, pensão alimentícia → deduz 100% |
| **R3** | Manutenções "lumpy" (pintura, portão, elétrica…) → deduz NFs extraordinárias identificadas pela IA |
| **R4** | Despesas Diversas (exceto Seguro) → provisão para Laudo de Autovistoria (cálculo interno; no documento final aparece somada em Conservação, sem linha própria) |
| **R5** | Cartoriais e Honorários → provisão para Sistema de Incêndio/Registro (idem — absorvida em Conservação no documento) |
| **R6** | Contratos, pró-labore, taxa de administração → último valor mensal × 12 (anualização) |
| **R7** | Inflação → +10% sobre o subtotal (percentual editável na interface de revisão) |
| **R8** | Inadimplência ≥ 3 meses consecutivos → abate a taxa do devedor da receita (não é despesa) |
| **R9** | Superávit ≥ R$2.000 → confortável; entre R$0 e R$1.999 → superávit insuficiente (alerta no documento e na interface); < R$0 → déficit |

> **Importante**: a IA **sugere** a classificação das NFs ambíguas — **quem decide é o humano** na interface de revisão.  
> A aritmética é 100% determinística e auditável.

---

## 💰 Receita: REC + balanual (híbrido)

Desde 07/2026 a receita anual usa duas fontes, cada uma no que faz melhor (validado contra previsões manuais reais):

| Origem | O que fornece | Por quê |
|--------|---------------|---------|
| **REC** (`rec02.xls` — Demonstrativo de Receitas por Unidade) | Taxa de Condomínio + Fundo de Reserva, do mês mais recente × 12 | Cobrança fixa mensal — o mês mais recente reflete a taxa vigente (reajustes) melhor que uma média anual |
| **Balanual** | Água, Gás, Luz, TV, Internet — mantém o valor bruto observado, sem extrapolar contas parciais | Repasse de consumo, varia mês a mês; contas que só aparecem em parte do ano (ex.: uma cota extra) não são projetadas como se repetissem todo mês |

Se o REC não for enviado, o sistema usa o balanual para tudo (comportamento anterior) — mas o upload do REC é obrigatório no fluxo normal do webapp.

---

## 🤖 Estratégia de IA

O sistema usa **Claude Opus 4.8** (Anthropic) como motor principal, com **GPT-5.4** (OpenAI) como fallback automático.

### Onde a IA atua

| Etapa | Responsável | Descrição |
|-------|-------------|-----------|
| **Parse dos .xls** | IA (fallback: código) | Lê os dados brutos e extrai estrutura (contas, grupos, valores mensais) |
| **Classificação NF por NF** | IA | Analisa cada nota fiscal do desbai06 e classifica como Recorrente ou Extraordinária |
| **Mapeamento de contas** | IA (fallback: nome) | Mapeia semanticamente as contas do balanual para a estrutura de saída |
| **Aritmética R1–R8** | **Código (determinístico)** | Cálculo exato, sem IA — auditável e reversível |

### Por que IA + código?

- **IA** resolve o que é semântico e variável: cada condomínio tem nomes de contas, grupos e estruturas diferentes
- **Código** resolve o que é determinístico: as regras R1–R8 são aritmética pura, não dependem de interpretação
- **Sem templates fixos**: o sistema se adapta automaticamente a qualquer condomínio

---

## 🚀 Deploy

### Pré-requisitos

- Docker + Docker Compose
- Chave da API Anthropic ([console.anthropic.com](https://console.anthropic.com))
- Chave da API OpenAI ([platform.openai.com](https://platform.openai.com)) — opcional, para fallback

### Quick start

```bash
git clone https://github.com/queziademetrioleo/portoreal-previsao-orcamentaria.git
cd portoreal-previsao-orcamentaria

# Configurar chaves
cp .env.example .env
# Edite .env com suas chaves de API

docker compose up -d --build
# Acesse http://localhost:8000
```

### EasyPanel

1. Conecte o repositório GitHub no EasyPanel
2. Configure as variáveis de ambiente (`.env.example`)
3. Aponte o Dockerfile: `webapp/Dockerfile`
4. Exponha a porta `8000`

Para usar somente OpenAI com GPT-6.1 Sol e raciocínio alto, configure no
serviço do EasyPanel (ou no `.env` do Docker Compose):

```env
OPENAI_API_KEY=sua-chave
PREVISAO_IA_PROVEDOR=openai
PREVISAO_IA_MODELO_OPENAI=gpt-6.1-sol
PREVISAO_IA_REASONING_EFFORT=high
```

Faça o deploy depois de salvar as variáveis. O provedor explícito impede
fallback para Anthropic, inclusive no parser. `high` é o padrão para modelos
OpenAI de raciocínio; modelos legados como GPT-4.1 não recebem esse parâmetro.
O limite de resposta reserva mais 16.384 tokens para raciocínio. Os logs
registram modelo, esforço e consumo de tokens sem registrar chaves ou documentos.

---

## 🏗️ Estrutura do projeto

```
.
├── previsao.py              # Core: parsers, regras R1-R8, IA, classificador
├── ia_parser.py             # IA-powered parsing (substitui parsers rígidos)
├── docker-compose.yml       # Deploy com Docker
├── .env.example             # Modelo de variáveis de ambiente
├── webapp/
│   ├── Dockerfile           # Build multi-stage (frontend + backend)
│   ├── backend/
│   │   ├── main.py          # API FastAPI (upload → análise → revisão → PDF)
│   │   ├── relatorio_pdf.py # Gera o relatório PDF
│   │   └── requirements.txt
│   └── frontend/
│       ├── src/
│       │   ├── App.tsx      # Interface React (upload + revisão)
│       │   ├── App.css      # Estilos (tema Porto Real)
│       │   └── api.ts       # Cliente HTTP
│       └── public/
│           └── assets/
│               └── logo.png # Logo Porto Real
```

---

## 🔄 Fluxo de uso

### 1. Upload
Preencha o nome do condomínio, ano da previsão e faça upload dos 4 arquivos:
- `balanual.xls` — Demonstrativo anual de receitas e despesas *(obrigatório)*
- `desbai06.xls` — Despesas por grupo e classe, nota fiscal por nota fiscal *(obrigatório)*
- `dessin02.xls` — Sintético de despesas *(opcional)*
- `inad01.xls` — Inadimplência *(opcional)*

### 2. Revisão
Três seções para decisão humana:
- 🔴 **Extraordinárias**: já marcadas para remoção — *reprove* para manter na base
- 🟡 **Em revisão**: itens ambíguos — marque *é extraordinária* ou *é recorrente*
- 💸 **Inadimplência**: unidades com ≥ 3 meses consecutivos — *abater* ou *ignorar*

### 3. Gerar relatório
Clique em **Gerar documento**, confirme o percentual de aumento, o último reajuste e a opção de Fundo de Reserva. O sistema recalcula com essas decisões e baixa o PDF automaticamente.

---

## 📊 Validação

Testado contra os manuais da Quezia (2022–2026, 4 condomínios):

| Condomínio | Subtotal auto vs manual | Status |
|------------|--------------------------|--------|
| Chateau Lavoisier 2025 | R$539.944 vs R$540.552 (−0,1%) | ✅ Meta ≤R$1.000 |
| Barramares 2026 | R$235.942 vs R$230.991 (+2,1%) | ⚠️ Em ajuste |
| Sophia I 2026 | R$334.134 vs manual (+1,5%) | ✅ |
| Rive Gauche I 2026 | — (+6,6%) | ⚠️ |

**Meta de precisão**: diferença ≤ R$1.000 entre o cálculo automático e o manual.

---

## 🛠️ Stack

- **Backend**: Python 3.12 + FastAPI + Uvicorn
- **Frontend**: React 19 + TypeScript + Vite
- **IA**: Claude API (Anthropic) + OpenAI (fallback)
- **Parsing**: xlrd (arquivos .xls legados)
- **Geração**: openpyxl (arquivos .xlsx) + WeasyPrint/Jinja2 (relatório .pdf)
- **Deploy**: Docker + Docker Compose → EasyPanel / VPS

---

## 📝 Licença

Sistema desenvolvido para a **Porto Real Imóveis (V.H.R. Empreendimentos)**.  
Uso interno — todos os direitos reservados.
