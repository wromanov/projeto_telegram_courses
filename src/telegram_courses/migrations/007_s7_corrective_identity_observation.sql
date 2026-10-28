-- S7 corrective provenance and observation state. Legacy evidence is retained.
ALTER TABLE downloads ADD COLUMN remote_identity_provenance TEXT NOT NULL DEFAULT 'UNKNOWN_LEGACY';
ALTER TABLE media_items ADD COLUMN remote_observation_state TEXT NOT NULL DEFAULT 'OBSERVED';
ALTER TABLE scan_runs ADD COLUMN media_unverified INTEGER NOT NULL DEFAULT 0;
