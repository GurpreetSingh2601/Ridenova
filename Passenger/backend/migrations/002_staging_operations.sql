CREATE TABLE rate_limits (
    key TEXT PRIMARY KEY,
    window_id BIGINT NOT NULL,
    attempts BIGINT NOT NULL,
    expires_ms BIGINT NOT NULL
);
CREATE TABLE operational_heartbeats (
    name TEXT PRIMARY KEY,
    at_ms BIGINT NOT NULL,
    revision TEXT NOT NULL
);
CREATE TABLE import_receipts (
    source_sha256 TEXT PRIMARY KEY,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    report TEXT NOT NULL
);
CREATE INDEX rides_status_time ON rides ((payload::jsonb->>'status'), ((payload::jsonb->>'updatedAtEpochMs')::bigint));
