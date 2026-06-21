---
name: r1-obras-benfeitorias
description: Como a R1 decide que obras e benfeitorias são gastos extraordinários
metadata: 
  node_type: memory
  type: reference
  originSessionId: f8450791-7b60-4ea7-a33d-7130d60e5880
---

# R1: Obras e Benfeitorias -- Gastos que o condomínio não repete todo ano

## O problema

Imagine que em 2025 seu condomínio gastou R$ 21.702,49 reformando a portaria. Pintura, piso novo, mão de obra, material -- tudo saiu do caixa do condomínio.

Agora é 2026, e alguém pega o relatório de 2025 e pergunta: "quanto vamos gastar este ano?"

Se você simplesmente copiar os números do ano passado, vai incluir essa reforma no orçamento de 2026 como se ela fosse acontecer de novo. Mas não vai. Portaria já está reformada.

**Incluir gastos de obra no orçamento do ano seguinte faz o condomínio achar que precisa de muito mais dinheiro do que realmente precisa.** Resultado: taxa condominial inflada, condôminos pagando mais à toa.

A R1 resolve isso: **ela joga fora** todos os gastos classificados como "Obras/Benfeitorias" na hora de fazer a previsão.

---

## Como a R1 funciona na prática

| O que acontece | Efeito |
|---|---|
| O sistema encontra uma despesa do grupo "Despesas com Obras/Benfeitorias" | Remove o valor integral da previsão |
| A despesa é marcada como "extraordinária" | Não entra na conta do orçamento do ano que vem |
| O valor migra para a coluna "Desconsiderações" | Aparece separado, documentado, mas fora da conta |

É um filtro: entra obra, sai obra. Simples assim.

---

## Caso real: Chateau Lavoisier 2026

No relatório `dessin02.xls` do Chateau Lavoisier, o grupo **"Despesas com Obras/Benfeitorias"** aparece com estes valores:

| Subgrupo | Total | Quantidade |
|---|---|---|
| Despesas com Material | R$ 8.102,59 | 4 notas fiscais |
| Despesas com Mão de Obra | R$ 12.750,00 | 7 notas fiscais |
| Despesas com Benfeitorias | R$ 849,90 | 1 nota fiscal |
| **Total Obras/Benfeitorias** | **R$ 21.702,49** | **12 lançamentos** |

Na planilha `Previsão 2026.xlsx`, a coluna "Desconsiderações" exibe exatamente **R$ 21.702,49**.

Repare: bate centavo por centavo. Não é coincidência -- é a R1 funcionando. O sistema simplesmente pega tudo que está no grupo de obras e transfere para a coluna de desconsiderações, sem cortar um real a mais nem a menos.

---

## Por que obras são diferentes de água, luz e salário?

Despesas de condomínio se dividem em dois tipos:

| Tipo | Exemplos | Se repete todo mês? |
|---|---|---|
| **Operacionais** (ordinárias) | Água, luz, salário do porteiro, material de limpeza | Sim |
| **Extraordinárias** | Reforma da fachada, troca do elevador, pintura do salão | Não |

Obra é gasto **extraordinário** porque:

- É um investimento em melhoria do patrimônio, não é consumo do dia a dia
- Depois que a obra acaba, o gasto acaba junto
- Nem todo ano tem obra igual
- O valor costuma ser alto e distorce a previsão se misturado com despesas normais

Um condomínio que gastou R$ 21.702,49 com obra em 2025 pode gastar R$ 0 em 2026. Se o orçamento presumir que vai gastar de novo, a taxa condominial fica mais cara sem necessidade.

---

## A lei por trás disso

O **Código Civil** (Lei 10.406/2002) trata do assunto no **Art. 1.341**:

> "As obras necessárias à conservação das partes comuns e as **extraordinárias** dependem de autorização da assembleia geral."

Traduzindo: obra não é uma decisão do síndico sozinho. Precisa de assembleia porque é um gasto extra, que sai do ordinário. A R1 só segue essa lógica: se a lei trata obra como algo à parte, o orçamento também deve tratar.

---

## Qual o impacto real?

Se a R1 **não existisse**, o orçamento previsto para 2026 incluiria R$ 21.702,49 a mais.

Vamos ver o efeito prático:

```
Orçamento sem R1:  R$ 240.000,00  (inclui a obra)
Orçamento com R1:  R$ 218.297,51  (obra removida)
Diferença:         -R$ 21.702,49  (-9%)
```

Num condomínio com ~200 unidades, isso dá aproximadamente **R$ 100 a mais por mês** para cada condômino -- só por causa de uma reforma que já aconteceu.

A R1 não está "escondendo" dinheiro. O gasto com obra está registrado, documentado, aparece nos relatórios. Só não entra na conta do que o condomínio vai precisar pagar no ano seguinte.

---

## E se o sistema erra?

Obras podem estar mal classificadas no sistema de contabilidade. Dois cenários comuns:

**Cenário 1: Um gasto que é obra, mas está em outro grupo**

Exemplo: o condomínio trocou o portão eletrônico (obra), mas o contador colocou como "Despesas com Manutenção". A R1 não vai remover esse valor, porque ela só olha para o grupo "Obras/Benfeitorias".

Resultado: o gasto entra na previsão como se fosse despesa normal. O orçamento fica um pouco maior, mas o impacto é pequeno (uma nota só, não o pacote inteiro).

**Cenário 2: Um gasto que não é obra, mas está no grupo de obras**

Exemplo: o contador classificou a compra de lâmpadas (material de consumo normal) como "Despesas com Material" dentro de obras. A R1 vai remover esse valor junto com o resto.

Resultado: o orçamento fica um pouco mais baixo do que deveria. O sistema "perdeu" um gasto que devia contar.

**O que fazer nesses casos?** Ajustar a classificação contábil na fonte. A R1 é um filtro automático que confia na categoria em que o gasto foi cadastrado. Se a categoria estiver errada, o filtro vai aplicar a regra errada. Não é bug da R1 -- é o dado de entrada que precisa de correção.

---

## Resumo em uma frase

**Obras e benfeitorias são gastos que não se repetem todo ano; a R1 os remove da previsão orçamentária para que o condomínio não monte um orçamento inflado com base em dinheiro que já gastou e não vai gastar de novo.**
