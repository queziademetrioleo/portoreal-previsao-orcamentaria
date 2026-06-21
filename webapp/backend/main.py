#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREVISAO ORCAMENTARIA — Backend Web (FastAPI)

Fluxo human-in-the-loop:
  1. POST /api/sessao            — upload dos 4 relatorios -> analise (regras + IA)
  2. GET  /api/sessao/{id}       — estado da sessao (itens p/ revisao)
  3. POST /api/sessao/{id}/gerar — decisoes humanas -> xlsx final (estrutura identica ao manual)

Dev:  uvicorn main:app --reload --port 8000
Prod: ver Dockerfile na raiz do projeto.
"""
import os
import sys
import json
import uuid
import asyncio
import threading
import tempfile
import datetime
import logging

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import previsao as core
from gerador_previsao import gerar_previsao_adaptativa

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title='Previsao Orcamentaria', version='2.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],          # dev: vite roda em outra porta; prod: mesma origem
    allow_methods=['*'],
    allow_headers=['*'],
)

ARQUIVOS_ESPERADOS = {
    'balanual': 'balanual.xls',
    'desbai': 'desbai06.xls',
    'dessin': 'dessin02.xls',
    'inad': 'inad01.xls',
}


# ---------------------------------------------------------------------------
# Helpers de sessao  (persistencia via MySQL)
# ---------------------------------------------------------------------------

def _carregar_estado(sid):
    """Carrega o estado JSON da sessao do MySQL."""
    row = db.carregar_sessao(sid)
    if not row or not row.get('estado_json'):
        raise HTTPException(404, 'Sessao nao encontrada')
    return json.loads(row['estado_json'])


def _json_dumps(obj):
    """Serializa objeto para JSON, convertendo chaves tupla em string."""
    def _converter(o):
        if isinstance(o, dict):
            return {str(k) if isinstance(k, tuple) else k: _converter(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_converter(v) for v in o]
        if isinstance(o, tuple):
            return str(o)
        return o
    return json.dumps(_converter(obj), ensure_ascii=False, default=str)


def _json_loads(s):
    """Carrega JSON, convertendo chaves que parecem tuplas de volta para tupla."""
    import ast
    def _converter(o):
        if isinstance(o, dict):
            result = {}
            for k, v in o.items():
                if isinstance(k, str) and k.startswith('(') and k.endswith(')'):
                    try:
                        k = ast.literal_eval(k)
                    except (ValueError, SyntaxError):
                        pass
                result[k] = _converter(v)
            return result
        if isinstance(o, list):
            return [_converter(v) for v in o]
        return o
    return _converter(json.loads(s))


def _obter_R(sid):
    """Retorna o cache de analise (R) do MySQL; fallback para core.analisar()."""
    row = db.carregar_sessao(sid)
    if row is None:
        raise HTTPException(404, 'Sessao nao encontrada')
    if row.get('cache_analise'):
        try:
            return _json_loads(row['cache_analise'])
        except (json.JSONDecodeError, TypeError):
            pass
    # Fallback: reconstituir arquivos do MySQL e re-analisar
    with tempfile.TemporaryDirectory() as tmpdir:
        for chave, fname in ARQUIVOS_ESPERADOS.items():
            content = db.obter_arquivo(sid, chave)
            if content:
                with open(os.path.join(tmpdir, fname), 'wb') as f:
                    f.write(content)
        R = core.analisar(tmpdir)
        db.salvar_cache_analise(sid, _json_dumps(R))
        return R


def _aplicar_decisoes(estado, dec):
    """Aplica as decisoes humanas no estado (in-place)."""
    for item in estado['extraordinarias']:
        d = dec.extraordinarias.get(str(item['id']))
        if d in ('aprovada', 'reprovada'):
            item['decisao'] = d
    for item in estado['revisar']:
        d = dec.revisar.get(str(item['id']))
        if d in ('aprovada', 'reprovada', 'pendente'):
            item['decisao'] = d
    for item in estado['inadimplencia']:
        d = dec.inadimplencia.get(str(item['id']))
        if d in ('abater', 'ignorar'):
            item['decisao'] = d


def _recalcular_com_decisoes(sid, estado):
    """Recalcula subtotal/total/impacto a partir das decisoes ja no 'estado'.
    Retorna (R2, impacto_receita). Nao gera xlsx."""
    ids_remover = {i['id'] for i in estado['extraordinarias'] if i['decisao'] == 'aprovada'}
    ids_remover |= {i['id'] for i in estado['revisar'] if i['decisao'] == 'aprovada'}

    R = _obter_R(sid)
    for idx, it in enumerate(R['des']['itens']):
        it['cat'] = 'Extraordinaria' if idx in ids_remover else (
            'Recorrente' if it['cat'] in ('Extraordinaria', 'Revisar') else it['cat'])
    R2 = core.recalcular(R)

    unidades = {}
    for item in estado['inadimplencia']:
        if item['decisao'] == 'abater':
            unidades.setdefault(item['unidade'], []).append(item['valor'])
    impacto = sum(sum(v) / len(v) for v in unidades.values())
    return R2, impacto


def _montar_estado(sid, nome, ano, R):
    """Converte o resultado de core.analisar() no payload de revisao humana."""
    des = R['des']

    extraordinarias, revisar = [], []
    for idx, it in enumerate(des['itens']):
        item = {
            'id': idx,
            'grupo': it['grupo'],
            'classe': it['classe'],
            'data': str(it['data'] or ''),
            'descricao': it['descricao'],
            'valor': round(it['valor_pago'], 2),
            'motivo': it['motivo'],
            'n_meses': it.get('n_meses'),
        }
        if it['cat'] == 'Extraordinaria':
            ia = R.get('sugestoes_ia', {}).get(idx) or R.get('sugestoes_ia', {}).get(str(idx))
            item['origem'] = 'IA' if (it['motivo'] or '').startswith('IA:') else 'Regra'
            item['decisao'] = 'aprovada'        # default: remover da base
            extraordinarias.append(item)
        elif it['cat'] == 'Revisar':
            item['origem'] = 'IA' if (it['motivo'] or '').startswith('IA:') else 'Regra'
            item['decisao'] = 'pendente'        # humano decide
            revisar.append(item)

    inad_itens = []
    if R['inad']:
        for i, it in enumerate(R['inad']['itens']):
            critica = it.get('critica', (it['meses_atraso'] or 0) >= 3)
            inad_itens.append({
                'id': i,
                'unidade': it['unidade'],
                'classe': it['classe'],
                'mes_ref': it['mes_ref'],
                'vencimento': str(it['vencimento'] or ''),
                'valor': round(it['valor'], 2),
                'meses_atraso': it['meses_atraso'],
                'critica': critica,
                'decisao': 'abater' if critica else 'ignorar',
            })

    linhas = [{
        'grupo': l['grupo'], 'classe': l['classe'],
        'base': round(l['base'], 2), 'deducao': round(l['deducao'], 2),
        'final': round(l['final'], 2), 'regra': l['regra'],
        'n_meses': l['n_meses'],
    } for l in R['linhas']]

    bal = R['bal']
    return {
        'sessao_id': sid,
        'nome_condominio': nome,
        'ano_previsao': ano,
        'criado_em': datetime.datetime.now().isoformat(timespec='seconds'),
        'modelo_ia': core._ia_modelo(),
        'ia_ativa': core._ia_disponivel(),
        'resumo': {
            'base_total': round(R['base_total'], 2),
            'desconsideracoes': round(R['desconsideracoes'], 2),
            'prov_laudo': round(R['prov_laudo'], 2),
            'prov_incendio': round(R['prov_incendio'], 2),
            'subtotal': round(R['subtotal'], 2),
            'inflacao': core.INFLACAO,
            'total_previsto': round(R['total_previsto'], 2),
            'receita_anual': round(bal['total_receitas'] or 0, 2),
            'receita_mensal': round((bal['total_receitas'] or 0) / 12, 2),
            'periodo': [str(R['des']['periodo'][0]), str(R['des']['periodo'][1])],
        },
        'extraordinarias': extraordinarias,
        'revisar': revisar,
        'inadimplencia': inad_itens,
        'inad_meta': ({
            'total': round(R['inad']['total'], 2),
            'critica': round(R['inad']['critica'], 2),
            'data_base': str(R['inad']['data_base']),
        } if R['inad'] else None),
        'linhas_contas': linhas,
        'status': 'em_revisao',
    }


# ---------------------------------------------------------------------------
# Modelo de decisoes
# ---------------------------------------------------------------------------
class Decisoes(BaseModel):
    extraordinarias: dict = {}
    revisar: dict = {}
    inadimplencia: dict = {}


# ---------------------------------------------------------------------------
# Startup — limpeza de sessoes antigas
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    removidas = db.limpar_sessoes_antigas(7)
    if removidas:
        logger.info(f'{removidas} sessoes antigas removidas (TTL=7d)')


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    db_ok = db.verificar_conexao()
    return {"status": "ok" if db_ok else "degraded", "db": "connected" if db_ok else "disconnected"}


# ---------------------------------------------------------------------------
# 1) UPLOAD + ANALISE
# ---------------------------------------------------------------------------
@app.post('/api/sessao')
async def criar_sessao(
    nome_condominio: str = Form(...),
    ano_previsao: int = Form(...),
    balanual: UploadFile = File(...),
    desbai: UploadFile = File(...),
    dessin: UploadFile = File(None),
    inad: UploadFile = File(None),
):
    sid = uuid.uuid4().hex[:12]

    # Criar registro PRIMEIRO (INSERT), depois salvar arquivos (UPDATE)
    db.criar_sessao(sid, nome_condominio, ano_previsao)

    uploads = {'balanual': balanual, 'desbai': desbai, 'dessin': dessin, 'inad': inad}
    file_bytes = {}
    for chave, up in uploads.items():
        if up is None:
            continue
        conteudo = await up.read()
        file_bytes[chave] = conteudo
        db.salvar_arquivo(sid, chave, conteudo)

    if 'balanual' not in file_bytes or 'desbai' not in file_bytes:
        db.deletar_sessao(sid)
        raise HTTPException(400, 'Arquivos obrigatorios ausentes')
    logger.info(f'Sessao {sid} criada: {nome_condominio} ({ano_previsao})')

    return {'sessao_id': sid, 'nome_condominio': nome_condominio,
            'ano_previsao': ano_previsao, 'status': 'pendente'}


@app.get('/api/sessao/{sid}/analisar')
async def analisar_sse(sid: str):
    """SSE endpoint: executa analise e transmite progresso em tempo real."""
    from fastapi.responses import StreamingResponse

    row = db.carregar_sessao(sid)
    if not row:
        raise HTTPException(404, 'Sessao nao encontrada')

    eventos = []
    lock = threading.Lock()

    def on_progress(p):
        with lock:
            eventos.append(p)

    async def gerar():
        loop = asyncio.get_event_loop()

        # Reconstitui arquivos do MySQL para diretorio temporario
        with tempfile.TemporaryDirectory() as tmpdir:
            for chave, fname in ARQUIVOS_ESPERADOS.items():
                content = db.obter_arquivo(sid, chave)
                if content:
                    with open(os.path.join(tmpdir, fname), 'wb') as f:
                        f.write(content)

            # Inicia analise em thread
            future = loop.run_in_executor(None, core.analisar, tmpdir, on_progress)

            # Stream progress enquanto analise roda
            last_idx = 0
            while not future.done():
                await asyncio.sleep(0.3)
                with lock:
                    while last_idx < len(eventos):
                        ev = eventos[last_idx]
                        last_idx += 1
                        yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                yield ": keepalive\n\n"

            # Pega ultimos eventos
            with lock:
                while last_idx < len(eventos):
                    ev = eventos[last_idx]
                    last_idx += 1
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

            # Resultado final
            R = future.result()
            db.salvar_cache_analise(sid, _json_dumps(R))

            nome = row['nome_condominio']
            ano = row['ano_previsao']
            estado = _montar_estado(sid, nome, ano, R)
            _salvar_estado_sync(sid, estado)

            yield f"data: {json.dumps({'done': True, 'sessao_id': sid}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gerar(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


def _salvar_estado_sync(sid, estado):
    db.salvar_estado(sid, json.dumps(estado, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# 2) CONSULTA
# ---------------------------------------------------------------------------
@app.get('/api/sessao/{sid}')
def obter_sessao(sid: str):
    return _carregar_estado(sid)


@app.delete("/api/sessao/{sid}")
async def deletar_sessao(sid: str):
    """Remove uma sessao e todos os seus dados."""
    try:
        db.deletar_sessao(sid)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"Erro ao deletar sessao: {e}")


@app.get('/api/sessoes')
def listar_sessoes():
    sessoes = db.listar_sessoes()
    return [{
        'sessao_id': s['id'],
        'nome': s['nome_condominio'],
        'ano': s['ano_previsao'],
        'criado_em': str(s['criado_em']),
        'status': s.get('status', 'em_revisao'),
    } for s in sessoes]


# ---------------------------------------------------------------------------
# 3) DECISOES + GERACAO DO DOCUMENTO FINAL
# ---------------------------------------------------------------------------
@app.post('/api/sessao/{sid}/preview')
def preview(sid: str, dec: Decisoes):
    """Recalcula subtotal/total/impacto com as decisoes atuais SEM gerar o xlsx.
    Permite que a interface atualize os numeros ao vivo a cada clique."""
    estado = _carregar_estado(sid)
    _aplicar_decisoes(estado, dec)
    R2, impacto = _recalcular_com_decisoes(sid, estado)
    return {'ok': True,
            'subtotal': round(R2['subtotal'], 2),
            'total_previsto': round(R2['total_previsto'], 2),
            'impacto_receita_mensal': round(impacto, 2)}


@app.post('/api/sessao/{sid}/gerar')
def gerar(sid: str, dec: Decisoes):
    estado = _carregar_estado(sid)

    _aplicar_decisoes(estado, dec)
    R2, impacto_receita = _recalcular_com_decisoes(sid, estado)

    # Gerar xlsx em arquivo temporario e salvar bytes no MySQL
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        out_path = tmp.name
    try:
        modelo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'templates', 'modelo_previsao.xlsx')
        gerar_previsao_adaptativa(
            destino=out_path,
            R=R2,
            nome_condominio=estado['nome_condominio'],
            ano=estado['ano_previsao'],
            impacto_receita_mensal=impacto_receita,
            inad_detalhe=estado['inadimplencia'],
            inad_meta=estado['inad_meta'],
            referencia=modelo if os.path.exists(modelo) else None,
        )
        with open(out_path, 'rb') as f:
            xlsx_bytes = f.read()
    finally:
        os.unlink(out_path)

    db.salvar_arquivo(sid, 'xlsx', xlsx_bytes)

    estado['status'] = 'gerado'
    estado['resumo']['subtotal'] = round(R2['subtotal'], 2)
    estado['resumo']['total_previsto'] = round(R2['total_previsto'], 2)
    estado['resumo']['impacto_receita_mensal'] = round(impacto_receita, 2)
    db.salvar_estado(sid, json.dumps(estado, ensure_ascii=False, default=str))

    return {'ok': True, 'sessao_id': sid,
            'subtotal': round(R2['subtotal'], 2),
            'total_previsto': round(R2['total_previsto'], 2),
            'impacto_receita_mensal': round(impacto_receita, 2),
            'download': f'/api/sessao/{sid}/download'}


@app.post('/api/sessao/{sid}/salvar-decisoes')
async def salvar_decisoes(sid: str, decisoes: Decisoes):
    """Salva decisoes parciais do usuario sem gerar o documento final.
    Permite que o usuario retome a revisao depois."""
    estado = _carregar_estado(sid)
    _aplicar_decisoes(estado, decisoes)
    db.salvar_estado(sid, json.dumps(estado, ensure_ascii=False, default=str))
    return {'ok': True, 'sessao_id': sid}


@app.get('/api/sessao/{sid}/download')
def download(sid: str):
    estado = _carregar_estado(sid)
    xlsx_bytes = db.obter_arquivo(sid, 'xlsx')
    if not xlsx_bytes:
        raise HTTPException(404, 'Documento ainda nao gerado')
    filename = f"Previsão {estado['ano_previsao']} - {estado['nome_condominio']}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Frontend estatico (build do React) — prod
# ---------------------------------------------------------------------------
_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
if os.path.isdir(_STATIC):
    app.mount('/', StaticFiles(directory=_STATIC, html=True), name='frontend')
