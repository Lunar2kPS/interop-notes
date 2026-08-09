-- NOTE: If you need to re-run this, use the following:
-- podman exec -it s3-analysis-database bash
-- cd /docker-entrypoint-initdb.d
-- psql -h 127.0.0.1 -p 5432 -U root -d localdev -f ./0001-table-comments.sql

COMMENT ON COLUMN s3analysis.example_table.s3_endpoint
    IS 'The S3 URL that this [redacted] was read from.';

COMMENT ON COLUMN s3analysis.example_table.s3_bucket
    IS 'The S3 bucket that this [redacted] was read from.';
