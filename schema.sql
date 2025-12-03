
-- Criar tabela de usuários
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL
);

-- Criar tabela de recargas
CREATE TABLE IF NOT EXISTS recharges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    kwh REAL NOT NULL,
    custo REAL NOT NULL,
    isento BOOLEAN NOT NULL DEFAULT 0, 
    odometro REAL NOT NULL,
    local TEXT,
    observacoes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Criar índice para otimizar consultas por usuário e data
CREATE INDEX IF NOT EXISTS idx_recharges_user_date ON recharges(user_id, data);

-- Criar tabela de configurações
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    preco_gasolina REAL NOT NULL,
    consumo_km_l REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Criar índice para configurações por usuário
CREATE UNIQUE INDEX IF NOT EXISTS idx_settings_user ON settings(user_id);
