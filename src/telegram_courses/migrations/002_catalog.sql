ALTER TABLE catalog_nodes
    ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1
    CHECK (is_active IN (0, 1));

CREATE TABLE IF NOT EXISTS catalog_node_identity (
    channel_id INTEGER NOT NULL REFERENCES channels(telegram_chat_id),
    parser_key TEXT NOT NULL,
    grammar_version TEXT NOT NULL,
    node_key TEXT NOT NULL,
    catalog_node_id INTEGER NOT NULL REFERENCES catalog_nodes(id) ON DELETE RESTRICT,
    PRIMARY KEY (channel_id, parser_key, grammar_version, node_key),
    UNIQUE (catalog_node_id)
);

CREATE INDEX IF NOT EXISTS ix_catalog_node_identity_node
    ON catalog_node_identity(catalog_node_id);

CREATE TABLE IF NOT EXISTS catalog_runs (
    id TEXT PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES channels(telegram_chat_id),
    parser_key TEXT NOT NULL,
    grammar_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('COMPLETE')),
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    source_message_count INTEGER NOT NULL CHECK (source_message_count >= 0),
    catalog_node_count INTEGER NOT NULL CHECK (catalog_node_count >= 0),
    unresolved_count INTEGER NOT NULL CHECK (unresolved_count >= 0)
);

CREATE INDEX IF NOT EXISTS ix_catalog_runs_channel_finished
    ON catalog_runs(channel_id, finished_at DESC);
