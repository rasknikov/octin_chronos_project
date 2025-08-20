-- Lab Octin: schema minimo para logs e relatorios
-- Padrao: snake_case, ts_utc em timestamptz, payload_json em jsonb
-- Nota de trincheira: usei JSONB porque o Gemini as vezes alucina na estrutura do log e eu nao quero quebrar o banco.

CREATE TABLE IF NOT EXISTS experiment_logs (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  ts_utc TIMESTAMPTZ NOT NULL,
  expert_id TEXT NOT NULL,
  task TEXT NOT NULL,
  confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
  payload_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_experiment_logs_run_id ON experiment_logs (run_id);
CREATE INDEX IF NOT EXISTS idx_experiment_logs_ts_utc ON experiment_logs (ts_utc);
CREATE INDEX IF NOT EXISTS idx_experiment_logs_expert_id ON experiment_logs (expert_id);

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  ts_utc TIMESTAMPTZ NOT NULL,
  allow BOOLEAN NOT NULL,
  severity TEXT NOT NULL,
  issues_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_run_id ON audit_logs (run_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_ts_utc ON audit_logs (ts_utc);

CREATE TABLE IF NOT EXISTS execution_logs (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  ts_utc TIMESTAMPTZ NOT NULL,
  action TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_logs_run_id ON execution_logs (run_id);
CREATE INDEX IF NOT EXISTS idx_execution_logs_ts_utc ON execution_logs (ts_utc);

-- Relatorio rapido (ultimas 24h por expert)
-- Use em queries do n8n se quiser evitar SQL longo.
CREATE OR REPLACE VIEW v_expert_summary_24h AS
SELECT
  expert_id,
  COUNT(*) AS total,
  AVG(confidence) AS avg_confidence
FROM experiment_logs
WHERE ts_utc >= NOW() - INTERVAL '24 hours'
GROUP BY expert_id;
