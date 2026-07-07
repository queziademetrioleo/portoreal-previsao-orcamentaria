# 🏢 Previsão Orçamentária — Porto Real Imóveis

**Sistema inteligente de previsão orçamentária para condomínios.**  
Lê os relatórios do Condomínio21 (Group Software), aplica regras de negócio aprendidas de anos de cálculos manuais, usa **IA (Claude Opus)** para classificar cada nota fiscal, e gera o documento final com revisão humana antes da conclusão.

<p align="center">
  <img src="webapp/frontend/public/assets/logo.png" alt="Porto Real" height="80">
</p>

---

## 🎯 O que o sistema faz

```
Relatórios .xls  →  IA lê e entende  →  Aplica regras R1–R8  →  Humano revisa  →  Previsão.xlsx
(Condomínio21)     (Claude Opus 4.8)     (cálculo determinístico)   (interface web)   (documento final)
```

1. **Upload** de 4 arquivos exportados do Condomínio21: `balanual.xls`, `desbai06.xls`, `dessin02.xls`, `inad01.xls`
2. **IA analisa** cada nota fiscal do desbai06, classificando como *Recorrente* ou *Extraordinária*
3. **Regras determinísticas** (R1 a R8) são aplicadas — deduções, provisões, anualizações
4. **Revisão humana** na interface web: o síndico aprova ou reprova cada item classificado
5. **Documento final** gerado com a mesma estrutura do manual da Porto Real

---

## 🧠 Regras de cálculo (R1–R8)

Aprendidas por engenharia reversa dos arquivos `Previsão 20XX.xlsx` manuais (2022–2026, 4 condomínios):

| Regra | Descrição |
|-------|-----------|
| **R1** | Obras/Benfeitorias → desconsideradas integralmente |
| **R2** | Rescisão, indenização trabalhista, pensão alimentícia → deduz 100% |
| **R3** | Manutenções "lumpy" (pintura, portão, elétrica…) → deduz NFs extraordinárias identificadas pela IA |
| **R4** | Despesas Diversas (exceto Seguro) → zeradas e realocadas como provisão para Laudo de Autovistoria |
| **R5** | Cartoriais e Honorários → zerados e realocados como provisão para Sistema de Incêndio/Registro |
| **R6** | Contratos, pró-labore, taxa de administração → último valor mensal × 12 (anualização) |
| **R7** | Inflação → +10% sobre o subtotal (percentual editável na interface de revisão) |
| **R8** | Inadimplência ≥ 3 meses consecutivos → abate a taxa do devedor da receita (não é despesa) |

> **Importante**: a IA **sugere** a classificação das NFs ambíguas — **quem decide é o humano** na interface de revisão.  
> A aritmética é 100% determinística e auditável.

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
│   │   ├── main.py          # API FastAPI (upload → análise → revisão → download)
│   │   ├── gerador_previsao.py  # Gera Previsão.xlsx (layout adaptativo)
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

### 3. Download
Clique em **Salvar** — o sistema recalcula com suas decisões e gera o `Previsão <ano>.xlsx` final.

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
- **Geração**: openpyxl (arquivos .xlsx)
- **Deploy**: Docker + Docker Compose → EasyPanel / VPS

---

## 📝 Licença

Sistema desenvolvido para a **Porto Real Imóveis (V.H.R. Empreendimentos)**.  
Uso interno — todos os direitos reservados.
