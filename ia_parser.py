#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IA-POWERED PARSING para Previsão Orçamentária
Substitui os 4 parsers rígidos por uma única chamada à Claude API.

A IA lê o dump textual dos .xls e retorna JSON estruturado,
adaptando-se automaticamente à estrutura de cada condomínio.

Uso:
    from ia_parser import ia_parse_pasta
    dados = ia_parse_pasta("/pasta/Barramares 2026")
    # dados['bal']['despesas']  → lista de contas com monthly, total, etc.
    # dados['des']['itens']     → itens do desbai classificados
    # dados['sin']['grand_total']
    # dados['inad']['itens']
"""

import os, sys, json, re, datetime, unicodedata, warnings
warnings.filterwarnings('ignore')
import xlrd

# ---------------------------------------------------------------------------
# Helpers — reusados do previsao.py
# ---------------------------------------------------------------------------
def _norm(s):
    s = str(s or '').lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')

def _num(v):
    try:
        f = float(v)
        return f if abs(f) > 1e-10 else 0.0
    except Exception:
        return 0.0

def _xldate(wb, v):
    try:
        return datetime.datetime(*xlrd.xldate_as_tuple(v, wb.datemode)).date()
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Dump de .xls para texto (a IA consome)
# ---------------------------------------------------------------------------
def _dump_xls(path, max_rows=None):
    """Converte um .xls em texto tabular legível pela IA.
    Formato: R0: C0=valor | C1=valor | ...
    """
    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_index(0)
    lines = []
    limit = max_rows or sh.nrows
    for r in range(min(sh.nrows, limit)):
        parts = []
        for c in range(sh.ncols):
            v = sh.cell_value(r, c)
            if v is None or v == '':
                continue
            if isinstance(v, float):
                if abs(v) < 1e-10:
                    continue
                parts.append(f"C{c}={v:.2f}")
            else:
                s = str(v).strip()
                if s:
                    parts.append(f"C{c}={s}")
        if parts:
            lines.append(f"R{r}: " + " | ".join(parts))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Schema do JSON que a IA deve retornar
# ---------------------------------------------------------------------------
SYSTEM_DUMP_PROMPT = """\
Você é um extrator de dados contábeis de condomínios. Seu trabalho é ler o dump textual
de arquivos .xls exportados do sistema Condomínio21 e extrair TODOS os dados estruturados.

Você receberá o dump de até 4 arquivos:
  - balanual.xls  (demonstrativo anual de receitas e despesas)
  - desbai06.xls  (despesas por grupo e classe — lançamentos individuais)
  - dessin02.xls  (sintético de despesas)
  - inad01.xls    (inadimplência)

Retorne APENAS um JSON válido (sem markdown, sem comentários) com esta estrutura exata:

{
  "bal": {
    "receitas": [
      {"grupo": "Receitas Operacionais", "classe": "Tx. Condomínio",
       "monthly": [100.0, 200.0, ...], "total": 1200.0, "n_meses": 12}
    ],
    "despesas": [
      {"grupo": "Despesas com Pessoal", "classe": "Salário Empregado(s)",
       "monthly": [5000.0, 5000.0, ...], "total": 60000.0, "n_meses": 12}
    ],
    "total_receitas": 50000.0,
    "total_despesas": 40000.0,
    "meses": ["12/2024", "01/2025", ...],
    "n_meses": 12
  },
  "des": {
    "itens": [
      {"grupo": "Conservação", "classe": "Manutenção Elétrica",
       "fornecedor": "ELETRICISTA LTDA", "data": "2025-03-15",
       "valor_lcto": 500.0, "valor_pago": 500.0,
       "descricao": "Conserto do quadro de luz do Hall"}
    ]
  },
  "sin": {"grand_total": 40000.0},
  "inad": {
    "data_base": "2025-11-30",
    "itens": [
      {"unidade": "B-402 — FERNANDO", "classe": "Tx. Condomínio",
       "mes_ref": "01/2025", "vencimento": "2025-01-10",
       "valor": 500.0, "meses_atraso": 10}
    ],
    "total": 5000.0
  }
}

REGRAS DE EXTRAÇÃO:

### balanual.xls
- A planilha tem 2 seções: "DEMONSTRATIVO ANUAL DE RECEITAS" e "DEMONSTRATIVO ANUAL DE DESPESAS"
- Cada seção tem cabeçalho com meses (MM/AAAA) nas colunas + coluna "Total" + coluna "Média"
- As linhas de GRUPO (ex: "Despesas com Pessoal") têm texto em C0 mas valores ZERADOS — pule-as (só são labels)
- As linhas de CONTA (ex: "Salário Empregado(s)") têm nome em C0 e valores mensais nas colunas de mês
- Cada conta pertence ao grupo imediatamente acima dela
- "monthly": array com os 12 valores mensais (na ordem das colunas, da esquerda pra direita)
- "total": soma dos 12 meses (ou valor da coluna Total se existir)
- "n_meses": quantos meses tiveram valor > 0
- "total_receitas": valor da linha "Total:" na seção de receitas
- "total_despesas": valor da linha "Total:" na seção de despesas
- "meses": labels das colunas de mês (ex: ["12/2024", "01/2025", ...])

### desbai06.xls
- Extraia TODOS os itens (lançamentos) — cada linha com data numérica em C4 é um item
- "grupo": nome do grupo (linha de cabeçalho de grupo — texto em C0 sem data)
- "classe": nome da classe (subtítulo de grupo — texto em C0 após o grupo)
- "data": data do pagamento (C4 convertida de serial Excel)
- "valor_lcto": valor em C7 (coluna 7)
- "valor_pago": valor em C8 (coluna 8); se zero ou vazio, use valor_lcto
- "descricao": texto em C9 (coluna 9) — histórico/fornecedor

### dessin02.xls
- Ache "Total Geral:" ou o maior "Total:" — esse é o grand_total

### inad01.xls
- "data_base": data após "até" no cabeçalho (formato DD/MM/AAAA)
- "itens": cada linha com mês ref (MM/AAAA) em C4 e vencimento (serial) em C5
- "unidade": código + nome do devedor (ex: "B-402 — FERNANDO ROBERTO")
- "mes_ref": mês de referência (C4)
- "vencimento": data de vencimento (C5 convertida)
- "valor": valor em C6
- Calcule "meses_atraso": (data_base - vencimento) em meses

IMPORTANTE:
- Extraia TODOS os itens, sem pular nenhum
- Valores zerados: retorne 0, não pule o item
- Datas: converta números seriais do Excel para ISO 8601 (YYYY-MM-DD)
- Se um arquivo estiver ausente (dump "NÃO ENCONTRADO"), retorne null para aquela seção
"""


# ---------------------------------------------------------------------------
# Função principal: parse IA
# ---------------------------------------------------------------------------
def ia_parse_pasta(pasta):
    """Parse todos os .xls de uma pasta usando IA.
    Retorna dict com 'bal', 'des', 'sin', 'inad' — mesmo schema dos parsers antigos.
    Se IA falhar, faz fallback para os parsers rígidos.
    """
    arquivos = {
        'balanual': os.path.join(pasta, 'balanual.xls'),
        'desbai06': os.path.join(pasta, 'desbai06.xls'),
        'dessin02': os.path.join(pasta, 'dessin02.xls'),
        'inad01':   os.path.join(pasta, 'inad01.xls'),
    }

    # Montar prompt com dump de cada arquivo
    partes = []
    for nome, path in arquivos.items():
        if os.path.exists(path):
            max_r = None if nome != 'desbai06' else 2000  # desbai pode ser enorme
            dump = _dump_xls(path, max_rows=max_r)
            partes.append(f"=== {nome}.xls ===\n{dump}")
            if nome == 'desbai06' and max_r:
                # avisar se foi truncado
                wb = xlrd.open_workbook(path)
                total_rows = wb.sheet_by_index(0).nrows
                if total_rows > max_r:
                    partes.append(f"[TRUNCADO: {total_rows} linhas no total, mostrando primeiras {max_r}]")
        else:
            partes.append(f"=== {nome}.xls ===\nNÃO ENCONTRADO")

    prompt = "\n\n".join(partes)

    print(f"   🤖 IA analisando {len(prompt)} caracteres de dados brutos...")
    resp = _call_ia(SYSTEM_DUMP_PROMPT, prompt, max_tokens=16000)
    if resp is None:
        print("   ⚠️  IA indisponível — usando parsers rígidos como fallback")
        return None

    # Extrair JSON da resposta
    dados = _extrair_json(resp)
    if dados is None:
        print("   ⚠️  IA retornou JSON inválido — usando parsers rígidos como fallback")
        return None

    # Validar estrutura mínima
    if 'bal' not in dados:
        print("   ⚠️  JSON da IA sem campo 'bal' — fallback para parsers rígidos")
        return None

    # Pós-processamento: garantir tipos e defaults
    return _pos_processar(dados)


# ---------------------------------------------------------------------------
# Chamada à Claude API (reusa as funções do previsao.py)
# ---------------------------------------------------------------------------
def _call_ia(system, user, max_tokens=16000):
    """Chama a Claude API. Retorna texto ou None."""
    try:
        # Tenta importar as funções do previsao.py
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import previsao as core
        if core._ia_disponivel():
            return core._claude_chat(system, user, max_tokens=max_tokens)
    except Exception as e:
        pass

    # Fallback: chave direta
    key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not key:
        key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chave_claude.txt')
        if os.path.exists(key_file):
            for line in open(key_file, encoding='utf-8'):
                line = line.strip()
                if line and not line.startswith('#'):
                    key = line
                    break
    if not key:
        return None

    try:
        import urllib.request
        model = os.environ.get('PREVISAO_IA_MODELO', 'claude-opus-4-8')
        body = {
            'model': model,
            'max_tokens': max_tokens,
            'system': system,
            'messages': [{'role': 'user', 'content': user}]
        }
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=json.dumps(body).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'x-api-key': key,
                'anthropic-version': '2023-06-01'
            }
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode('utf-8'))
        return ''.join(b.get('text', '') for b in data.get('content', [])
                       if b.get('type') == 'text')
    except Exception as e:
        print(f"   ❌ Erro na chamada IA: {e}")
        return None


def _extrair_json(texto):
    """Extrai objeto JSON de uma resposta que pode conter markdown."""
    # Tenta parse direto
    try:
        return json.loads(texto)
    except Exception:
        pass
    # Tenta extrair de bloco ```json
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', texto, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Tenta encontrar o primeiro { ... } completo
    try:
        inicio = texto.index('{')
        fim = texto.rindex('}') + 1
        return json.loads(texto[inicio:fim])
    except Exception:
        pass
    return None


def _pos_processar(dados):
    """Garante tipos corretos e preenche defaults no JSON retornado pela IA."""
    bal = dados.get('bal', {})
    des = dados.get('des', {})
    sin = dados.get('sin', {})
    inad = dados.get('inad', {})

    # bal: garante arrays e tipos numéricos
    for sec in ('receitas', 'despesas'):
        if sec not in bal:
            bal[sec] = []
        for item in bal[sec]:
            item['total'] = _num(item.get('total', 0))
            item['n_meses'] = int(item.get('n_meses', 0))
            item['monthly'] = [_num(v) for v in item.get('monthly', [])]
            item['grupo'] = item.get('grupo', '') or ''
            item['classe'] = item.get('classe', '') or ''

    bal['total_receitas'] = _num(bal.get('total_receitas', 0))
    bal['total_despesas'] = _num(bal.get('total_despesas', 0))
    bal['n_meses'] = int(bal.get('n_meses', 12))
    if 'meses' not in bal:
        bal['meses'] = [f'M{i+1}' for i in range(bal['n_meses'])]
    if 'saldo_inicial' not in bal:
        bal['saldo_inicial'] = None
    if 'saldo_final' not in bal:
        bal['saldo_final'] = None

    # des: garante itens com data
    if 'itens' not in des:
        des['itens'] = []
    for item in des['itens']:
        item['valor_lcto'] = _num(item.get('valor_lcto', 0))
        item['valor_pago'] = _num(item.get('valor_pago', 0)) or item['valor_lcto']
        item['grupo'] = item.get('grupo', '') or ''
        item['classe'] = item.get('classe', '') or ''
        item['fornecedor'] = item.get('fornecedor', '') or ''
        item['descricao'] = item.get('descricao', '') or item.get('fornecedor', '')
        # data pode vir como string ISO ou None
        data = item.get('data')
        if isinstance(data, str):
            try:
                item['data'] = datetime.datetime.strptime(data[:10], '%Y-%m-%d')
            except Exception:
                item['data'] = None
        elif data is None:
            item['data'] = None

    # periodo
    datas = [i['data'] for i in des['itens'] if i.get('data')]
    des['periodo'] = (
        (min(datas), max(datas)) if datas else (None, None)
    )

    # sin
    sin['grand_total'] = _num(sin.get('grand_total', 0)) or None

    # inad
    if inad and 'itens' in inad:
        data_base = inad.get('data_base')
        if isinstance(data_base, str):
            try:
                data_base = datetime.datetime.strptime(data_base[:10], '%Y-%m-%d').date()
            except Exception:
                data_base = None
        inad['data_base'] = data_base
        for item in inad['itens']:
            item['valor'] = _num(item.get('valor', 0))
            item['meses_atraso'] = int(item.get('meses_atraso', 0))
            item['unidade'] = item.get('unidade', '') or ''
            item['classe'] = item.get('classe', '') or ''
            item['mes_ref'] = item.get('mes_ref', '') or ''
            venc = item.get('vencimento')
            if isinstance(venc, str):
                try:
                    item['vencimento'] = datetime.datetime.strptime(venc[:10], '%Y-%m-%d')
                except Exception:
                    item['vencimento'] = None
        inad['total'] = _num(inad.get('total', 0))
        if inad['total'] == 0 and inad['itens']:
            inad['total'] = sum(i['valor'] for i in inad['itens'])
    else:
        inad = None

    return {'bal': bal, 'des': des, 'sin': sin, 'inad': inad}
