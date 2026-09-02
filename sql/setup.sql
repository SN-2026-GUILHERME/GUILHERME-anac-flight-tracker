-- ============================================================
-- ANAC Flight Tracker — Schema do Supabase
-- Tabela "voos": armazena os voos coletados pelo scripts/fetch_flights.py
-- e exibidos pelo index.html.
-- ============================================================

CREATE TABLE IF NOT EXISTS voos (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    numero_voo        TEXT NOT NULL,
    companhia         TEXT,
    origem            TEXT,
    destino           TEXT,
    icao_aeroporto    TEXT NOT NULL,
    horario_previsto  TIMESTAMPTZ,
    horario_real      TIMESTAMPTZ,
    situacao          TEXT,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT voos_unicos UNIQUE (numero_voo, icao_aeroporto, horario_previsto)
);

-- Índice para acelerar a consulta usada pelo index.html (order by horario_previsto)
CREATE INDEX IF NOT EXISTS idx_voos_horario_previsto ON voos (horario_previsto);

-- Índice para o filtro por aeroporto
CREATE INDEX IF NOT EXISTS idx_voos_icao_aeroporto ON voos (icao_aeroporto);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE voos ENABLE ROW LEVEL SECURITY;

-- Leitura pública (o painel usa a chave "anon" direto no navegador)
CREATE POLICY "Permitir leitura publica de voos" ON voos
    FOR SELECT USING (true);

-- Apenas a service_role (usada pelo GitHub Actions) pode inserir/atualizar
CREATE POLICY "Permitir insert somente para service_role" ON voos
    FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Permitir update somente para service_role" ON voos
    FOR UPDATE TO service_role USING (true) WITH CHECK (true);

-- ============================================================
-- GRANTs
-- ============================================================
GRANT SELECT ON voos TO anon;
GRANT SELECT ON voos TO authenticated;
GRANT ALL ON voos TO service_role;
