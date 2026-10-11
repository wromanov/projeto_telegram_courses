ALTER TABLE downloads ADD COLUMN sha256 TEXT;
ALTER TABLE downloads ADD COLUMN validated_at TEXT;
ALTER TABLE downloads ADD COLUMN failure_category TEXT;
ALTER TABLE downloads ADD COLUMN owner_pid INTEGER;
CREATE UNIQUE INDEX IF NOT EXISTS ux_downloads_media_item ON downloads(media_item_id);
