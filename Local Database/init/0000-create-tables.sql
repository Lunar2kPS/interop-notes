-- SCHEMA: A logical namespace for our tables:
CREATE SCHEMA IF NOT EXISTS s3analysis;

CREATE TABLE IF NOT EXISTS s3analysis.example_table (
    s3_endpoint                 text        NOT NULL,
    s3_bucket                   text        NOT NULL,
    s3_parent_path              text        NOT NULL,
    valueA                      text        NOT NULL,
    valueB                      integer     NOT NULL,
    valueC                      text        NOT NULL,
    valueD                      text        NOT NULL,
    jt_file_count               integer     NOT NULL,
    glb_file_count              integer     NOT NULL,
    drc_file_count              integer     NOT NULL,
    hasSomeFile                 boolean     NOT NULL,

    last_updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT example_table_pk PRIMARY KEY (
        s3_endpoint,
        s3_bucket,
        s3_parent_path,
        valueA,
        valueB,
        valueC,
        valueD
    )
);
