---
name: r4-r5-provisoes
description: Como R4 e R5 realocam gastos genéricos para provisões obrigatórias (Laudo e SCIP) sem alterar o total
metadata: 
  node_type: memory
  type: reference
  originSessionId: f8450791-7b60-4ea7-a33d-7130d60e5880
---

# R4 e R5 — Como gastos genéricos viram provisões obrigatórias (sem mexer no total)

---

## R4 — Despesas Diversas vira Provisão para Laudo de Autovistoria Predial

### O problema

O orçamento tem uma categoria chamada "Despesas Diversas" com R$ 57.406,71. Dentro dela tem de tudo:

```
Reparo no Elevador        R$  9.383,75   ✅ Mantido
Seguro Incêndio           R$ 10.666,65   ✅ Mantido
Conserto de Bomba         R$  1.510,00   ✅ Mantido
Outras Despesas           R$ 35.846,31   ❌ ZERADO
────────────────────────────────────────
Total:                    R$ 57.406,71
```

**Pergunta**: Isso tudo é mesmo "diverso"? Ou tem coisa aí que não deveria estar nesse balde?

Reparo de elevador é **manutenção** — vai acontecer de novo. Seguro incêndio é **obrigatório por lei** e se repete todo ano. Conserto de bomba é **reparo**, mesma lógica.

Mas **"Outras Despesas"** é a gaveta de bagunça do orçamento. É onde vai parar tudo que não se encaixa em lugar nenhum: uma taxa aqui, um gasto pontual ali, uma despesa que aconteceu uma vez e nunca mais. Não faz sentido prever R$ 35 mil em "gastos aleatórios que a gente nem sabe o que são".

### O que a regra faz

A R4 zera "Outras Despesas" (R$ 35.846,31) e cria uma **provisão de Laudo de Autovistoria Predial** com o mesmo valor.

> Laudo de Autovistoria Predial é uma vistoria técnica obrigatória que todo condomínio precisa fazer periodicamente para verificar as condições de segurança do prédio. É caro, é obrigatório, e todo mundo sabe que vai ter que pagar — mas ninguém lembra de colocar no orçamento.

```
ANTES:
  Despesas Diversas ─────── R$ 57.406,71
    ├── Reparo Elevador     R$  9.383,75
    ├── Seguro Incêndio     R$ 10.666,65
    ├── Conserto Bomba      R$  1.510,00
    └── Outras Despesas     R$ 35.846,31  ← balde de "qualquer coisa"

DEPOIS:
  Despesas Diversas ─────── R$ 21.560,40
    ├── Reparo Elevador     R$  9.383,75
    ├── Seguro Incêndio     R$ 10.666,65
    └── Conserto Bomba      R$  1.510,00

  ⚠️ NOVO: Provisão Laudo ─ R$ 35.846,31  ← gasto de verdade, obrigatório
```

### Impacto no total: ZERO

```
Total ANTES:  R$ 57.406,71 (Despesas Diversas)
Total DEPOIS: R$ 21.560,40 (Despesas Diversas)
             + R$ 35.846,31 (Provisão Laudo)
             = R$ 57.406,71 ✅ Mesmo valor
```

É como pegar R$ 35.846 de um envelope chamado "Bagunça" e colocar em outro chamado "Vistoria Obrigatória do Prédio". O total de dinheiro no orçamento não muda — só muda de lugar.

---

## R5 — Despesas Cartoriais e Honorários vira Provisão de SCIP

### O problema

"Despesas Cartoriais e Honorários" tem R$ 2.287,09. É uma categoria de gastos que ninguém sabe direito quando vai acontecer:

```
Honorários Advocatícios     R$   600,00   ❌ ZERADO
Custas Judiciais            R$ 1.250,38   ❌ ZERADO
Despesas Cartório           R$   436,71   ❌ ZERADO
────────────────────────────────────────
Total:                      R$ 2.287,09
```

Condomínio raramente está no tribunal. Gastar com advogado e cartório todo ano não é previsível. Um ano pode ter uma ação, no ano seguinte nada. Colocar R$ 2.287 num orçamento de "custas judiciais" é chute — pode sobrar tudo ou faltar tudo.

### O que a regra faz

A R5 zera **tudo** (R$ 2.287,09) e cria uma **provisão para SCIP** (Sistema de Combate a Incêndio / Registro da Convenção) com o mesmo valor.

> SCIP é o Sistema de Combate a Incêndio do prédio — extintores, mangueiras, alarmes, tudo que é exigido pelo Corpo de Bombeiros. Precisa ser vistoriado, recarregado, mantido. E o Registro da Convenção é a documentação do condomínio no cartório de imóveis. São gastos obrigatórios que todo condomínio tem, mas que frequentemente são esquecidos no orçamento.

```
ANTES:
  Despesas Cartoriais e Honorários ─ R$ 2.287,09
    ├── Honorários Advocatícios      R$   600,00
    ├── Custas Judiciais             R$ 1.250,38
    └── Despesas Cartório            R$   436,71

DEPOIS:
  Despesas Cartoriais e Honorários ─ R$     0,00  (categoria some)

  ⚠️ NOVO: Provisão SCIP ─────────── R$ 2.287,09  ← gasto obrigatório
```

### Impacto no total: ZERO

```
Total ANTES:  R$ 2.287,09 (Cartoriais e Honorários)
Total DEPOIS: R$     0,00 (Cartoriais e Honorários)
             + R$ 2.287,09 (Provisão SCIP)
             = R$ 2.287,09 ✅ Mesmo valor
```

---

## A lógica por trás das duas regras

R4 e R5 fazem a mesma coisa com categorias diferentes: **tirar dinheiro de gastos genéricos/imprevisíveis e colocar em provisões obrigatórias**.

### O fio condutor

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   "Outras Despesas" (R$ 35.846)                         │
│   "Honorários / Custas" (R$ 2.287)                      │
│         │                                                │
│         ▼                                                │
│   São gastos que:                                        │
│   • Não se repetem todo ano                             │
│   • São imprevisíveis                                   │
│   • Não têm obrigatoriedade legal                       │
│         │                                                │
│         ▼                                                │
│   Em vez de chutar, o sistema REALOCA:                  │
│         │                                                │
│         ├──→ R$ 35.846 → Provisão Laudo (obrigatório)   │
│         └──→ R$ 2.287  → Provisão SCIP (obrigatório)     │
│                                                         │
│   Resultado: orçamento mais honesto, mesmo total.       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### A diferença entre elas

| Característica | R4 | R5 |
|---|---|---|
| Categoria origem | Despesas Diversas | Cartoriais e Honorários |
| O que é zerado | Só "Outras Despesas" (itens de manutenção/seguro ficam) | Tudo |
| Provisão criada | Laudo de Autovistoria Predial | SCIP (Sistema Combate Incêndio) |
| Valor (Chateau 2026) | R$ 35.846,31 | R$ 2.287,09 |

### Regra de ouro: o que NÃO é zerado no "Diversas"

A R4 só mexe no genérico. Se dentro de "Despesas Diversas" tem itens que são claramente **manutenção, reparo, conserto, seguro, ou qualquer gasto com cara de recorrente**, eles ficam. O filtro é:

```
❌ ZERADO (vai para provisão):
   Outras Despesas, Diversos, Diversas Despesas,
   Gastos Gerais — qualquer descrição genérica

✅ MANTIDO (fica na base):
   Reparo de... — Reparo no Elevador, Reparo Hidráulico
   Conserto de... — Conserto de Bomba
   Manutenção de... — Manutenção de Portão
   Seguro... — Seguro Incêndio, Seguro do Prédio
```

---

## O que pode dar errado

### 1. Alguém colocar gasto importante dentro de "Outras Despesas"

Se o síndico registrar um gasto essencial (ex.: "Manutenção de Extintores") com a descrição genérica "Outras Despesas" na nota fiscal, o sistema vai zerar e realocar. Aí o gasto real some do orçamento e vira provisão.

**Como evitar**: classificar corretamente as notas fiscais. Se é manutenção, coloca na categoria de manutenção. Só sobra no "Diversas" o que realmente não tem onde colocar.

### 2. Superdimensionar a provisão

R$ 35.846 de Laudo pode ser mais ou menos que o custo real. Se for mais, o condomínio acumulou provisão demais. Se for menos, vai precisar complementar.

**Como evitar**: revisar a provisão anualmente com base no custo real do último laudo. A regra é um ponto de partida, não um valor definitivo.

### 3. Gastos cartoriais reais não sumirem

Se o condomínio realmente processar alguém ou precisar de cartório no ano, o dinheiro da provisão de SCIP foi usado para outra coisa. Aí o condomínio precisa de um orçamento suplementar.

**Como evitar**: avaliar se o condomínio tem histórico de ações judiciais. Se sim, talvez faça sentido manter uma reserva separada para custas. A R5 é conservadora — prefere provisionar algo obrigatório a chutar gasto judicial.

### 4. Itens de manutenção serem incorretamente zerados

Se o sistema classificar errado um "Conserto de Portão" como "gasto genérico" e zerar, o orçamento perde um gasto real de manutenção.

**Como evitar**: a R4 já protege isso — ela só mexe no item chamado "Outras Despesas" dentro da categoria Diversas. Itens com descrição específica de reparo são preservados. Mas é bom revisar a classificação manualmente.

---

## Resumo em uma frase

> R4 e R5 são a mesma ideia com categorias diferentes: em vez de deixar dinheiro parado em "gastos genéricos que talvez não aconteçam" (Outras Despesas, Honorários, Custas), o sistema realoca esse dinheiro para provisões de gastos **obrigatórios que todo condomínio tem** (Laudo de Autovistoria e SCIP) — o total do orçamento não muda, mas ele fica mais honesto e mais útil.
