# Regras do motor (`previsao.py`) — como estão no código

> Fonte da verdade é o código; atualizar este resumo junto com qualquer mudança de regra.
> Última revisão: 18/10/2026.

| Regra | O que faz hoje |
|---|---|
| **R1** Obras/Benfeitorias | Grupo inteiro fora da previsão, mesmo se a revisão marcar "manter". |
| **R2** Pessoal pontual | Rescisão/indenização: deduz os lançamentos marcados como extraordinários; folha e pensão alimentícia recorrente ficam. |
| **R3** Manutenções irregulares | Outliers estatísticos (MAD) + IA marcam lançamentos extraordinários; humano confirma na revisão. |
| **R4** Despesas Diversas | Seguro tem regra própria. Manutenções (reparo, conserto, bomba, portão, elevador) e contas genéricas ("Outras despesas", "Outros", "Estorno", "Diversas") ficam, menos extraordinários. **Demais contas** viram "Provisão para Laudo de Autovistoria" (somada em Conservação no PDF). |
| **R5** Cartoriais e Honorários | **Desligada em 18/10/2026.** Fica na linha própria "Despesas Cartoriais e Honorários", menos extraordinários. |
| **R6** Contratos / pró-labore / taxa de administração | Último valor pago × 12. A 13ª taxa não usa essa regra. |
| **Seguro** | Apólice vigente: última parcela × total de parcelas (coluna Parcela do Alma ou "Parcela N/M" na descrição). Sem essa informação, conta pagamentos mensais seguidos de mesmo valor (pagamento único = 1). |
| **R7** Aumento previsto | 10% fixo sobre o subtotal (não editável). |
| **R8** Inadimplência | Abate da receita (não é despesa), um mês por unidade. Só Condo21: ≥3 meses consecutivos, taxa da unidade. **Só Group** (Inadimplência detalhada, opcional): mesma regra do Alma — mês do relatório = data de emissão; boleto sem Recebimento nos dois meses anteriores → abate o boleto inteiro mais recente (boleto só de acordo não conta). Com Alma (e Group sozinho): unidade que deve **os dois** meses anteriores ao mês do relatório Alma (outubro → setembro e agosto; débito antigo com esses meses pagos = acordo, não entra) → abate **um boleto inteiro** (taxa, fundo e água, sem multa/juros); sem registro = zero; não buscar débitos antigos do outro sistema. |
| **R9** Superávit | ≥ R$ 2.000/mês confortável; entre 0 e 2.000 insuficiente (alerta); < 0 déficit. Reajuste sugerido mira a margem mínima. |

Exceções fixas: `PONTUAL_FORA` (combate a incêndio — gasto pontual, fora); `SEMPRE_RECORRENTE`
(extintor — nunca deduzido, aparece como "Recarga de Extintores").

PDF (`relatorio_pdf.py`): considerações com inicial maiúscula por frase; composição de conservação
omite "Outros Materiais"/"Outras despesas" e termina com "etc."; 13ª taxa de administração omitida do texto.
