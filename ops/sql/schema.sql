CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS app (
  app_id        UUID PRIMARY KEY,
  name          TEXT NOT NULL,
  version       TEXT NOT NULL,
  site_id       TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job (
  job_id        UUID NOT NULL,
  app_id        UUID NOT NULL REFERENCES app(app_id),
  site_id       TEXT NOT NULL,
  job_key       TEXT NOT NULL,
  status        TEXT NOT NULL,
  started_at    TIMESTAMPTZ,
  ended_at      TIMESTAMPTZ,
  duration_s    DOUBLE PRECISION,
  cpu_user_s    DOUBLE PRECISION DEFAULT 0,
  cpu_system_s  DOUBLE PRECISION DEFAULT 0,
  mem_max_mb    DOUBLE PRECISION DEFAULT 0,
  metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
  inserted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (job_id, inserted_at)
);

CREATE TABLE IF NOT EXISTS subjob (
  subjob_id     UUID NOT NULL,
  job_id        UUID NOT NULL,
  app_id        UUID NOT NULL,
  site_id       TEXT NOT NULL,
  sub_key       TEXT NOT NULL,
  status        TEXT NOT NULL,
  started_at    TIMESTAMPTZ,
  ended_at      TIMESTAMPTZ,
  duration_s    DOUBLE PRECISION,
  cpu_user_s    DOUBLE PRECISION DEFAULT 0,
  cpu_system_s  DOUBLE PRECISION DEFAULT 0,
  mem_max_mb    DOUBLE PRECISION DEFAULT 0,
  metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
  inserted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (subjob_id, inserted_at)
);

CREATE TABLE IF NOT EXISTS event (
  at            TIMESTAMPTZ NOT NULL,
  entity_type   TEXT NOT NULL CHECK (entity_type IN ('job','subjob')),
  entity_id     UUID NOT NULL,
  app_id        UUID NOT NULL,
  site_id       TEXT NOT NULL,
  kind          TEXT NOT NULL,
  payload       JSONB NOT NULL,
  idempotency_key TEXT NOT NULL,
  PRIMARY KEY (entity_id, at)
);

DO $$ BEGIN
  ALTER TABLE event ADD CONSTRAINT uq_event_idem UNIQUE (idempotency_key);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

SELECT create_hypertable('job', 'inserted_at', if_not_exists => TRUE);
SELECT create_hypertable('subjob', 'inserted_at', if_not_exists => TRUE);
SELECT create_hypertable('event', 'at', if_not_exists => TRUE);

SELECT add_retention_policy('job', INTERVAL '72 hours', if_not_exists => TRUE);
SELECT add_retention_policy('subjob', INTERVAL '72 hours', if_not_exists => TRUE);
SELECT add_retention_policy('event', INTERVAL '72 hours', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_job_site_time ON job(site_id, inserted_at DESC);
CREATE INDEX IF NOT EXISTS idx_sub_site_time ON subjob(site_id, inserted_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_site_time ON event(site_id, at DESC);
CREATE INDEX IF NOT EXISTS idx_job_status ON job(status);
CREATE INDEX IF NOT EXISTS idx_subjob_status ON subjob(status);

CREATE OR REPLACE FUNCTION notify_event() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('evt', row_to_json(NEW)::text);
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DO $$ BEGIN
  CREATE TRIGGER trg_notify_event AFTER INSERT ON event FOR EACH ROW EXECUTE FUNCTION notify_event();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
