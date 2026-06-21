---
name: r2-pessoal-pontual
description: Como a R2 identifica eventos pontuais de pessoal (rescisão, indenização) e os separa da folha recorrente
metadata: 
  node_type: memory
  type: reference
  originSessionId: f8450791-7b60-4ea7-a33d-7130d60e5880
---

# R2 — Como o sistema separa gastos pontuais de pessoal da folha normal

## O problema

No Chateau Lavoisier 2026, o grupo **"Despesas com Pessoal"** soma **R$ 286.407,47**. Olhando cada item:

```
Salário Empregado(s)                R$ 143.029,00  ← recorrente todo mês
INSS/IRRF/Pis/Cofins/CSLL          R$  69.460,17  ← recorrente (encargos)
13º Salário                         R$  12.881,00  ← recorrente todo ano
Férias                              R$  19.543,17  ← recorrente todo ano
FGTS                                R$  16.424,30  ← recorrente (8% do salário)
Vale Transporte                     R$   5.550,00  ← recorrente todo mês
Pensão Alimentícia                  R$  13.042,19  ← 14 meses de gasto → RECORRENTE
INSS S/13. Salário                  R$   5.338,68  ← recorrente todo ano
Consult., Medicina e Seg. Trabalho  R$     810,00  ← recorrente todo ano
Contribuição Assistencial           R$     328,96  ← recorrente todo ano
```

Tudo parece recorrente... mas e se no meio disso tivesse aparecido uma **rescisão** ou uma **indenização trabalhista**?

Pergunta: se um funcionário foi demitido em agosto e pagamos uma rescisão de R$ 15.000, esse valor vai se repetir no ano que vem? **Claro que não.** A mesma pessoa não pode ser demitida duas vezes. É um evento único, pontual.

---

## A regra R2 em uma frase

> **Rescisão, indenização trabalhista e pensão alimentícia sem histórico são deduzidos 100% da base. Mas pensão alimentícia com 6+ meses de ocorrência vira recorrente.**

---

## Quando algo é "pontual" vs. "recorrente"

O sistema não adivinha — ele usa **critérios objetivos**:

| Item | O que é | Regra R2 |
|---|---|---|
| **Rescisão** | Pagamento quando um funcionário sai (aviso prévio, multa FGTS, saldo de salário) | **Pontual** — deduz 100%. A pessoa já saiu, não sai de novo. |
| **Indenização Trabalhista** | Acordo judicial ou extrajudicial com ex-funcionário | **Pontual** — deduz 100%. É um acordo único, não recorrente. |
| **Pensão Alimentícia (poucos meses)** | Desconto em folha determinado por decisão judicial recente | **Pontual** — precisa de revisão manual. Pode ser novo ou temporário. |
| **Pensão Alimentícia (6+ meses)** | Desconto em folha consolidado, com histórico longo | **Recorrente** — permanece na base. É uma obrigação contínua. |

### Exemplo visual da decisão

```
VALOR APARECEU NA PLANILHA?
         │
         ▼
┌─────────────────────────────────┐
│ É rescisão ou indenização?      │
└─────────────────────────────────┘
         │               │
        SIM              NÃO
         │               │
         ▼               ▼
    ┌────────┐    ┌────────────────────────┐
    │DEDUZIR │    │É Pensão Alimentícia?   │
    │ 100%   │    └────────────────────────┘
    └────────┘         │               │
                      SIM              NÃO
                       │               │
                       ▼               ▼
              ┌──────────────┐   ┌──────────────┐
              │Apareceu em   │   │Fica na base  │
              │6+ meses?     │   │(recorrente)  │
              └──────────────┘   └──────────────┘
                  │         │
                 SIM        NÃO
                  │         │
                  ▼         ▼
           ┌──────────┐ ┌──────────┐
           │MANTÉM    │ │REVISAR   │
           │na base   │ │manualmente│
           └──────────┘ └──────────┘
```

---

## Exemplo concreto: e se tivesse uma rescisão?

Imagine que nos dados do Chateau Lavoisier houvesse uma linha extra:

```
Rescisão - João Silva                R$  15.000,00  ← ⚠️ rescisão
```

A R2 identificaria isso e diria:

```
Base bruta:                          R$ 301.407,47  (com a rescisão)
Item pontual detectado:              R$  15.000,00  (rescisão)
                                     ─────────────
Valor que fica na base (recorrente): R$ 286.407,47
```

**O que acontece se a gente NÃO deduzir?**

O orçamento do ano seguinte incluiria R$ 15.000 para "demitir o João Silva de novo". Resultado: o condomínio ficaria com R$ 15.000 a menos de folga no orçamento, esperando uma despesa que nunca vai acontecer. Sobra dinheiro no caixa no fim do ano, mas faltou planejamento.

**O que acontece se a gente deduzir certo?**

A previsão reflete a realidade: aquele gasto foi um evento único que já passou. O dinheiro que estava reservado para "recorrências" agora está livre para outros usos — ou simplesmente não é orçado, e o condomínio tem uma previsão mais enxuta e realista.

---

## O caso especial da Pensão Alimentícia

Pensão alimentícia parece pontual — é um valor que varia, pode ser temporário... mas na prática dos condomínios, quando aparece por **6 meses ou mais**, é um **desconto em folha permanente**, ordem judicial que vale por anos.

No Chateau Lavoisier, a Pensão Alimentícia de **R$ 13.042,19** apareceu em **14 meses** de gasto. Isso significa que é uma obrigação contínua — todos os meses o condomínio desconta do salário de alguém e repassa. Não faz sentido deduzir da base.

### Como o sistema decide

```
Histórico de Pensão Alimentícia nos últimos 12 meses:

Jan  Fev  Mar  Abr  Mai  Jun  Jul  Ago  Set  Out  Nov  Dez
 ✅   ✅   ✅   ✅   ✅   ✅   ✅   ✅   ✅   ✅   ✅   ✅

6+ meses com gasto → RECORRENTE ✅
```

Se aparecesse só 1 ou 2 meses:

```
Jan  Fev  Mar  Abr  Mai  Jun  Jul  Ago  Set  Out  Nov  Dez
 ✅   ❌   ❌   ❌   ❌   ❌   ❌   ❌   ❌   ❌   ❌   ❌

Menos de 6 meses → REVISAR MANUALMENTE ⚠️
```

Nesse caso, o sistema **não deduz automaticamente** (porque pensão tem exceção), mas **sinaliza para revisão**. Pode ser:

- Uma pensão recém-determinada pela justiça (vai virar recorrente)
- Uma pensão temporária que já acabou (não deve voltar)
- Um erro de lançamento

---

## O que pode dar errado

**1. Pensão alimentícia com menos de 6 meses que é permanente**

Se a ordem judicial saiu em novembro e o funcionário só teve 2 meses de desconto no ano base, o sistema vai pedir revisão. Se ninguém revisar, a pensão some do orçamento e no ano seguinte falta dinheiro para pagar.

**2. Rescisão registrada como "Salário"**

Se o contador lançou a rescisão dentro da rubrica "Salário Empregado(s)" em vez de criar uma rubrica separada, o sistema não vai saber que aquilo foi uma rescisão. A R2 não encontra o que não está identificado. Isso é um problema de classificação contábil, não da regra.

**3. Pensão que era temporária e virou permanente (ou vice-versa)**

Uma ação de alimentos pode ser revisada na justiça. Se era temporária e virou definitiva, o histórico de "poucos meses" estava correto na época mas engana o sistema hoje. O contrário também vale: uma pensão que durou anos e foi extinta precisa ser removida da base manualmente.

---

## Resumo em uma frase

> **Rescisão e indenização trabalhista nunca se repetem — saem 100% da base. Pensão alimentícia com 6+ meses de histórico é despesa contínua e fica; com poucos meses, pede revisão.**
