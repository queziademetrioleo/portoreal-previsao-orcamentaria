"""Conexao MySQL para sessoes da Previsao Orcamentaria."""
import os
import logging
from datetime import datetime, timedelta

import mysql.connector
from mysql.connector import pooling

logger = logging.getLogger(__name__)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="previsao_pool",
            pool_size=5,
            host=os.environ.get('MYSQL_HOST', 'localhost'),
            port=int(os.environ.get('MYSQL_PORT', '3306')),
            user=os.environ.get('MYSQL_USER', 'root'),
            password=os.environ.get('MYSQL_PASSWORD', ''),
            database=os.environ.get('MYSQL_DATABASE', 'previsao'),
            charset='utf8mb4',
        )
        logger.info('MySQL connection pool created (size=5)')
    return _pool


def get_conn():
    return _get_pool().get_connection()


# -------------------------------------------------------------------
# Schema bootstrap
# -------------------------------------------------------------------
_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS sessoes (
    id VARCHAR(12) PRIMARY KEY,
    nome_condominio VARCHAR(200) NOT NULL,
    ano_previsao INT NOT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('em_revisao','gerado') DEFAULT 'em_revisao',
    estado_json LONGTEXT,
    cache_analise LONGTEXT,
    arquivo_balanual LONGBLOB,
    arquivo_desbai LONGBLOB,
    arquivo_dessin LONGBLOB,
    arquivo_inad LONGBLOB,
    arquivo_previsao LONGBLOB,
    arquivo_xlsx LONGBLOB
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def _init_schema():
    """Create the sessoes table if it does not exist."""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(_BOOTSTRAP_SQL)
        try:
            cursor.execute("ALTER TABLE sessoes ADD COLUMN arquivo_previsao LONGBLOB AFTER arquivo_inad")
        except mysql.connector.Error as exc:
            if exc.errno != 1060:  # duplicate column
                raise
        conn.commit()
        cursor.close()
        conn.close()
        logger.info('Schema bootstrap: sessoes table ready')
    except mysql.connector.Error as exc:
        logger.warning('Schema init failed: %s', exc)


# ---------- operacoes CRUD ----------

def criar_sessao(sid, nome_condominio, ano_previsao):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO sessoes (id, nome_condominio, ano_previsao) VALUES (%s, %s, %s)",
            (sid, nome_condominio, ano_previsao)
        )
        conn.commit()
    finally:
        conn.close()


def carregar_sessao(sid):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM sessoes WHERE id = %s", (sid,))
        return cur.fetchone()
    finally:
        conn.close()


def listar_sessoes():
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, nome_condominio, ano_previsao, criado_em, status FROM sessoes ORDER BY criado_em DESC LIMIT 50")
        return cur.fetchall()
    finally:
        conn.close()


def salvar_estado(sid, estado_json_str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE sessoes SET estado_json = %s WHERE id = %s", (estado_json_str, sid))
        conn.commit()
    finally:
        conn.close()


def salvar_cache_analise(sid, cache_json_str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE sessoes SET cache_analise = %s WHERE id = %s", (cache_json_str, sid))
        conn.commit()
    finally:
        conn.close()


def salvar_arquivo(sid, campo, conteudo_bytes):
    conn = get_conn()
    try:
        cur = conn.cursor()
        colunas_validas = {
            'balanual': 'arquivo_balanual',
            'desbai': 'arquivo_desbai',
            'dessin': 'arquivo_dessin',
            'inad': 'arquivo_inad',
            'previsao': 'arquivo_previsao',
            'xlsx': 'arquivo_xlsx',
        }
        col = colunas_validas.get(campo)
        if not col:
            raise ValueError(f'Campo invalido: {campo}')
        cur.execute(f"UPDATE sessoes SET {col} = %s WHERE id = %s", (conteudo_bytes, sid))
        conn.commit()
    finally:
        conn.close()


def obter_arquivo(sid, campo):
    conn = get_conn()
    try:
        cur = conn.cursor()
        colunas_validas = {
            'balanual': 'arquivo_balanual',
            'desbai': 'arquivo_desbai',
            'dessin': 'arquivo_dessin',
            'inad': 'arquivo_inad',
            'previsao': 'arquivo_previsao',
            'xlsx': 'arquivo_xlsx',
        }
        col = colunas_validas.get(campo)
        if not col:
            raise ValueError(f'Campo invalido: {campo}')
        cur.execute(f"SELECT {col} FROM sessoes WHERE id = %s", (sid,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def atualizar_status(sid, status):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE sessoes SET status = %s WHERE id = %s", (status, sid))
        conn.commit()
    finally:
        conn.close()


def limpar_sessoes_antigas(dias=7):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessoes WHERE criado_em < NOW() - INTERVAL %s DAY", (dias,))
        n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def deletar_sessao(sid):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessoes WHERE id = %s", (sid,))
        conn.commit()
    finally:
        conn.close()


def verificar_conexao():
    try:
        conn = get_conn()
        conn.ping()
        conn.close()
        return True
    except Exception:
        return False


# ---- Bootstrap on import ----
try:
    _init_schema()
except Exception:
    logger.warning('Could not init schema at import time (db may not be up yet)')
