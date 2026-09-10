---
name: alma-integracao
description: Mapeamento dos relatórios Alma para o contrato de dados da previsão orçamentária e controles necessários para preservar a precisão atual
metadata:
  node_type: memory
  type: reference
  updated: 2026-09-10
---

# Integração Alma — preservar o resultado da previsão orçamentária

## Objetivo

Aceitar relatórios do sistema **Alma** sem alterar o motor financeiro já
validado com o **Condo21**. A origem do documento muda; as regras R1–R9, a
aritmética determinística, a classificação assistida por IA e a revisão humana
devem continuar recebendo o mesmo contrato interno de dados.

Não criar um segundo cálculo para Alma. Criar adaptadores específicos que
normalizam os documentos Alma para os objetos `bal`, `des`, `rec`, `inad` e
`sin` já consumidos por `previsao.py`.

## Estado do frontend

O upload já exibe a escolha visual **Condo21** (padrão) ou **Alma** em
`webapp/frontend/src/components/TelaUpload.tsx`. Nesta etapa inicial a escolha
não é persistida, não altera o endpoint e não seleciona parser. A próxima
implementação deve persistir `origem_sistema` na sessão e usar esse campo para
selecionar o adaptador correto.

## Mapeamento confirmado dos documentos Alma

| Contrato atual | Documento Alma | Dados que devem ser extraídos | Situação |
|---|---|---|---|
| `balanual` / `bal` | `Por Período Agrupado Por Contas.xls` | condomínio, período, 12 meses, grupos, contas, total, média, receitas, despesas e saldos | Confirmado |
| `rec02` / `rec` | `Relatório Agrupado por Conta.pdf` | mês de vencimento, contas de receita, valor emitido, valor pago e valor a receber | Confirmado |
| `desbai06` / `des` | `Demonstrativo de Despesas Detalhadas por Grupo de Contas.pdf` | grupo, conta, fornecedor, documento, complemento, forma, vencimento, pagamento, valor e parcela | Confirmado |
| detalhe complementar de `des` | `FIN00601.xlsx` | lançamentos estruturados, recorrência, status, fornecedor, descrição, conta de fluxo e observações | Confirmado com ressalva |
| `inad01` / `inad` | `Relatório Inadimplência.pdf` | unidade, documento, competência, vencimento, valor original, multa, juros, status e totais | Confirmado com ressalva |
| `dessin02` / `sin` | Não identificado | total sintético de despesas para conferência | Pendente |

## Regras por documento

### 1. Balanual Alma

O arquivo possui extensão `.xls`, porém seu conteúdo é **HTML UTF-8**, não
BIFF/Excel. Não pode ser aberto com `xlrd`.

- Identificar pelo título `Demonstrativo Por Período` e pela tabela de período.
- Usar os cabeçalhos `MM/AAAA`, `Total` e `Média`.
- Manter os 12 meses, inclusive os meses zerados; zero é dado válido, não
  ausência de dado.
- Ignorar linhas de subtotal sem nome.
- Preservar grupo e, quando houver, subgrupo; o contrato atual aceita ao menos
  `grupo` e `classe`.
- Separar as seções `(+ ) RECEITAS` e `(-) DESPESAS`.
- Usar o `TOTAL GERAL` de cada seção como `total_receitas` e
  `total_despesas`.

O exemplo analisado é do período 09/2025–08/2026 e tem total de despesas de
R$ 287.522,37.

### 2. REC Alma

O relatório `Contas a Receber Agrupado por Conta` deve ser emitido para um
único mês de vencimento. `VALOR TOTAL` equivale ao **Lançado** do Condo21 e é
a base da previsão; `VALOR TOTAL PAGO` é apenas conferência.

- Taxa condominial: conta cujo nome normalizado representa taxa/tx de
  condomínio, conforme a regra atual.
- Fundo: conta que contém `fundo` e `reserva`.
- O cálculo de receita fixa segue o motor atual: taxa + complemento de taxa
  quando a regra atual o reconhecer + fundo, multiplicados por 12.
- Não usar `VALOR TOTAL RECEBER` como receita prevista, pois ele é saldo em
  aberto e já se relaciona com inadimplência.
- Taxas extras e receitas ocasionais continuam fora da receita fixa, salvo
  decisão explícita da regra vigente.

No exemplo de 09/2026, a receita fixa mensal segundo as regras atuais é
R$ 58.384,29: Taxa R$ 49.944,09 + Complemento R$ 3.445,91 + Fundo R$ 4.994,29.

### 3. Analítico de despesas Alma

O PDF detalhado é o equivalente estrutural do `desbai06`: contém o grupo e
cada lançamento. O XLSX `FIN00601` possui os mesmos lançamentos em formato
mais apropriado para máquina, mas não informa o grupo da conta.

Contrato a produzir por lançamento:

```text
grupo, classe, fornecedor, data, tipo_pgto, valor_lcto, valor_pago, descricao
```

Mapeamento prioritário:

- `grupo`: cabeçalho de grupo no PDF detalhado.
- `classe`: `Contas` no PDF ou `Despesa` no XLSX.
- `fornecedor`: `Fornecedor`.
- `data`: `Dt Pagto`; se ausente, usar data de vencimento apenas com marcação
  explícita de fallback.
- `tipo_pgto`: `Pgto`/`Forma Pgto.`.
- `valor_lcto` e `valor_pago`: `Valor` e `Valor Pago` do XLSX; no PDF o
  campo é `Valor`.
- `descricao`: `Descrição`, seguida de `Observações` quando houver.
- `parcela` e `status`: manter como metadados de auditoria e para a IA.

Não incluir linhas técnicas `TOTAL` do FIN00601 como lançamentos. O sinal
`Pago Recorrente` deve ser enviado como evidência para a classificação, sem
substituir a decisão humana.

### 4. Inadimplência Alma

Mapeamento:

- `Boletos em DD/MM/AAAA` → `data_base`.
- `CLI/UNID` → `unidade`.
- `COMPTO.` → `mes_ref`.
- `VENC` → `vencimento`.
- `VL ORIG` → `valor`.
- `VL PAGTO`, multa, juros, `VL TOTAL`, acordo e status → auditoria.

Nunca usar `VL TOTAL` para abater receita, pois inclui multa e juros.

O relatório analisado foi emitido com `Receita: Todas` e não revela a classe
da cobrança por título. A R8 só pode abater **Taxa de Condomínio**. Para a
integração segura, exigir exportação filtrada em Taxa de Condomínio ou outro
relatório Alma que identifique a conta de receita de cada título.

A criticidade deve ser apurada por competências consecutivas (`COMPTO.`) por
unidade, e o abatimento continua limitado a uma única taxa mensal por unidade
crítica.

## Controle de reconciliação obrigatório

Antes de rodar as regras financeiras, o adaptador deve produzir controles
auditáveis e bloquear ou alertar a análise quando falharem:

1. Condomínio e período devem ser compatíveis em todos os documentos.
2. Total de despesas do balanual = total do demonstrativo detalhado.
3. Totais por grupo do demonstrativo detalhado devem conferir com o balanual.
4. REC deve representar um único mês e ter Taxa/Fundo identificados.
5. O relatório de inadimplência deve conter a classe Taxa de Condomínio ou
   uma confirmação operacional equivalente.
6. Linhas de subtotal, cabeçalho e total não podem virar lançamentos.
7. Períodos com meses zerados devem ser mantidos, sem preencher valores.

## Pendências que bloqueiam produção Alma

1. Identificar o equivalente Alma do `dessin02` (sintético de despesas).
2. Explicar a diferença de R$ 285,90 entre o FIN00601 (R$ 287.236,47) e o
   PDF detalhado/balanual (R$ 287.522,37). Até isso ser resolvido, o PDF é a
   fonte de total e grupo; o XLSX é apenas complemento de detalhe.
3. Confirmar exportação de inadimplência filtrada por Taxa de Condomínio ou
   fornecer relatório com classe da cobrança por título.
4. Se existir, pedir exportação XLSX do demonstrativo detalhado já com a
   coluna de grupo. Isso elimina a necessidade de derivar grupos de PDF.

## Estratégia de implementação e validação

1. Adicionar `origem_sistema` à sessão e ao formulário, com `condo21` como
   padrão retrocompatível.
2. Criar `parsers_alma.py` isolado dos parsers Condo21.
3. Normalizar Alma para o contrato interno existente antes de chamar
   `analisar()` e `recalcular()`.
4. Guardar no estado o documento-fonte e metadados de extração para auditoria.
5. Manter IA somente para classificação semântica; parsing de estrutura e
   aritmética devem ser determinísticos.
6. Rodar em modo sombra com previsões manuais já aprovadas: comparar total de
   despesa, receita, deduções por regra, subtotal e previsão final.
7. Liberar somente quando a divergência da previsão final continuar dentro da
   meta atual de R$ 1.000 e todas as reconciliações passarem.

## Arquivos analisados em 10/09/2026

- `/Users/Usuario/Downloads/Por Período Agrupado Por Contas.xls`
- `/Users/Usuario/Downloads/Relatório Inadimplência.pdf`
- `/Users/Usuario/Downloads/Relatório Agrupado por Conta.pdf`
- `/Users/Usuario/Downloads/FIN00601 (1).xlsx`
- `/Users/Usuario/Downloads/Demonstrativo de Despesas Detalhadas por Grupo de Contas.pdf`
