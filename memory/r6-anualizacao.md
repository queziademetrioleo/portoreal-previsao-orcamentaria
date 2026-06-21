---
name: r6-anualizacao
description: Como a R6 projeta contratos usando a tarifa mensal atual em vez da média histórica
metadata: 
  node_type: memory
  type: reference
  originSessionId: f8450791-7b60-4ea7-a33d-7130d60e5880
---

# R6 — Anualização: como o sistema calcula a projeção de contratos

## O problema

O prédio tem contratos que se repetem mês a mês — manutenção de elevador, seguro, pró-labore do síndico, taxa de administração da administradora. Todo mês entra uma conta parecida.

Para fazer o orçamento do ano que vem, você precisa responder:

**Quanto vamos gastar com esses contratos nos próximos 12 meses?**

A resposta parece óbvia: é só somar os últimos 12 meses. Mas tem uma pegadinha.

```
Contrato de Manutenção de Elevador — Chateau Lavoisier 2026

Janeiro:    R$ 1.000,00
Fevereiro:  R$ 1.000,00
Março:      R$ 1.000,00
Abril:      R$ 1.000,00
Maio:       R$ 1.000,00
Junho:      R$ 1.000,00
Julho:      R$ 1.067,05  ← reajuste contratual
Agosto:     R$ 1.067,05
Setembro:   R$ 1.067,05
Outubro:    R$ 1.067,05
Novembro:   R$ 1.067,05
Dezembro:   R$ 1.067,05
           ──────────
Total 12 meses: R$ 12.402,00  (6 meses a R$ 1.000 + 6 meses a R$ 1.067,05)
```

Se você simplesmente somar os últimos 12 meses, o orçamento daria **R$ 12.402,00**. Mas o contrato hoje custa **R$ 1.067,05/mês**. Pelos próximos 12 meses, você vai pagar:

```
R$ 1.067,05 × 12 = R$ 12.804,60
```

A diferença é de **R$ 402,60** — um valor que ficaria de fora do orçamento se você usasse a soma histórica.

---

## O que a R6 faz

A R6 pega o **valor mensal vigente** (a última tarifa que foi paga de verdade) e multiplica por 12.

Ela não pergunta "quanto foi gasto?". Ela pergunta **"quanto está sendo pago hoje?"**.

### Contrato de Manutenção de Elevador

```
Último valor mensal:       R$ 1.067,05
Projeção R6:               R$ 1.067,05 × 12 = R$ 12.804,60
Soma histórica (12 meses): R$ 12.402,00

 → A R6 projeta R$ 12.804,60, que é o valor correto para o próximo ano
```

### Pró-labore do Síndico

```
Último valor mensal:       R$ 1.621,00
Projeção R6:               R$ 1.621,00 × 12 = R$ 19.452,00
Soma histórica (12 meses): R$ 18.525,00
Previsão manual:           R$ 19.452,00 ✓

 → A R6 acertou exatamente o que o síndico colocou manualmente
```

---

## A intuição (com um exemplo do dia a dia)

Imagine que seu plano de internet era R$ 100/mês por 6 meses, e depois subiu para R$ 120/mês.

```
Meses 1 a 6:   R$ 100/mês
Meses 7 a 12:  R$ 120/mês
```

Duas formas de calcular o orçamento do próximo ano:

| Método | Conta | Resultado |
|--------|-------|-----------|
| Média dos 12 meses | (6×100 + 6×120) ÷ 12 | R$ 110/mês → **R$ 1.320/ano** |
| Tarifa atual (R6) | R$ 120 × 12 | **R$ 1.440/ano** |

A média diz "R$ 1.320". Mas nos próximos 12 meses você vai pagar **R$ 120 todo mês**, não R$ 110. O orçamento correto é **R$ 1.440**.

A R6 faz exatamente isso: ela ignora o "preço que já passou" e projeta com base no **preço que vale hoje**.

---

## A exceção do 13º salário

Alguns contratos incluem 13º salário no nome — "Pró-labore" e "Pró-labore 13" são itens diferentes.

O problema: imagine que o pró-labore de R$ 1.621,00 em dezembro veio com o 13º embutido, totalizando R$ 3.242,00 (dobrado). Se a R6 pegasse esse valor e multiplicasse por 12:

```
R$ 3.242,00 × 12 = R$ 38.904,00  ←  13 décimos terceiros! 🙅
```

Isso não faz sentido. O 13º acontece uma vez por ano. Multiplicar por 12 um mês que já tem 13º incluído significaria orçar **12 parcelas de 13º salário**.

**Por isso a R6 é desligada para itens com "13" no nome.** Esses itens usam a soma histórica simples (total dos 12 meses) em vez da anualização.

```
Item sem "13":         pró-labore             → R6 ligada  (último valor × 12)
Item com "13":         pró-labore 13          → R6 desligada (soma dos 12 meses)
```

---

## A pegadinha do último mês zerado

A R6 usa o **último valor mensal NÃO ZERO**. Se a conta de dezembro não foi paga ainda (valor zero), ela olha novembro. Se novembro também for zero, outubro... até achar um mês com valor real.

```
Mês a mês:
Dezembro:  R$ 0,00        ← fatura ainda não entrou
Novembro:  R$ 0,00        ← também não
Outubro:   R$ 1.067,05    ← achou!
```

Nesse caso, a R6 usa **R$ 1.067,05** mesmo que os dois últimos meses estejam zerados. O sistema não se engana: o contrato continua valendo R$ 1.067,05 — a fatura é que está atrasada.

---

## O que pode dar errado

### 1. Último mês com cobrança anormal

Imagine que em dezembro o elevador quebrou e veio uma taxa extra de R$ 2.500 junto com a mensalidade de R$ 1.067.

```
Dezembro:    R$ 3.567,05   (R$ 1.067 + R$ 2.500 de taxa extra)
```

A R6 pegaria esse valor de R$ 3.567 e faria: R$ 3.567 × 12 = **R$ 42.804,60** — um orçamento completamente errado.

**O que fazer?** Se o último mês tiver uma cobrança atípica, vale a pena verificar manualmente ou aguardar o mês seguinte para ter um valor limpo.

### 2. Contrato recém-iniciado

Se o contrato começou há 2 meses, a R6 tem apenas 2 valores para olhar. O último valor é confiável, mas vale conferir se há reajustes programados.

### 3. Reajuste futuro já contratado

A R6 não sabe de reajustes futuros. Se o contrato prevê 10% de aumento em março, a R6 vai projetar o valor atual — o orçamento vai ficar defasado a partir de março.

### 4. Contratos com parcelamento

Obras ou serviços parcelados (ex.: "Pintura da fachada — parcela 6/12") não devem ser anualizados — eles têm data para acabar. Mas a R6 não distingue isso sozinha; a classificação como contrato ou obra é definida antes.

---

## Resumo em uma frase

> A R6 não pergunta "quanto foi gasto?", ela pergunta "quanto está sendo pago hoje?" — pega a tarifa mensal vigente e multiplica por 12, ignorando o histórico de meses com valores mais baixos (a não ser que o item tenha "13" no nome, porque aí seria 13º salário repetido 12 vezes).

---

## Visual rápido

```
Para cada item classificado como CONTRATO, PRÓ-LABORE ou TAXA DE ADMINISTRAÇÃO:

  1. O nome tem "13"?
     ├── Sim → usa a soma dos 12 meses (R6 desligada)
     └── Não → continua

  2. Qual o último mês com valor > 0?
     ├── Dezembro  → usa dezembro
     ├── Novembro  → usa novembro (se dezembro for zero)
     └── [...]     → volta até achar um valor real

  3. Projeção = último valor mensal × 12

     Exemplo: R$ 1.067,05 × 12 = R$ 12.804,60
```
