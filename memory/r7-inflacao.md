---
name: r7-inflacao
description: Por que a R7 aplica 10% de inflação sobre o subtotal do orçamento
metadata: 
  node_type: memory
  type: reference
  originSessionId: f8450791-7b60-4ea7-a33d-7130d60e5880
---

# R7 — Por que a inflação é de 10%?

## O problema

Você fez o orçamento para 2027 baseado nos gastos reais de 2026. Depois de aplicar todas as regras (R1 a R6), sobrou um **subtotal de R$ 637.637,66** para custear o condomínio no próximo ano.

A pergunta é: **esse valor é suficiente?**

Não, não é. Porque tudo fica mais caro de um ano para o outro.

- O salário do zelador vai subir (dissídio)
- O contrato de manutenção do elevador vai reajustar
- O seguro do prédio vai aumentar
- O material de limpeza, as lâmpadas, os filtros de água... tudo sobe

Se você orçar exatamente o mesmo que gastou em 2026, em 2027 vai faltar dinheiro. É como encher o tanque do carro: hoje cabem R$ 200, ano que vem cabem R$ 220 pelo mesmo tanto de gasolina. Você precisa colocar os R$ 20 a mais.

---

## O cálculo

```
Subtotal (R1 a R6):  R$ 637.637,66
Inflação (10%):      R$  63.763,77
─────────────────────────────────────
Total previsto:      R$ 701.401,43
```

A inflação de **10%** é um acréscimo de segurança aplicado sobre tudo o que já foi calculado.

---

## Por que 10% e não 5%?

A inflação oficial do Brasil (IPCA) gira em torno de **5% ao ano**. Mas gastos de condomínio sobem **mais** que a inflação média por alguns motivos:

| Item | Tende a subir |
|------|--------------|
| Salários (zelador, portaria, faxina) | Dissídio anual ~6-8% |
| Contratos terceirizados (elevador, segurança) | Reajuste anual com IGPM |
| Seguro do prédio | 10-15% ao ano |
| Material de limpeza e manutenção | Acompanha inflação + variação de commodities |
| Água e luz | Reajustes acima da média |

**10% é uma margem conservadora.** Significa que, se a inflação real do condomínio ficar entre 5% e 9%, você ainda tem folga. Melhor sobrar um pequeno superávit no fim do ano do que ter déficit e precisar fazer rateio extra.

### E quanto aos itens que já capturam inflação?

A R6 (anualização) já usa as taxas e contratos **vigentes**, que embutem alguma correção. Mas isso só cobre contratos que foram renovados. Itens como água, energia elétrica, material de limpeza, pequenos reparos e compras avulsas **não têm reajuste contratual** — eles simplesmente ficam mais caros. A R7 cobre exatamente esses buracos.

---

## Visual: o efeito da inflação no orçamento

```
Orçamento 2027 sem inflação:

  [R$ 637.637,66] →  Gasolina para o ano todo
                      ↓
              ⛽⛽⛽⛽⛽⛽⛽⛽⛽⛽  (10 litros)
              
  Em julho, o preço da gasolina sobe.
  Em dezembro, você ficou parado na estrada.
```

```
Orçamento 2027 com inflação (+10%):

  [R$ 637.637,66] + [R$ 63.763,77] = R$ 701.401,43
                      ↓
              ⛽⛽⛽⛽⛽⛽⛽⛽⛽⛽⛽  (11 litros — a folga que você precisa)
```

---

## O que pode dar errado

### Cenário A: inflação menor que 10% (ex: 3%)

```
Você orçou:    R$ 701.401,43
Gastou real:   R$ 656.566,59 (subtotal + 3%)

Sobra:         R$  44.834,84 → superávit
```

**Problema:** você cobrou a mais dos condôminos. O superávit vai para o fundo de reserva, mas ninguém gosta de pagar mais do que o necessário.

**Mitigação:** melhor do que faltar. Um superávit vira reserva para emergências.

### Cenário B: inflação maior que 10% (ex: 15%)

```
Você orçou:    R$ 701.401,43
Gastou real:   R$ 733.283,31 (subtotal + 15%)

Falta:         R$  31.881,88 → déficit
```

**Problema:** no meio do ano você descobre que o dinheiro não vai dar. Precisa fazer rateio extra ou cortar gastos.

**Mitigação:** com 10% você já cobre boa parte. Se faltar, é um valor menor do que se tivesse colocado 5%.

### Cenário C: inflação bem baixa (ex: 2%)

```
Você orçou:    R$ 701.401,43
Gastou real:   R$ 650.390,41 (subtotal + 2%)

Sobra:         R$  51.011,02 → superávit grande
```

Nesse caso, o condomínio acumulou um bom fundo de reserva. No ano seguinte, dá para reduzir a inflação projetada para 5% ou 6%, devolvendo parte do que sobrou para os condôminos.

---

## Resumo em uma frase

> Tudo fica mais caro de um ano para o outro — salários, contratos, materiais — e os 10% da R7 são uma margem de segurança para garantir que o orçamento de 2027 não quebre no meio do caminho, nem precise de rateio extra.
