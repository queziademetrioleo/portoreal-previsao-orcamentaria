"""Banco em memória para os testes de upload: guarda uma linha de ``sessoes``."""
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import db


class BancoFalso:
    def __init__(self):
        self.row = {}

    def registrar_recebimento(self, sid, nome, ano, tem_fundo_reserva, arquivos, config_json):
        self.row = {'id': sid, 'nome_condominio': nome, 'ano_previsao': ano,
                    'tem_fundo_reserva': tem_fundo_reserva, 'config_importacao': config_json,
                    'etapa': 'recebido', 'erro': None}
        self.row.update({db.COLUNAS_ARQUIVOS[campo]: conteudo for campo, conteudo in arquivos.items()})

    def salvar_arquivo(self, sid, campo, conteudo):
        self.row[db.COLUNAS_ARQUIVOS[campo]] = conteudo

    def salvar_config_importacao(self, sid, config_json):
        self.row['config_importacao'] = config_json

    def marcar_etapa(self, sid, etapa, erro=None):
        self.row.update(etapa=etapa, erro=erro)

    @property
    def etapa(self):
        return self.row.get('etapa')

    @contextmanager
    def ativo(self):
        with ExitStack() as stack:
            for nome in ('registrar_recebimento', 'salvar_arquivo', 'salvar_config_importacao', 'marcar_etapa'):
                stack.enter_context(patch.object(db, nome, side_effect=getattr(self, nome)))
            yield self
