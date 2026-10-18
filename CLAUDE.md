# Previsão Orçamentária — instruções para agentes

Leia primeiro `memory/estado-atual.md` (estado vivo) e `memory/regras.md` (regras do motor).

## Manutenção da memória (obrigatório)

A cada mudança de código ou decisão de negócio, **no mesmo commit**:
- atualize `memory/estado-atual.md` (seções "Último trabalho" e "Próximos passos"; remova o que ficou velho);
- se mexer em regra de cálculo ou texto do PDF, atualize `memory/regras.md`;
- não crie arquivos de "retomada"/sessão novos — o histórico fica no `git log`.

## Higiene do repositório

- Dados de clientes, backups de produção e saídas de conferência ficam em `tmp/`, `output/`, `outputs/`
  (ignorados pelo git). Nunca commitar documentos financeiros nem estados de sessão.
- Scripts de depuração descartáveis vão em `tmp/`, não na raiz.
- Push não é deploy: o EasyPanel exige rebuild manual. Só fazer push/deploy com autorização explícita.
