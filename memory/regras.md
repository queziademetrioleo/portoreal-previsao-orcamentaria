# Regras do motor (`previsao.py`) — como estão no código

> Fonte da verdade é o código; atualizar este resumo junto com qualquer mudança de regra.
> Última revisão: 18/10/2026.

| Regra | O que faz hoje |
|---|---|
| **R1** Obras/Benfeitorias | Grupo inteiro fora da previsão, mesmo se a revisão marcar "manter". |
| **R2** Pessoal pontual | Rescisão/indenização: deduz os lançamentos marcados como extraordinários; folha e pensão alimentícia recorrente ficam. |
| **R3** Manutenções irregulares | Outliers estatísticos (MAD) + IA marcam lançamentos extraordinários; humano confirma na revisão. |
| **R4** Despesas Diversas | Seguro tem regra própria. Todas as demais contas ficam na própria linha, menos extraordinários. **Não existe provisão** (laudo/incêndio) desde 23/10/2026 — nem nome, nem valor. |
| **R5** Cartoriais e Honorários | **Desligada em 18/10/2026.** Fica na linha própria "Despesas Cartoriais e Honorários", menos extraordinários. |
| **R6** Contratos / pró-labore / taxa de administração | Último valor pago × 12. A 13ª taxa não usa essa regra. |
| **Seguro** | Apólice vigente: última parcela × total de parcelas (coluna Parcela do Alma ou "Parcela N/M" na descrição). Sem essa informação, conta pagamentos mensais seguidos de mesmo valor (pagamento único = 1). |
| **R7** Aumento previsto | 10% fixo sobre o subtotal (não editável). |
| **R8** Inadimplência | Abate da receita (não é despesa), um mês por unidade. Só Condo21: ≥3 meses consecutivos, taxa da unidade. **Só Group** (Inadimplência detalhada, opcional): mesma regra do Alma — mês do relatório = data de emissão; boleto sem Recebimento nos dois meses anteriores → abate o boleto inteiro mais recente (boleto só de acordo não conta). Com Alma (e Group sozinho): unidade que deve **os dois** meses anteriores ao mês do relatório Alma (outubro → setembro e agosto; débito antigo com esses meses pagos = acordo, não entra) → abate **um boleto inteiro** (taxa, fundo e água, sem multa/juros); sem registro = zero; não buscar débitos antigos do outro sistema. |
| **R9** Superávit | ≥ R$ 2.000/mês confortável; entre 0 e 2.000 insuficiente (alerta); < 0 déficit. Reajuste sugerido mira a margem mínima. |

Exceções fixas: `PONTUAL_FORA` (combate a incêndio — gasto pontual, fora); `SEMPRE_RECORRENTE`
(extintor — nunca deduzido, aparece como "Recarga de Extintores").

**Receita:** documento vigente (taxa com desconto + fundo + recorrentes identificadas) **+ água cobrada das unidades**
(média dos meses com receita no balancete, `receitas_consumo`) + receitas manuais. Fora: complemento/chamada de capital,
juros, multa, taxa extra, rendimentos, créditos.
**Sem gráfico de evolução mensal (retirado em 26/10/2026, pedido da usuária: "não será mais preciso"):** nem no
PDF, nem no DOCX, nem no XLSX; o estado da sessão também não calcula mais `fluxo_mensal`. Único gráfico: pizza.
Opções de custeio: "Receitas sem fundo de reserva" / "Receitas com fundo de reserva" (+ aluguel, se houver).
Páginas (26/10/2026, "sem espaçamentos muito longos"): sem página nova forçada — pizza e Conclusão seguem o
fluxo (seção inteira pula de página só se não couber); assinatura presa ao último item das Considerações.

PDF (`relatorio_pdf.py`): considerações com inicial maiúscula por frase; composição de conservação
omite "Outros Materiais"/"Outras despesas" e termina com "etc."; 13ª taxa de administração omitida do texto.
Avisos de importação (mês não fechado, receita fixa, diferenças balancete × pagamentos) **nunca** entram nas
considerações: o documento vai ao condomínio; esses avisos ficam só na tela (José, 22/10/2026).

Sem aprendizado entre análises (retirado em 23/10/2026): cada análise usa só regras + IA; decisões valem só na sessão.

## Relatório XLSX

Mesmo desenho e números do PDF, com fórmulas (linha nova com "fundo de reserva" no nome conta como fundo). Opções: sem fundo = total de receitas − Fundo − Aluguel; com fundo soma o
Fundo; "+ aluguel" soma o Aluguel. Reajuste = |TOTAL / RECEITA − 1| só com resultado negativo. Situação:
Superávit ≥ R$ 2.000/mês, Superávit insuficiente ≥ 0, senão Déficit.
