-- Marketlytics PostgreSQL namespaces. Raw CSVs are loaded into staging by scripts/load_staging.py.
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

COMMENT ON SCHEMA staging IS 'Source-aligned, text-preserving Olist tables; rebuilt transactionally by the loader.';
COMMENT ON SCHEMA analytics IS 'Typed and modeled analytical tables; populated in later project phases.';
