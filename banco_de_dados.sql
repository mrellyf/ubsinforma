
-- BANCO DE DADOS: UBS INFORMA

-- 1. TABELA DAS UNIDADES DE SAUDE
CREATE TABLE ubs (
    id_ubs SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    endereco VARCHAR(200) NOT NULL
);

-- 2. TABELA DOS PROFISSIONAIS
CREATE TABLE profissional (
    id_profissional SERIAL PRIMARY KEY,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    id_ubs INTEGER NOT NULL UNIQUE,
    FOREIGN KEY (id_ubs) REFERENCES ubs(id_ubs)
);

-- 3. TABELA DO MURAL DE AVISOS
CREATE TABLE mural (
    id_mural SERIAL PRIMARY KEY,
    titulo VARCHAR(150) NOT NULL,
    descricao TEXT NOT NULL,
    data DATE NOT NULL,
    horario TIME NOT NULL,
    id_ubs INTEGER NOT NULL,
    id_profissional INTEGER NOT NULL,
    categoria VARCHAR(80),
    prioridade VARCHAR(30),
    FOREIGN KEY (id_ubs) REFERENCES ubs(id_ubs),
    FOREIGN KEY (id_profissional) REFERENCES profissional(id_profissional)
);
