CREATE TABLE IF NOT EXISTS catalog_unresolved_sources (
    run_id TEXT NOT NULL REFERENCES catalog_runs(id) ON DELETE CASCADE,
    channel_id INTEGER NOT NULL,
    telegram_message_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (run_id, telegram_message_id),
    FOREIGN KEY (channel_id, telegram_message_id)
        REFERENCES messages(channel_id, telegram_message_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_catalog_unresolved_channel_message
    ON catalog_unresolved_sources(channel_id, telegram_message_id);
