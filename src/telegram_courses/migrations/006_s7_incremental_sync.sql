-- S7 incremental synchronization checkpoints and immutable download identity.
-- Existing S2/S5/S6 migrations are intentionally left unchanged.

ALTER TABLE scan_runs ADD COLUMN sync_mode TEXT NOT NULL DEFAULT 'FULL';
ALTER TABLE scan_runs ADD COLUMN sync_baseline_confirmed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scan_runs ADD COLUMN sync_high_water_before INTEGER;
ALTER TABLE scan_runs ADD COLUMN sync_reconcile_floor_message_id INTEGER;
ALTER TABLE scan_runs ADD COLUMN sync_reconcile_window INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scan_runs ADD COLUMN sync_max_messages INTEGER;
ALTER TABLE scan_runs ADD COLUMN messages_unverified INTEGER;
ALTER TABLE scan_runs ADD COLUMN owner_pid INTEGER;
ALTER TABLE scan_runs ADD COLUMN sync_snapshot_head_message_id INTEGER;

-- Records the run that last observed each message. A missing observation is
-- only evidence of non-observation, never evidence of deletion.
ALTER TABLE messages ADD COLUMN last_seen_run_id TEXT;

-- Snapshot the remote identity represented by each physical download. S7
-- compares this snapshot to the current media item before planning or commit.
ALTER TABLE downloads ADD COLUMN remote_identity_media_id TEXT;
ALTER TABLE downloads ADD COLUMN remote_identity_kind TEXT;
ALTER TABLE downloads ADD COLUMN remote_identity_size INTEGER;

UPDATE downloads
SET remote_identity_media_id = (
        SELECT telegram_media_id FROM media_items WHERE media_items.id = downloads.media_item_id
    ),
    remote_identity_kind = (
        SELECT kind FROM media_items WHERE media_items.id = downloads.media_item_id
    ),
    remote_identity_size = (
        SELECT file_size_bytes FROM media_items WHERE media_items.id = downloads.media_item_id
    );

CREATE INDEX IF NOT EXISTS ix_scan_runs_channel_status_finished
    ON scan_runs(channel_id, status, finished_at);
