"""
conftest.py — WEbdEX Monitor Engine Test Foundation (Story 16.1)

Estratégia:
- Mock de imports pesados (telebot, web3, psycopg2, matplotlib, openai) ANTES de qualquer import
- SQLite :memory: via env var DB_PATH — o webdex_db usa isso automaticamente
- Fixtures reutilizáveis para todos os outros testes (16.2, 16.3, 16.4)
"""
from __future__ import annotations

import os
import sys
import sqlite3
import threading
import unittest.mock as mock

import pytest


# ==============================================================================
# 1. ENV VARS — devem ser setados ANTES de qualquer import do projeto
# ==============================================================================
os.environ.setdefault('DB_PATH', ':memory:')
os.environ.setdefault('TELEGRAM_TOKEN', 'fake:token12345678')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'fake:token12345678')
os.environ.setdefault('OPENAI_API_KEY', 'sk-fakekey-test')
os.environ.setdefault('DATABASE_URL', 'postgresql://fake:fake@localhost:5432/fake')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-fake-deepseek')
os.environ.setdefault('GROQ_API_KEY', 'gsk-fake-groq')
os.environ.setdefault('DISCORD_WEBHOOK_URL', 'https://discord.com/api/webhooks/fake/fake')
os.environ.setdefault('ADMIN_USER_IDS', '123456789')
os.environ.setdefault('OPENAI_DEFAULT_ON', '1')


# ==============================================================================
# 2. MOCK DE IMPORTS PESADOS — injeta em sys.modules antes de qualquer import
# ==============================================================================

def _mock_telebot():
    m = mock.MagicMock()
    m.TeleBot = mock.MagicMock()
    m.types = mock.MagicMock()
    m.apihelper = mock.MagicMock()
    sys.modules.setdefault('telebot', m)
    sys.modules.setdefault('telebot.types', m.types)
    sys.modules.setdefault('telebot.apihelper', m.apihelper)


def _mock_web3():
    m = mock.MagicMock()
    m.Web3 = mock.MagicMock()
    m.Web3.to_checksum_address = lambda x: x
    sys.modules.setdefault('web3', m)
    sys.modules.setdefault('web3.middleware', mock.MagicMock())


def _mock_psycopg2():
    m = mock.MagicMock()
    sys.modules.setdefault('psycopg2', m)
    sys.modules.setdefault('psycopg2.pool', mock.MagicMock())
    sys.modules.setdefault('psycopg2.extras', mock.MagicMock())


def _mock_matplotlib():
    m = mock.MagicMock()
    # Submodules DEVEM estar em sys.modules para que `import matplotlib.X` funcione
    sys.modules['matplotlib'] = m
    sys.modules['matplotlib.pyplot'] = mock.MagicMock()
    sys.modules['matplotlib.dates'] = mock.MagicMock()
    sys.modules['matplotlib.figure'] = mock.MagicMock()
    sys.modules['matplotlib.backends'] = mock.MagicMock()
    sys.modules['matplotlib.backends.backend_agg'] = mock.MagicMock()
    sys.modules['matplotlib.ticker'] = mock.MagicMock()
    sys.modules['matplotlib.patches'] = mock.MagicMock()
    sys.modules['matplotlib.lines'] = mock.MagicMock()


def _mock_openai():
    m = mock.MagicMock()
    sys.modules.setdefault('openai', m)


def _mock_webdex_chain():
    """Mock webdex_chain — depende de web3 real (não disponível em tests)."""
    m = mock.MagicMock()
    m.web3 = mock.MagicMock()
    m.rpc_pool = []
    m.CONTRACTS_A = mock.MagicMock()
    m.CONTRACTS_B = mock.MagicMock()
    m.TOPIC_OPENPOSITION = '0x' + '0' * 64
    m.TOPIC_TRANSFER = '0x' + '0' * 64
    m.erc20_contract = mock.MagicMock()
    m.get_active_wallet_map = mock.MagicMock(return_value={})
    m.notify_cids_for_wallet = mock.MagicMock(return_value=[])
    m.obter_preco_pol = mock.MagicMock(return_value=0.5)
    m._is_429_error = mock.MagicMock(return_value=False)
    sys.modules.setdefault('webdex_chain', m)


def _mock_webdex_bot_core():
    """Mock webdex_bot_core — depende do bot Telegram."""
    m = mock.MagicMock()
    m.send_html = mock.MagicMock()
    m.esc = lambda x: str(x)
    m.code = lambda x: f'<code>{x}</code>'
    m.get_token_meta = mock.MagicMock(return_value={'sym': 'USDT', 'dec': 6, 'icon': '💵'})
    m.formatar_moeda = mock.MagicMock(return_value='$0.00')
    m._is_admin = mock.MagicMock(return_value=False)
    sys.modules.setdefault('webdex_bot_core', m)


_mock_telebot()
_mock_web3()
_mock_psycopg2()
_mock_matplotlib()
_mock_openai()
_mock_webdex_chain()
_mock_webdex_bot_core()


# ==============================================================================
# 3. SCHEMA SQLite — tabelas do monitor engine
# ==============================================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    wallet TEXT DEFAULT '',
    rpc TEXT DEFAULT '',
    env TEXT DEFAULT 'AG_C_bd',
    active INTEGER DEFAULT 0,
    periodo TEXT DEFAULT '24h',
    pending TEXT DEFAULT '',
    sub_filter TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT,
    last_seen_ts REAL,
    username TEXT
);

CREATE TABLE IF NOT EXISTS operacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT,
    log_index INTEGER,
    wallet TEXT,
    amount REAL,
    tipo TEXT,
    timestamp TEXT,
    contract_address TEXT,
    ambiente TEXT DEFAULT 'UNKNOWN',
    bloco INTEGER,
    block_ts INTEGER
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    role TEXT,
    content TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet TEXT NOT NULL,
    chat_id INTEGER,
    tx_hash TEXT UNIQUE,
    log_index INTEGER,
    bloco INTEGER,
    amount_wei TEXT,
    tier TEXT DEFAULT 'pro',
    expires_at TEXT,
    activated_at TEXT DEFAULT (datetime('now')),
    ambiente TEXT DEFAULT 'UNKNOWN'
);

CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    milestone_key TEXT UNIQUE,
    notified_at TEXT DEFAULT (datetime('now')),
    value TEXT
);

CREATE TABLE IF NOT EXISTS op_owner (
    hash TEXT,
    log_index INTEGER,
    wallet TEXT,
    PRIMARY KEY (hash, log_index)
);

CREATE TABLE IF NOT EXISTS block_ts (
    bloco INTEGER PRIMARY KEY,
    ts INTEGER,
    ambiente TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS user_funnel (
    chat_id TEXT PRIMARY KEY,
    stage TEXT DEFAULT 'new',
    total_trades INTEGER DEFAULT 0,
    first_trade TEXT,
    updated_at TEXT
);
"""


# ==============================================================================
# 4. FIXTURES
# ==============================================================================

@pytest.fixture(scope='session')
def base_schema_conn():
    """
    Conexão SQLite :memory: com schema completo.
    Escopo session — criada uma vez, compartilhada por todos os testes.
    """
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def db_conn(base_schema_conn):
    """
    Conexão limpa por teste — apaga todos os dados antes de cada teste.
    Usa a mesma conexão session para evitar overhead de criação.
    """
    tables = ['config', 'users', 'operacoes', 'ai_conversations', 'subscriptions', 'milestones']
    for t in tables:
        base_schema_conn.execute(f'DELETE FROM {t}')
    base_schema_conn.commit()
    yield base_schema_conn


@pytest.fixture
def mock_pg_conn():
    """
    Mock de conexão psycopg2 para testes de AI memory (Story 16.2).
    Retorna (conn_mock, cursor_mock) prontos para uso.
    """
    cur_mock = mock.MagicMock()
    cur_mock.fetchall.return_value = []
    cur_mock.fetchone.return_value = None

    conn_mock = mock.MagicMock()
    conn_mock.cursor.return_value.__enter__ = mock.MagicMock(return_value=cur_mock)
    conn_mock.cursor.return_value.__exit__ = mock.MagicMock(return_value=False)

    return conn_mock, cur_mock


@pytest.fixture
def mock_telegram_bot():
    """Mock do bot Telegram para testes de handlers."""
    bot = mock.MagicMock()
    bot.send_message = mock.MagicMock(return_value=mock.MagicMock(message_id=999))
    bot.reply_to = mock.MagicMock(return_value=mock.MagicMock(message_id=998))
    bot.answer_callback_query = mock.MagicMock()
    return bot


@pytest.fixture
def fake_message():
    """Mensagem Telegram fake para testes de handlers."""
    msg = mock.MagicMock()
    msg.chat.id = 111222333
    msg.from_user.id = 111222333
    msg.from_user.username = 'testuser'
    msg.text = '/start'
    msg.message_id = 1
    return msg


@pytest.fixture
def fake_admin_message():
    """Mensagem fake de admin (usa ADMIN_USER_IDS)."""
    msg = mock.MagicMock()
    msg.chat.id = 123456789  # mesmo que ADMIN_USER_IDS
    msg.from_user.id = 123456789
    msg.from_user.username = 'admin'
    msg.text = '/admin'
    msg.message_id = 2
    return msg
