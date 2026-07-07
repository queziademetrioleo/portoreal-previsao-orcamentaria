# Plano de Execução — Ajustes pós-apresentação ao CEO (Porto Real)

> Escopo confirmado em 06-07/07/2026. 5 itens de trabalho, ordenados do MAIS DIFÍCIL
> ao MAIS FÁCIL, para execução 1 por 1. Cada item: comportamento atual (arquivo:linha),
> mudança exata, critério de aceite e teste.
>
> **Validação transversal:** após cada item que toca cálculo ou documento, rodar os 4
> condomínios de referência (Barramares, Chateau Lavoisier, Rive Gauche I, Sophia I —
> `~/Downloads/Quezia - Previsão Orçamentária/`) e conferir que o TOTAL não mudou
> (itens 3, 4 e 5 não alteram totais; itens 1 e 2 alteram por design).

---

## Mapa do código

| Responsabilidade | Local |
|---|---|
| Motor de regras R1–R8 (função de cálculo) | `previsao.py:1134-1235` |
| Taxa de inflação (constante global) | `previsao.py:786` (`INFLACAO`, env `PREVISAO_INFLACAO_PCT`, default 4,72%) |
| Dicionário `R` (subtotal, provisões, linhas) | `previsao.py:1353-1360` |
| API — sessão, recálculo, geração | `webapp/backend/main.py` (`_recalcular_com_decisoes:285`, endpoints `:445-680`) |
| xlsx — caminho template | `gerador_previsao.py:300` (provisões em `:423-446`) |
| xlsx — caminho adaptativo | `gerador_previsao.py:638-747` (provisões em `:723-728`) |
| Interface de revisão/resumo | `webapp/frontend/src/App.tsx` |

⚠️ **Toda mudança de documento (itens 3 e 5) tem que ser aplicada nos DOIS caminhos
de geração** (template e adaptativo) — é o erro mais fácil de cometer neste projeto.

---

## ITEM 1 — Cenários COM e SEM fundo de reserva na interface final 🔴 mais difícil

**O que o CEO quer:** na interface final, poder ver os números com fundo de reserva
e sem fundo de reserva.

**Atual:** o sistema não tem nenhuma noção de fundo de reserva. Cálculo único.

**Pré-requisito (única pergunta em aberto do plano inteiro):**
❓ Como a Porto Real calcula o fundo de reserva? Hipótese padrão de mercado:
percentual sobre a taxa condominial (tipicamente 10%), definido na convenção de cada
condomínio. Confirmar: percentual fixo ou por condomínio? Incide sobre o quê?

**Mudança:**
1. **Motor** (`previsao.py`): novo parâmetro `fundo_reserva_pct` (default 0.10, env
   `PREVISAO_FUNDO_RESERVA_PCT`). O `R` retornado ganha:
   ```
   R['cenarios'] = {
     'sem_fundo': {'total_previsto': X, 'taxa_mensal': X/12, 'resultado': ...},
     'com_fundo': {'total_previsto': X*(1+fr), 'taxa_mensal': ..., 'resultado': ...},
   }
   ```
   As despesas são idênticas nos dois cenários — o que muda é o valor a arrecadar
   (e portanto o rateio/resultado).
2. **Backend** (`main.py`): estado da sessão guarda `fundo_reserva_pct`; o payload do
   resumo (`_montar_estado:349`) expõe os dois cenários.
3. **Frontend** (`App.tsx`): no resumo final, toggle "Com fundo de reserva / Sem fundo
   de reserva" alternando os números exibidos (total anual, mensal, resultado). O
   percentual aparece ao lado, editável (mesmo padrão do item 2 — inflação).
4. **xlsx** (`gerador_previsao.py`): documento final apresenta os dois valores —
   sugestão: duas linhas ao final da PREVISÃO ("Total sem fundo de reserva" /
   "Total com fundo de reserva (X%)"). Validar layout com um exemplo manual da
   Porto Real se disponível.

**Por que é o mais difícil:** atravessa as 4 camadas (motor → API → frontend → xlsx),
cria o conceito de "cenário" que não existe na estrutura de dados, e depende de uma
definição de negócio externa.

**Aceite:**
- Toggle na interface alterna os números; diferença entre cenários = exatamente o FR.
- xlsx exibe os dois totais.
- Despesas idênticas entre cenários (assert em teste).

**Esforço:** ~2-3 sessões. **Depende de:** resposta sobre a regra do FR (dá para
implementar com 10% default e deixar o percentual editável, eliminando o bloqueio).

---

## ITEM 2 — Inflação editável na interface, com recálculo automático 🟠

**O que o CEO quer:** alterar o número da inflação na interface e ver todos os valores
recalculados automaticamente.

**Atual:** `INFLACAO` é constante global lida do env no boot (`previsao.py:786`),
usada em `previsao.py:1235` (`total_previsto = subtotal * (1 + INFLACAO)`) e nos
textos do parecer (`:332`). Nenhum caminho para o usuário alterá-la. Detalhe: código
usa 4,72% default; README anuncia 10% — o campo editável resolve a ambiguidade
(CEO define na tela), mas o default deve virar **0.10** conforme feedback ("taxa de
10% em cima de todas as despesas").

**Mudança:**
1. **Motor**: transformar em parâmetro — a função de cálculo recebe `inflacao_pct`
   (fallback: env atual). Remover leituras diretas da global no corpo.
2. **Backend**:
   - Estado da sessão ganha `inflacao_pct` (default 0.10).
   - `POST /api/sessao/{sid}/preview` e `salvar-decisoes` aceitam `inflacao_pct` no
     payload; `_recalcular_com_decisoes` (`main.py:285`) repassa ao motor.
     (A infraestrutura de recálculo JÁ EXISTE — é o mesmo fluxo usado quando o
     usuário aprova/reprova itens. Só falta o parâmetro viajar junto.)
   - `gerar`/`download` usam o valor salvo na sessão.
3. **Frontend** (`App.tsx`): campo numérico "Inflação (%)" no resumo, com debounce →
   chama o preview → atualiza total previsto, mensal e resultado na tela. Sem F5,
   sem reenviar arquivos.
4. **Textos**: parecer IA e Considerações do xlsx passam a interpolar o percentual da
   sessão, não a constante.

**Por que é o 2º mais difícil:** exige refatorar a constante global em parâmetro que
atravessa motor → sessão → recálculo → geração, e o recálculo reativo na UI. Mas a
malha de recálculo já existe, o que tira boa parte do risco.

**Aceite:**
- Mudar 10% → 12% na tela atualiza o total exibido em segundos, sem re-upload.
- xlsx gerado depois reflete 12% (linha de inflação e total).
- Sessão recarregada mantém o valor escolhido.

**Esforço:** ~1-2 sessões. **Depende de:** nada.

---

## ITEM 3 — Provisões fora do documento final + Despesas Diversas em Conservação 🟡

> Dois feedbacks acoplados — executar juntos porque mexem nas mesmas linhas do gerador.

**O que o CEO quer:**
(a) "Provisão Laudo Autovistoria" e "Provisão Sistema de Incêndio/Registro" **não
devem aparecer** no índice de despesas do documento gerado — o dado é inócuo ali.
(b) Despesas Diversas entra na categoria **CONSERVAÇÃO**.

**Importante:** o cálculo NÃO muda. Hoje o subtotal já soma as provisões de volta
(`previsao.py:1234`: `subtotal = Σ finais + prov_laudo + prov_incendio`), então o
total permanece idêntico — a mudança é só de APRESENTAÇÃO: esses valores deixam de
ter linhas próprias e passam a compor a linha de Conservação.

**Atual:**
- Caminho adaptativo: provisões viram linhas próprias em `gerador_previsao.py:723-728`;
  Diversas vira "Outras despesas diversas" (`:686-687`); Conservação em `:680-681`.
- Caminho template: provisões escritas em linhas do template em `:423-446`
  (`_acha_linha('laudo','autovistoria')` etc.).
- Atenção à linha de reconciliação "Ajustes de previsão" (`:743-747`): se as provisões
  sumirem das linhas sem serem realocadas, a diferença cai ali e aparece um "Ajustes"
  gigante no documento — realocar, não deletar.

**Mudança (caminho adaptativo):**
1. Deletar o bloco `:723-728` (linhas de provisão).
2. Somar `prov_laudo + prov_incendio` ao valor da categoria "Gastos com conservação".
3. Predicado de "Gastos com conservação" passa a incluir `'diversas' in _ng(ln)`
   (exceto a linha de seguro, que tem categoria própria — ver item 5).
4. Remover a categoria "Outras despesas diversas" da lista.

**Mudança (caminho template):**
5. Deletar o bloco `:423-446`; garantir que `_classes_do_grupo` (`:326`) role Diversas
   para dentro de Conservação com os mesmos critérios.

**Mudança (frontend, se aplicável):** conferir se `App.tsx` exibe as provisões no
resumo e remover/realocar da mesma forma.

**Aceite:**
- Nenhum xlsx gerado (pelos dois caminhos) contém as duas linhas de provisão.
- Valor de "Gastos com conservação" = valor antigo + Diversas + provisões.
- Subtotal e total previsto EXATAMENTE iguais aos de antes da mudança (teste de
  regressão nos 4 condomínios).
- Linha "Ajustes de previsão" não aparece (ou permanece com o valor residual antigo).

**Esforço:** ~1 sessão. **Depende de:** item 5 feito antes ajuda (o predicado do
seguro precisa estar correto para a exceção do passo 3 funcionar) — por isso, na
prática, executar o 5 primeiro se preferir começar pelo fácil.

---

## ITEM 4 — Faixa de atenção do superávit (0 a R$1.999) 🟢

**O que o CEO quer:** superávit "de verdade" é acima de R$2.000. Entre R$0 e R$1.999,
mostrar mensagem: *"Por mais que o valor esteja em superávit, o mesmo não é
suficiente"* — com explicação do porquê.

**Atual:** o sistema não classifica nem confronta resultado (receita − previsão).

**Mudança:**
1. **Motor** (`previsao.py`): calcular `resultado = receita_anual − total_previsto`
   (receita: `bal['total_receitas']`) e classificar:
   - `>= 2000` → `'superavit'`
   - `0 a 1999,99` → `'superavit_insuficiente'`
   - `< 0` → `'deficit'`
   Constante `SUPERAVIT_MINIMO = 2000` (env `PREVISAO_SUPERAVIT_MIN`).
   Adicionar `resultado` e `status_resultado` ao `R`.
2. **Texto da mensagem** (usar nos dois lugares — xlsx e interface):
   > "Atenção: embora a previsão aponte superávit de R$ X, o valor é inferior a
   > R$ 2.000 e não constitui margem de segurança suficiente. Qualquer despesa
   > imprevista (manutenção corretiva, reajuste de contrato, inadimplência) pode
   > converter o resultado em déficit. Recomenda-se avaliar reajuste da taxa
   > condominial ou reforço do fundo de reserva."
3. **xlsx** (`gerador_previsao.py`): célula do resultado com destaque amarelo
   (`PatternFill fgColor='FFF3CD'`) + a mensagem nas Considerações Importantes
   (`_adicionar_consideracoes:84` — passar `R` como parâmetro, hoje só recebe `ws, ano`).
4. **Frontend**: badge no resumo — verde (≥2.000), amarelo com a mensagem (0–1.999),
   vermelho (déficit).
5. **Interação com item 1**: quando os cenários existirem, o status é calculado POR
   CENÁRIO (com FR pode ser superávit e sem FR insuficiente). Se o item 4 for feito
   antes do 1, calcular sobre o cenário único atual e estender depois.

**Aceite:** teste unitário das 3 faixas (2000→verde, 1999,99→amarelo, −0,01→vermelho);
xlsx de caso sintético mostra célula amarela e a mensagem; badge correto na UI.

**Esforço:** ~1 sessão. **Depende de:** nada (interage com item 1, mas não bloqueia).

---

## ITEM 5 — Bugs: Material de Limpeza e Seguro de Incêndio ausentes no relatório 🟢 mais fácil

**O que o CEO viu:** o relatório final pulou "Material de Limpeza", e "Seguro de
Incêndio" não apareceu no relatório de despesas.

**Causa provável (diagnóstico já feito):**
- Seguro: o predicado em `gerador_previsao.py:684-685` exige `'seguro' E 'incendio'`
  no nome da classe. Mas o motor (`previsao.py:1153`) trata contas chamadas apenas
  "Seguro" — quando a classe não contém "incendio", o valor cai em "Outras despesas
  diversas" e a linha própria some.
- Material de Limpeza: mesmo padrão — predicado `:678-679` exige `'material' E
  'limpeza'`; se a conta se chama "Mat. Limpeza", "Produtos de Limpeza" etc., falha
  e a linha é engolida pelo fallback genérico (`:731-741`).

**Passos:**
1. **Reproduzir**: rodar o condomínio da demo e logar `_norm(grupo)/_norm(classe)` de
   todas as linhas ativas — confirmar os nomes reais que não bateram.
2. **Corrigir predicados** conforme os nomes encontrados:
   - Seguro: `'seguro' in _nc(ln)` (com exclusão explícita de "seguro de vida" se
     existir nos 4 condomínios).
   - Limpeza: aceitar variações (`'limpeza' in _nc(ln)` combinado com
     `material/mat/produto/higiene`).
3. **Verificar o caminho template também**: se a demo usou `_gerar_via_template`, o
   matching relevante é `_acha_linha` (`:428`) / `_tokens` (`:56`) — aplicar a mesma
   flexibilização lá.
4. **Teste de regressão**: para os 4 condomínios, assert de que nenhuma linha ativa
   contendo "limpeza" ou "seguro" no nome termina no fallback genérico ou em "Outras
   despesas diversas".

**Aceite:** relatório do condomínio da demo exibe as duas linhas com os valores
corretos; total inalterado (é só realocação de linha).

**Esforço:** ~meia sessão a 1 sessão. **Depende de:** nada. Não muda nenhum cálculo.

---

## Ordem de execução

Ordenado por dificuldade (pedido do CEO/Quezia): **1 → 2 → 3 → 4 → 5**.

Recomendação técnica se preferir destravar valor rápido: **inverter (5 → 4 → 3 → 2 → 1)** —
os três primeiros saem em ~2 sessões sem nenhuma dependência externa, e o item 5
feito antes simplifica a exceção do seguro no item 3. A ordem é indiferente para o
resultado final; só o item 1 tem pergunta aberta (regra do fundo de reserva), que
pode ser contornada com percentual editável default 10%.

## Fora deste ciclo (feedbacks anteriores do CEO ainda em aberto)

Guardados no `BRIEFING-FEEDBACK-CEO.md`, aguardando insumos da Porto Real:
- Documento REC como fonte da taxa de condomínio (precisa de exemplos do arquivo)
- Itens numerados 2/3/8 do documento manual (precisa do modelo com texto exato)
- Seguro incêndio pro-rata por parcelas no ano (precisa saber onde obter vigência)
- Detalhamento do Contrato de Manutenção (fornecedores/objeto)
- R2 travado (rescisão/indenização sem opção de reprovar na revisão)

## Documentação a atualizar ao concluir

- `README.md`: R7 (inflação editável, default 10%), R4/R5 (provisões não aparecem no
  documento; Diversas → Conservação), novo recurso de cenários com/sem FR
- `memory/r7-inflacao.md` e `memory/r4-r5-provisoes.md`: refletir o novo comportamento
- Novos: `memory/r9-superavit.md`, `memory/r10-fundo-reserva.md`
