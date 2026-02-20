-- Add description column to holdings table
-- Needed by holdings_extractor for autocallable note detection
-- and other description-based feature extraction.

ALTER TABLE holdings ADD COLUMN IF NOT EXISTS description TEXT;
