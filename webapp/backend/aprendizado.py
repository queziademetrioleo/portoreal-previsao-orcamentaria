"""Memória das decisões humanas sobre lançamentos de despesas."""
import hashlib
import re
import unicodedata


def normalizar(texto):
    texto = str(texto or '').lower().strip()
    texto = ''.join(
        char for char in unicodedata.normalize('NFD', texto)
        if unicodedata.category(char) != 'Mn'
    )
    # Números de NF, datas e valores mudam entre relatórios e não identificam
    # a natureza do gasto. O texto restante (fornecedor/serviço) identifica.
    texto = re.sub(r'\b\d+(?:[.,/-]\d+)*\b', ' ', texto)
    texto = re.sub(r'[^a-z0-9]+', ' ', texto)
    return ' '.join(texto.split())


def criar_registro(sessao_id, item_id, item, decisao):
    grupo = normalizar(item.get('grupo'))
    classe = normalizar(item.get('classe'))
    descricao = normalizar(item.get('descricao'))
    assinatura = hashlib.sha256(
        f'{grupo}\x1f{classe}\x1f{descricao}'.encode('utf-8')
    ).hexdigest()
    return {
        'sessao_id': str(sessao_id),
        'lancamento_id': int(item_id),
        'assinatura': assinatura,
        'grupo_norm': grupo,
        'classe_norm': classe,
        'descricao_norm': descricao,
        'decisao': decisao,
    }


def decisao_padrao(item):
    categoria = item.get('categoria_inicial') or item.get('cat') or 'Recorrente'
    if categoria == 'Extraordinaria':
        return 'deduzir'
    if categoria == 'Revisar':
        return 'pendente'
    return 'manter'


def _similaridade(descricao_a, descricao_b):
    tokens_a = set(descricao_a.split())
    tokens_b = set(descricao_b.split())
    if len(tokens_a & tokens_b) < 2:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def encontrar_decisao(item, memorias):
    """Retorna a decisão humana mais compatível ou None.

    As memórias devem vir da mais recente para a mais antiga. Sem descrição
    útil não há generalização: grupo/classe isolados podem conter gastos de
    naturezas diferentes.
    """
    grupo = normalizar(item.get('grupo'))
    classe = normalizar(item.get('classe'))
    descricao = normalizar(item.get('descricao'))
    if not descricao:
        return None

    candidatas = [
        memoria for memoria in memorias
        if memoria.get('grupo_norm') == grupo
        and memoria.get('classe_norm') == classe
        and memoria.get('descricao_norm')
    ]
    for memoria in candidatas:
        if memoria['descricao_norm'] == descricao:
            return memoria['decisao']

    melhor = None
    melhor_score = 0.0
    for memoria in candidatas:
        score = _similaridade(descricao, memoria['descricao_norm'])
        if score >= 0.82 and score > melhor_score:
            melhor = memoria
            melhor_score = score
    return melhor['decisao'] if melhor else None


def aplicar_memorias(itens, memorias):
    aplicados = 0
    for item in itens or []:
        decisao = encontrar_decisao(item, memorias)
        if decisao not in ('deduzir', 'manter'):
            continue
        item['cat'] = 'Extraordinaria' if decisao == 'deduzir' else 'Recorrente'
        item['motivo'] = (
            'Aprendizado humano: lançamento semelhante foi marcado como '
            + ('gasto extraordinário' if decisao == 'deduzir' else 'gasto recorrente')
        )
        item['aprendizado_aplicado'] = True
        aplicados += 1
    return aplicados
