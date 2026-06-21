---
name: r8-inadimplencia
description: Como a R8 detecta inadimplência crítica (3+ meses consecutivos) e alerta sobre risco de receita
metadata: 
  node_type: memory
  type: reference
  originSessionId: f8450791-7b60-4ea7-a33d-7130d60e5880
---

# R8 — Como a inadimplência afeta a receita prevista

## O problema

No Chateau Lavoisier, 4 unidades estão com contas em atraso. Juntas, elas devem **R$ 5.718,69** ao condomínio:

```
Unidade  Atraso           Valor       Crítico?
─────────────────────────────────────────────────
B-106    mar/2026 (1 mês)  R$ 1.008,53  ❌ Não
B-203    mar/2026 (1 mês)  R$ 1.037,95  ❌ Não
B-302    fev a mar/2026    R$ 2.384,20  ❌ Não
         (2 meses)
B-405    mar/2026 (1 mês)  R$ 1.288,01  ❌ Não
─────────────────────────────────────────────────
Total:                     R$ 5.718,69
Unidades críticas:         0
```

Nenhuma dessas unidades está em situação crítica. Por que? Porque o sistema usa um **limiar de 3 meses consecutivos** para considerar que a inadimplência é real — e não apenas um esquecimento ou atraso pontual.

---

## A lógica do limiar: 1, 2 ou 3 meses?

A regra é simples: **só abate da receita se o atraso for de 3 meses consecutivos ou mais.**

### 1 mês de atraso — "esqueci de pagar"

```
Status da conta:       ⬜ ATRASADO
Passou 1 mês?          ✅
Considera crítico?     ❌

Motivo: a pessoa pode ter esquecido, viajado, ou
está esperando o boleto cair na segunda via. Na
maioria dos casos, ela paga no mês seguinte.
```

### 2 meses consecutivos — "estou enrolando"

```
Status da conta:       ⬜ ATRASADO ⬜ ATRASADO
Passou 2 meses?        ✅
Considera crítico?     ❌

Motivo: pode ser dificuldade financeira temporária,
pode ser descuido. Mas ainda pode regularizar nos
próximos 30 dias pagando os dois meses juntos.
```

### 3 meses consecutivos — "problema real"

```
Status da conta:       ⬜ ATRASADO ⬜ ATRASADO ⬜ ATRASADO
Passou 3 meses?        ✅
Considera crítico?     ✅ → ✅ Abate da receita

Motivo: quando alguém fica 3 meses sem pagar, não
é mais esquecimento. É inadimplência real. O
condomínio precisa agir (protesto, negativação,
medidas legais) e, financeiramente, não pode contar
com esse dinheiro no orçamento.
```

### Exemplo prático: B-302

```
Unidade B-302:

Janeiro/2026   →  ✅ PAGO
Fevereiro/2026 →  ⬜ ATRASADO  ← Mês 1
Março/2026     →  ⬜ ATRASADO  ← Mês 2 consecutivo
Abril/2026     →  ⬜ ???       ← Se não pagar: MÊS 3 → CRÍTICO

Situação atual: 2 meses consecutivos → AINDA NÃO crítico
```

Se a B-302 pagar em abril (os dois meses de uma vez), o problema some. Se não pagar em abril, entra mês 3 e vira crítico.

---

## Inadimplência não é despesa — é receita que não entra

Essa é a diferença mais importante da R8:

```
Gastar mais:          ⬆ Despesa (aumenta o custo)
Receber menos:        ⬇ Receita (diminui o dinheiro disponível)
```

Quando uma unidade não paga, o condomínio **não gasta mais dinheiro**. Ele apenas **deixa de receber** o que esperava. Por isso a R8 não mexe no total de despesas — ela cria um **alerta** que mostra quanto da receita prevista está em risco.

```
Orçamento completo:

  Despesa total:     R$ 701.401,43  (fixo, não muda)
  Receita prevista:  R$ 701.401,43  (o que todo mundo deveria pagar)
  
  Risco de inadimplência: R$ 0,00   (nenhuma unidade crítica)
  
  → Se nenhuma unidade atingir 3 meses de atraso,
    a receita prevista continua R$ 701.401,43.
```

Se alguma unidade atingisse 3 meses, o alerta mostraria:

```
  Risco de inadimplência: R$ 2.384,20  (unidade X, 3 meses)
  Receita REAL esperada:  R$ 699.017,23  (previsto - risco)
  
  → As despesas continuam R$ 701.401,43.
    A diferença precisa vir do fundo de reserva.
```

---

## O que aprendemos com o leia-me.txt?

> "Considerei a inadimplência apenas da unidade 203B na previsão de 2022. Nos demais anos eu desconsiderei pelo fato da inadimplência ser apenas de 1 ou 2 meses."

Isso confirma a lógica: em 2022 havia de fato um caso crítico (unidade 203B com 3+ meses). Nos demais anos, todos os atrasos eram de 1 ou 2 meses — dentro do limiar de "não crítico" — e foram ignorados no cálculo do orçamento.

---

## O que pode dar errado

### Cenário: o inadimplente crônico (2 sim, 1 não, 2 sim)

```
Unidade X:

Jan ✅  Fev ❌  Mar ✅  Abr ❌  Mai ✅  Jun ❌
Nunca atinge 3 meses consecutivos, mas também
nunca está em dia. Paga um mês sim, um não.

Resultado: R8 nunca aciona → receita sempre superestimada
```

**Problema:** o sistema não pega esse padrão porque o limiar é "meses consecutivos". Alguém que paga todo mês sim, mês não, fica inadimplente metade do ano mas nunca é classificado como crítico.

**Mitigação:** o limiar de 3 meses foi escolhido porque ele separa bem "esquecimento eventua" de "inadimplência real". O padrão de pagar um mês sim, um não é raro em condomínios residenciais e, quando acontece, o valor devido nunca acumula muito — o condomínio consegue cobrar com medidas extrajudiciais antes de virar problema orçamentário.

### Cenário: crise econômica geral

Se metade do prédio ficar inadimplente de uma vez (ex: desemprego em massa), o limiar de 3 meses pode ser tarde demais. A receita despenca antes do sistema alertar.

**Mitigação:** nesse cenário, a regra precisa ser revista manualmente — reduzindo o limiar para 1 ou 2 meses — porque a situação é excepcional.

---

## Resumo em uma frase

> Atraso de 1 ou 2 meses pode ser esquecimento e a pessoa paga depois; atraso de 3 meses consecutivos é inadimplência real — mas no Chateau Lavoisier em 2026 ninguém chegou nesse ponto, então o risco é zero e a receita prevista de R$ 701.401,43 permanece intacta.
