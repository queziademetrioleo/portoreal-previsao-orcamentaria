# Briefing — Feedback do CEO (apresentação do MVP)

> Notas coletadas na apresentação do MVP ao CEO da Porto Real, organizadas por tema,
> cruzadas com o comportamento atual do sistema. Data da apresentação: julho/2026.

---

## 1. Fontes de dados

### 1.1 Novo documento de entrada: REC
**Nota:** "Taxa de Condomínio deve ser pega do DOCUMENTO REC e não do balanço anual, pois o REC traz o valor REAL e atual do modelo do condomínio."

- **Hoje:** a receita (taxa de condomínio) vem do `balanual.xls` (seção Receitas).
- **Mudança:** adicionar o REC como 5º arquivo de upload e usar ele como fonte da taxa de condomínio. O balanço anual passa a ser usado só para despesas (e histórico).
- **Impacto:** `webapp/backend/main.py` (upload), `previsao.py` (novo parser), `ia_parser.py`, frontend (tela de upload).

❓ **Confirmar:** qual export exato do Condomínio21 é o "REC"? Obrigatório ou opcional (com fallback para o balanço)?

---

## 2. Regras de cálculo

### 2.1 R2 — Rescisão e indenização: dedução incondicional
**Nota:** "Rescisão e indenização SEMPRE saem do nosso balanço."

- **Hoje:** R2 já deduz 100%, mas itens ambíguos podem cair na fila de revisão da IA.
- **Mudança:** garantir que rescisão/indenização nunca vá para revisão — dedução determinística, sem passar pela IA.

### 2.2 Seguro incêndio: pro-rata por parcelas no ano
**Nota:** "Se estiver dentro do mesmo ano, mantemos o valor integral; se não, calcular o número de parcelas NAQUELE ano. Ex.: 12x."

- **Hoje:** seguro é preservado integralmente (exceção dentro da R4).
- **Mudança:** detectar a vigência/parcelamento da apólice. Se a vigência cruza o ano da previsão, projetar só as parcelas que caem naquele ano.
- **Dependência:** precisa da data/parcelamento da NF do seguro (desbai06 traz? senão, pedir input na revisão humana).

### 2.3 Taxa de 10% sobre TODAS as despesas
**Nota:** "Taxa de 10% em cima DE TODAS as despesas."

- **Hoje:** R7 aplica +10% sobre o **subtotal ajustado** (depois das deduções R1–R6).
- **Mudança:** aplicar sobre todas as despesas.

❓ **Confirmar:** 10% sobre o total bruto de despesas (antes das deduções) ou a intenção é só garantir que nenhuma categoria escape do +10%? Muda materialmente o resultado.

### 2.4 Superávit: faixa de atenção
**Nota:** "Superávit é sempre acima de R$2.000. Entre 0 e 2.000, marcar em amarelo com adendo de atenção."

- **Hoje:** não existe classificação de superávit.
- **Mudança:** regra nova de apresentação:
  - `> R$2.000` → superávit (verde/normal)
  - `R$0 – R$2.000` → superávit em **amarelo** + adendo de atenção
  - `< R$0` → déficit
- **Impacto:** `gerador_previsao.py` (formatação do xlsx) + interface de revisão.

### 2.5 Cenários com e sem fundo de reserva
**Nota:** "SEMPRE calcular com fundo de reserva e SEM fundo de reserva."

- **Hoje:** um único cálculo.
- **Mudança:** o documento final apresenta os dois cenários lado a lado (ou duas seções).

❓ **Confirmar:** percentual do fundo de reserva vem do REC / convenção de cada condomínio? É fixo (ex.: 10%)?

### 2.6 Provisões R4/R5 — REMOVER
**Nota:** "Provisão Laudo Autovistoria NÃO ENTRA. Provisão Sistema de Incêndio/Registro NÃO ENTRA. Tirar as duas, pois não entram nessa categorização."

- **Hoje:** R4/R5 zeram os grupos e realocam como provisões (`prov_laudo`, `prov_incendio`), inclusive com linhas próprias no xlsx (`gerador_previsao.py:723-728`).
- **Mudança:** eliminar as duas provisões do cálculo e do documento.
- **Atenção:** ver 2.7 — o destino de "Despesas Diversas" muda junto.

### 2.7 Despesas Diversas → Conservação
**Nota:** "Despesas Diversas entra em CONSERVAÇÃO."

- **Hoje:** R4 zerava Despesas Diversas (exceto seguro) e virava provisão de laudo.
- **Mudança:** com R4/R5 removidas, Despesas Diversas passam a ser somadas na categoria **Conservação** — sem alterar o total, só a categorização.

---

## 3. Documento final / relatório

### 3.1 Itens 2 e 3 — base em Despesas de Conservação
**Nota:** "O item 2 é baseado na demonstração da planilha balanço anual em despesas de conservação. O item 3 também — mas NÃO entra a despesa administrativa."

- **Mudança:** itens 2 e 3 do relatório derivam do grupo Despesas de Conservação do balanço anual; item 3 exclui despesa administrativa.

❓ **Confirmar:** "itens 2 e 3" referem-se às Considerações Importantes do xlsx ou às seções do parecer executivo? Pedir um exemplo do documento manual para replicar.

### 3.2 Item 8 — texto fixo
**Nota:** "8) é sempre fixo."

❓ **Confirmar:** obter o texto exato do item 8 no modelo manual da Porto Real.

### 3.3 Material de Limpeza — faltou no relatório final
**Nota:** "Pulou material de limpeza no relatório final de análise."

- **Bug:** a linha existe no gerador (`gerador_previsao.py:678`) mas não apareceu no documento gerado. Investigar o matching (`_acha_linha`/tokens) com o nome real da conta desse condomínio.

### 3.4 Seguro de Incêndio — faltou no relatório de despesas
**Nota:** "Seguro de Incêndio faltou no relatório de despesas."

- **Bug:** mesma natureza do 3.3 — linha prevista em `gerador_previsao.py:684-685`, mas não saiu. Investigar juntos.

### 3.5 Contrato de Manutenção — detalhar composição
**Nota:** "Precisa de mais detalhes, para saber o que está incluso ali."

- **Mudança:** abrir o item "Contrato de Manutenção" mostrando as NFs/contratos que o compõem (fornecedor, objeto, valor mensal). Dados já existem no desbai06.

---

## 4. Plano de implementação sugerido

| Fase | Escopo | Itens |
|------|--------|-------|
| **F1 — Bugs** (rápido, sem depender de confirmação) | Matching de linhas do relatório | 3.3, 3.4 |
| **F2 — Recategorização** | Remover provisões R4/R5, Diversas → Conservação, R2 incondicional | 2.6, 2.7, 2.1 |
| **F3 — Novas regras de cálculo** | Superávit em faixas, seguro pro-rata, 10% sobre todas as despesas, cenários com/sem fundo | 2.4, 2.2, 2.3, 2.5 |
| **F4 — Fonte REC** | Novo upload + parser + taxa de condomínio via REC | 1.1 |
| **F5 — Relatório** | Itens 2/3/8, detalhamento contrato de manutenção | 3.1, 3.2, 3.5 |

### Pré-requisitos (perguntas em aberto)
1. Exemplo do **documento REC** (arquivo real de um condomínio).
2. Definição do **10%**: sobre bruto ou sobre subtotal ajustado, ver 2.3.
3. **Texto fixo do item 8** e um exemplo do documento manual com os itens numerados (2, 3, 8).
4. Regra do **fundo de reserva** (percentual, fonte).
5. Seguro: onde obter **vigência/parcelamento** da apólice.

### Documentação a atualizar junto
- `README.md` (tabela R1–R8: R4/R5 mudam, R7 muda)
- `memory/r4-r5-provisoes.md` (regra deixa de existir como provisão)
- `memory/r7-inflacao.md` (base de cálculo dos 10%)
