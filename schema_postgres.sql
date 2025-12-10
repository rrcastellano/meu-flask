-- Arquivo: schema_postgres.sql

-- Criar tabela de usuários
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY, -- Alterado de INTEGER PRIMARY KEY AUTOINCREMENT
    nome VARCHAR(100) NOT NULL, -- Alterado de TEXT
    email VARCHAR(255) NOT NULL UNIQUE, -- Alterado de TEXT
    senha_hash VARCHAR(255) NOT NULL -- Alterado de TEXT
);

-- Criar tabela de recargas
CREATE TABLE IF NOT EXISTS recharges (
    id SERIAL PRIMARY KEY, -- Alterado de INTEGER PRIMARY KEY AUTOINCREMENT
    user_id INTEGER NOT NULL,
    data TIMESTAMP NOT NULL, -- Alterado de TEXT para TIMESTAMP (consistente com contact_logs)
    kwh REAL NOT NULL,
    custo REAL NOT NULL,
    isento BOOLEAN NOT NULL DEFAULT FALSE, -- Alterado de DEFAULT 0 para DEFAULT FALSE
    odometro REAL NOT NULL,
    local VARCHAR(255), -- Alterado de TEXT
    observacoes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Criar índice para otimizar consultas por usuário e data
CREATE INDEX IF NOT EXISTS idx_recharges_user_date ON recharges(user_id, data);

-- Criar tabela de configurações
CREATE TABLE IF NOT EXISTS settings (
    id SERIAL PRIMARY KEY, -- Alterado de INTEGER PRIMARY KEY AUTOINCREMENT
    user_id INTEGER NOT NULL,
    preco_gasolina REAL NOT NULL,
    consumo_km_l REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Criar índice para configurações por usuário
CREATE UNIQUE INDEX IF NOT EXISTS idx_settings_user ON settings(user_id);

-- ----------------- NOVA TABELA ADICIONADA E ATUALIZADA -----------------

-- Criar tabela para logs de contato (formulário "Fale Conosco")
CREATE TABLE IF NOT EXISTS contact_logs (
    id SERIAL PRIMARY KEY, -- Alterado de INTEGER PRIMARY KEY AUTOINCREMENT
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    mensagem TEXT NOT NULL,
    data_envio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Adicionado DEFAULT para facilitar
    status VARCHAR(50) NOT NULL
);

-- Criar índice para otimizar consultas por data de envio
CREATE INDEX IF NOT EXISTS idx_contact_logs_date ON contact_logs(data_envio);
