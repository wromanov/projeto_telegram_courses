CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS channels (
    telegram_chat_id INTEGER PRIMARY KEY,
    title TEXT,
    username TEXT,
    parser_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_scanned_at TEXT
);
CREATE TABLE IF NOT EXISTS catalog_nodes (
    id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES channels(telegram_chat_id),
    parent_id INTEGER REFERENCES catalog_nodes(id),
    kind TEXT NOT NULL,
    code TEXT,
    ordinal INTEGER,
    title TEXT,
    source_message_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    channel_id INTEGER NOT NULL REFERENCES channels(telegram_chat_id),
    telegram_message_id INTEGER NOT NULL,
    message_date_utc TEXT NOT NULL,
    edit_date_utc TEXT,
    text TEXT,
    grouped_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (channel_id, telegram_message_id)
);
CREATE TABLE IF NOT EXISTS media_items (
    id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    telegram_message_id INTEGER NOT NULL,
    media_ordinal INTEGER NOT NULL,
    catalog_node_id INTEGER REFERENCES catalog_nodes(id),
    kind TEXT NOT NULL,
    telegram_media_id TEXT,
    original_filename TEXT,
    mime_type TEXT,
    file_size_bytes INTEGER CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (channel_id, telegram_message_id, media_ordinal),
    FOREIGN KEY (channel_id, telegram_message_id)
        REFERENCES messages(channel_id, telegram_message_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY,
    media_item_id INTEGER NOT NULL REFERENCES media_items(id),
    state TEXT NOT NULL,
    final_path TEXT,
    partial_path TEXT,
    expected_bytes INTEGER,
    downloaded_bytes INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    error_details TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_runs (
    id TEXT PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES channels(telegram_chat_id),
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    watermark_message_id INTEGER,
    messages_seen INTEGER NOT NULL DEFAULT 0,
    messages_new INTEGER NOT NULL DEFAULT 0,
    messages_updated INTEGER NOT NULL DEFAULT 0,
    media_seen INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    stop_reason TEXT,
    error_category TEXT
);
CREATE TABLE IF NOT EXISTS sync_checkpoints (
    scan_run_id TEXT PRIMARY KEY REFERENCES scan_runs(id),
    channel_id INTEGER NOT NULL REFERENCES channels(telegram_chat_id),
    watermark_message_id INTEGER,
    last_message_id INTEGER,
    last_message_date_utc TEXT,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
