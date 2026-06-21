---
name: r3-como-funciona
description: Explicação prática e visual de como a regra R3 funciona (Camada 1 estatística + Camada 2 IA)
metadata: 
  node_type: memory
  type: reference
  originSessionId: f8450791-7b60-4ea7-a33d-7130d60e5880
---

# R3 — Como o sistema decide o que é gasto extraordinário

## O problema

Temos uma classe de gastos como "Manutenção Elétrica". No ano, foram 8 notas fiscais:

```
R$ 321,14   Troca de sensores
R$ 450,00   Visita mensal do eletricista
R$ 450,00   Visita mensal do eletricista
R$ 450,00   Visita mensal do eletricista
R$ 450,00   Visita mensal do eletricista
R$ 850,00   Reparo no quadro de energia (parcela final)
R$ 1.121,00 Instalação de lâmpadas LED na recepção
R$ 1.176,00 Compra de 12 válvulas de reposição
```

**Pergunta**: quais desses gastos vão se repetir no ano que vem (recorrentes) e quais foram eventos pontuais (extraordinários)?

As visitas de R$ 450 do eletricista acontecem todo mês — são recorrentes. Mas o reparo de R$ 850 no quadro de energia, a instalação de R$ 1.121 em LED e a compra de R$ 1.176 em válvulas são coisas que aconteceram uma vez e não devem se repetir.

O sistema precisa descobrir isso **sozinho**, sem uma pessoa olhando nota por nota.

---

## Camada 1 — Estatística (MAD)

A Camada 1 não sabe ler. Ela só olha para os **números**.

### Passo 1: Encontra o valor "normal"

Pega todos os valores e ordena do menor para o maior:

```
321, 450, 450, 450, 450, 850, 1121, 1176
```

O valor do meio é a **mediana**: R$ 450. Esse é o gasto "típico" dessa classe.

> A mediana é melhor que a média porque a média seria puxada para cima pelos valores grandes (daria R$ 659) e aí tudo pareceria "normal".

### Passo 2: Mede o quanto os valores se espalham

Calcula a distância de cada valor até a mediana:

```
|321 - 450| = 129
|450 - 450| = 0
|450 - 450| = 0
|450 - 450| = 0
|450 - 450| = 0
|850 - 450| = 400
|1121 - 450| = 671
|1176 - 450| = 726
```

Ordena essas distâncias:

```
0, 0, 0, 0, 129, 400, 671, 726
```

A mediana dessas distâncias é o **MAD** (Median Absolute Deviation): **(0 + 129) ÷ 2 = 64,43**.

> O MAD mede a variação "normal" dos dados. Se todo mundo gastasse exatamente R$ 450 toda vez, o MAD seria zero.

### Passo 3: Define a linha de corte

```
Linha de corte = Mediana + 3 × MAD × 1,4826
               = 450 + 3 × 64,43 × 1,4826
               = 450 + 286,58
               = R$ 736,58
```

Qualquer nota fiscal **acima de R$ 736,58** é considerada fora do padrão.

### Passo 4: Separa os outliers

```
R$ 321,14  →  abaixo de R$ 737  →  ✅ Normal (recorrente)
R$ 450,00  →  abaixo de R$ 737  →  ✅ Normal (recorrente)
R$ 450,00  →  abaixo de R$ 737  →  ✅ Normal (recorrente)
R$ 450,00  →  abaixo de R$ 737  →  ✅ Normal (recorrente)
R$ 450,00  →  abaixo de R$ 737  →  ✅ Normal (recorrente)
R$ 850,00  →  ACIMA de R$ 737   →  ⚠️ Extraordinário
R$ 1.121,00 →  ACIMA de R$ 737   →  ⚠️ Extraordinário
R$ 1.176,00 →  ACIMA de R$ 737   →  ⚠️ Extraordinário

Total extraordinário: R$ 3.147,00 (60% da classe)
```

### Resumo visual

```
[Recorrentes]              [Extraordinários]
R$ 321                     R$ 850  ⚠️
R$ 450                     R$ 1.121 ⚠️
R$ 450                     R$ 1.176 ⚠️
R$ 450                           
R$ 450                     Linha de corte: R$ 737
───────┬─────────────────────────────────────
       R$ 450 (mediana)
```

### Quando a Camada 1 NÃO encontra nada

Exemplo: Manutenção Pintura (11 notas fiscais):

```
R$ 195   Material miúdo (lixa, desempenadeira)
R$ 205   Tinta e massa corrida
R$ 2.100 Pintura de muro lateral
R$ 2.100 Pintura de muro lateral (parte 2)
R$ 2.196 Material (parcela 2/3)
R$ 2.196 Material (parcela 3/3)
R$ 2.197 Material (parcela 1/3)
R$ 2.700 Reparo de reboco
R$ 3.500 Pintura da garagem térrea
R$ 4.000 Pintura da garagem (parcela 1)
R$ 4.000 Pintura da garagem (parcela 2)
```

Mediana = R$ 2.196. Linha de corte = **R$ 7.108**. Nenhum valor acima disso.

**Resultado: zero outliers.** Isso está certo — os valores são distribuídos de forma uniforme, sem um item isolado que destoe. Não tem como a estatística sozinha decidir o que é extraordinário aqui.

---

## Camada 2 — Inteligência Artificial (IA por classe)

A Camada 2 **sabe ler**. Ela olha para as descrições das notas fiscais e entende o contexto.

### O que a IA recebe

A IA (Claude) recebe **todas as notas fiscais de uma classe de uma vez** e o resultado da Camada 1. Por exemplo:

```
CLASSE: Manutenção Elétrica (grupo: Conservação)
  Total 12 meses: R$ 5.268,14
  Notas fiscais: 8
  Outliers já encontrados pela estatística: R$ 3.147,00

  Notas fiscais (maiores valores primeiro):
    R$ 1.176,00 | 14/04/2025 | Aquisição de 12 unidades de reparo de válvula docol
    R$ 1.121,00 | 19/12/2025 | Serviço de retirada e instalação de lâmpadas de LED
    R$ 850,00   | 11/04/2025 | Manutenção do PC de energia - Parcela 02/02
    R$ 450,00   | 05/06/2025 | Nilo César dos Santos
    R$ 450,00   | 04/08/2025 | Nilo César dos Santos
    R$ 450,00   | 04/09/2025 | Nilo César dos Santos
    R$ 450,00   | 24/02/2026 | Nilo César dos Santos
    R$ 321,14   | 04/02/2026 | Retirada dos sensores dos blocos A e B
```

### O que a IA responde

```json
{
  "classes": {
    "manutencao eletrica": {
      "pct": 0.60,
      "justificativa": "3 itens sao reparos pontuais (PC de energia, LED, valvulas); os 5 restantes sao visitas periodicas do tecnico"
    }
  }
}
```

A IA confirma: **60% é extraordinário**.

### Por que a IA vê coisas que a estatística não vê

Imagine que em vez de 1 nota de R$ 850, fossem **3 notas de R$ 850** parceladas. A estatística não pegaria (R$ 850 está abaixo da linha de corte de R$ 737 se a mediana subir). Mas a IA leria "Parcela 01/03", "Parcela 02/03", "Parcela 03/03" e saberia que é um projeto único parcelado → extraordinário.

Outro exemplo: uma nota de **R$ 500** com descrição "Substituição completa do sistema de interfonia". O valor é baixo, mas a descrição indica um evento pontual. A Camada 1 não pega (R$ 500 é "normal"), mas a Camada 2 pega.

---

## Como as duas camadas se combinam

```
Para cada classe de manutenção:

1. Roda a Camada 1 (MAD)
   → Encontrou outliers? Anota o valor.

2. Roda a Camada 2 (IA)
   → Sugeriu um % de dedução? Converte em valor (base × %).

3. Pega o MAIOR dos dois
   → Dedução final = max(Camada1, Camada2)

4. Se nenhuma camada encontrou nada
   → Dedução = R$ 0 (tudo é recorrente)
```

### Exemplo real (Manutenção Elétrica)

```
Base total da classe:           R$ 5.268,14

Camada 1 (MAD):                 R$ 3.147,00  (60%)
Camada 2 (IA):                  60% = R$ 3.160,89

Resultado: max(3.147, 3.161) = R$ 3.161,00 deduzido
Valor que fica na base:         R$ 2.107,14  (as visitas mensais)
```

### Exemplo real (Manutenção Pintura)

```
Base total da classe:           R$ 25.389,05

Camada 1 (MAD):                 R$ 0  (sem outliers isolados)
Camada 2 (IA):                  analisa e decide

Se a IA disser 0%:
  → Tudo fica na base (como a Quézia fez manualmente)
Se a IA disser 50%:
  → R$ 12.694 deduzido (pintura externa = extraordinária)
```

## E se a IA não estiver disponível?

O sistema continua funcionando **só com a Camada 1**. Se houver outliers estatísticos, eles são deduzidos. Se não houver, a dedução é zero (tudo fica como recorrente).

**Antes**: sem IA → dedução zero (cega).
**Agora**: sem IA → Camada 1 ainda detecta outliers → dedução onde há evidência numérica.

## Resumo em uma frase

> A **Camada 1** olha os números e pergunta: "Tem alguma nota fiscal com valor muito acima do normal?". A **Camada 2** lê as descrições e pergunta: "Tem algum serviço ou compra que é claramente um evento pontual?". As duas trabalham juntas — o que uma não vê, a outra pode ver.
