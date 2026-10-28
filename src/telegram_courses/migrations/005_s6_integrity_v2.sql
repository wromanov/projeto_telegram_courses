ALTER TABLE downloads ADD COLUMN contract_version INTEGER;
ALTER TABLE downloads ADD COLUMN evidence_version INTEGER;

CREATE TABLE s6_v2_attempts (
    id TEXT PRIMARY KEY,
    media_item_id INTEGER NOT NULL REFERENCES media_items(id),
    channel_id INTEGER NOT NULL,
    telegram_message_id INTEGER NOT NULL,
    media_ordinal INTEGER NOT NULL,
    telegram_media_id TEXT NOT NULL,
    expected_bytes INTEGER NOT NULL CHECK (expected_bytes >= 0),
    selected_mode TEXT NOT NULL CHECK (selected_mode IN (
        'REMOTE_HASH_REQUIRED', 'OPERATIONAL_ONLY', 'TRUSTED_REFERENCE'
    )),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    contract_version INTEGER NOT NULL CHECK (contract_version = 2),
    evidence_version INTEGER NOT NULL CHECK (evidence_version = 1),
    plan_id TEXT,
    invocation_id TEXT NOT NULL,
    reference_manifest_path TEXT,
    status TEXT NOT NULL,
    remote_hash_class TEXT,
    evidence_class TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    requests INTEGER NOT NULL DEFAULT 0 CHECK (requests >= 0),
    bytes_reserved INTEGER NOT NULL DEFAULT 0 CHECK (bytes_reserved >= 0),
    bytes_received INTEGER NOT NULL DEFAULT 0 CHECK (bytes_received >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_s6_v2_attempts_media ON s6_v2_attempts(media_item_id, created_at);

CREATE TABLE s6_v2_evidence (
    media_item_id INTEGER PRIMARY KEY REFERENCES media_items(id),
    attempt_id TEXT NOT NULL REFERENCES s6_v2_attempts(id),
    channel_id INTEGER NOT NULL,
    telegram_message_id INTEGER NOT NULL,
    media_ordinal INTEGER NOT NULL,
    telegram_media_id TEXT NOT NULL,
    expected_bytes INTEGER NOT NULL CHECK (expected_bytes >= 0),
    final_path TEXT NOT NULL,
    final_sha256 TEXT NOT NULL,
    selected_mode TEXT NOT NULL CHECK (selected_mode IN (
        'REMOTE_HASH_REQUIRED', 'OPERATIONAL_ONLY', 'TRUSTED_REFERENCE'
    )),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    evidence_class TEXT NOT NULL,
    remote_hash_class TEXT NOT NULL,
    contract_version INTEGER NOT NULL CHECK (contract_version = 2),
    evidence_version INTEGER NOT NULL CHECK (evidence_version = 1),
    plan_id TEXT,
    invocation_id TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
