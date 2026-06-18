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
import shutil
import tempfile
import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import previsao as core
from gerador_previsao import gerar_previsao_adaptativa

app = FastAPI(title='Previsao Orcamentaria', version='2.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],          # dev: vite roda em outra porta; prod: mesma origem
    allow_methods=['*'],
    allow_headers=['*'],
)

# Sessoes persistidas em disco (JSON) — sobrevivem a restart do container
SESSOES_DIR = os.environ.get('PREVISAO_SESSOES_DIR',
                             os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessoes'))
os.makedirs(SESSOES_DIR, exist_ok=True)

ARQUIVOS_ESPERADOS = {
    'balanual': 'balanual.xls',
    'desbai': 'desbai06.xls',
    'dessin': 'dessin02.xls',
    'inad': 'inad01.xls',
}


def _sessao_path(sid):
    return os.path.join(SESSOES_DIR, sid)


def _salvar_estado(sid, estado):
    with open(os.path.join(_sessao_path(sid), 'estado.json'), 'w', encoding='utf-8') as f:
        json.dump(estado, f, ensure_ascii=False, default=str)


def _carregar_estado(sid):
    p = os.path.join(_sessao_path(sid), 'estado.json')
    if not os.path.exists(p):
        raise HTTPException(404, 'Sessao nao encontrada')
    with open(p, encoding='utf-8') as f:
        return json.load(f)


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
    pasta = _sessao_path(sid)
    os.makedirs(pasta, exist_ok=True)

    uploads = {'balanual': balanual, 'desbai': desbai, 'dessin': dessin, 'inad': inad}
    for chave, up in uploads.items():
        if up is None:
            continue
        destino = os.path.join(pasta, ARQUIVOS_ESPERADOS[chave])
        with open(destino, 'wb') as f:
            shutil.copyfileobj(up.file, f)

    obrigatorios = ['balanual.xls', 'desbai06.xls']
    faltando = [a for a in obrigatorios if not os.path.exists(os.path.join(pasta, a))]
    if faltando:
        shutil.rmtree(pasta, ignore_errors=True)
        raise HTTPException(400, f'Arquivos obrigatorios ausentes: {faltando}')

    # O IA parser já lida com arquivos ausentes (retorna null para a seção)
    try:
        R = core.analisar(pasta)
    except Exception as e:
        shutil.rmtree(pasta, ignore_errors=True)
        raise HTTPException(422, f'Falha ao analisar os relatorios: {e}')

    estado = _montar_estado(sid, nome_condominio, ano_previsao, R)
    _salvar_estado(sid, estado)
    return JSONResponse(estado)


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
            item['origem'] = 'Regra'
            item['decisao'] = 'pendente'        # humano decide
            revisar.append(item)

    inad_itens = []
    if R['inad']:
        for i, it in enumerate(R['inad']['itens']):
            # critica ja vem calculada pelo analisar() — >= 3 meses CONSECUTIVOS
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
# 2) CONSULTA
# ---------------------------------------------------------------------------
@app.get('/api/sessao/{sid}')
def obter_sessao(sid: str):
    return _carregar_estado(sid)


@app.get('/api/sessoes')
def listar_sessoes():
    out = []
    for d in sorted(os.listdir(SESSOES_DIR)):
        p = os.path.join(SESSOES_DIR, d, 'estado.json')
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                e = json.load(f)
            out.append({'sessao_id': e['sessao_id'], 'nome': e['nome_condominio'],
                        'ano': e['ano_previsao'], 'criado_em': e['criado_em'],
                        'status': e['status']})
    return out


# ---------------------------------------------------------------------------
# 3) DECISOES + GERACAO DO DOCUMENTO FINAL
# ---------------------------------------------------------------------------
class Decisoes(BaseModel):
    # {"17": "aprovada"|"reprovada"} p/ extraordinarias; revisar idem;
    # inadimplencia: {"0": "abater"|"ignorar"}
    extraordinarias: dict = {}
    revisar: dict = {}
    inadimplencia: dict = {}


@app.post('/api/sessao/{sid}/gerar')
def gerar(sid: str, dec: Decisoes):
    estado = _carregar_estado(sid)
    pasta = _sessao_path(sid)

    # aplicar decisoes humanas no estado
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

    # reconstruir o calculo com as decisoes:
    #   Extraordinaria aprovada  -> continua removida
    #   Extraordinaria reprovada -> volta para a base (recorrente)
    #   Revisar aprovada (= e extraordinaria) -> removida
    #   Revisar reprovada/pendente -> fica na base
    ids_remover = {i['id'] for i in estado['extraordinarias'] if i['decisao'] == 'aprovada'}
    ids_remover |= {i['id'] for i in estado['revisar'] if i['decisao'] == 'aprovada'}

    R = core.analisar(pasta)  # IA-powered parsing (fallback automático para parsers rígidos)

    # sobrescrever a classificacao com a decisao humana (fonte da verdade)
    for idx, it in enumerate(R['des']['itens']):
        it['cat'] = 'Extraordinaria' if idx in ids_remover else (
            'Recorrente' if it['cat'] in ('Extraordinaria', 'Revisar') else it['cat'])

    R2 = core.recalcular(R)

    # inadimplencia: impacto na receita = soma das taxas das unidades marcadas p/ abater
    unidades = {}
    for item in estado['inadimplencia']:
        if item['decisao'] == 'abater':
            unidades.setdefault(item['unidade'], []).append(item['valor'])
    impacto_receita = sum(sum(v) / len(v) for v in unidades.values())

    out_xlsx = os.path.join(pasta, f"Previsão {estado['ano_previsao']}.xlsx")
    modelo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'modelo_previsao.xlsx')
    gerar_previsao_adaptativa(
        destino=out_xlsx,
        R=R2,
        nome_condominio=estado['nome_condominio'],
        ano=estado['ano_previsao'],
        impacto_receita_mensal=impacto_receita,
        inad_detalhe=estado['inadimplencia'],
        inad_meta=estado['inad_meta'],
        referencia=modelo if os.path.exists(modelo) else None,
    )

    estado['status'] = 'gerado'
    estado['resumo']['subtotal'] = round(R2['subtotal'], 2)
    estado['resumo']['total_previsto'] = round(R2['total_previsto'], 2)
    estado['resumo']['impacto_receita_mensal'] = round(impacto_receita, 2)
    _salvar_estado(sid, estado)

    return {'ok': True, 'sessao_id': sid,
            'subtotal': round(R2['subtotal'], 2),
            'total_previsto': round(R2['total_previsto'], 2),
            'impacto_receita_mensal': round(impacto_receita, 2),
            'download': f'/api/sessao/{sid}/download'}



@app.get('/api/sessao/{sid}/download')
def download(sid: str):
    estado = _carregar_estado(sid)
    p = os.path.join(_sessao_path(sid), f"Previsão {estado['ano_previsao']}.xlsx")
    if not os.path.exists(p):
        raise HTTPException(404, 'Documento ainda nao gerado')
    return FileResponse(
        p, filename=f"Previsão {estado['ano_previsao']} - {estado['nome_condominio']}.xlsx",
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ---------------------------------------------------------------------------
# Frontend estatico (build do React) — prod
# ---------------------------------------------------------------------------
_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
if os.path.isdir(_STATIC):
    app.mount('/', StaticFiles(directory=_STATIC, html=True), name='frontend')
