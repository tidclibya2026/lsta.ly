-- منصة أطلس ليبيا السياحي الذكي
-- المرحلة: جداول الاستقبال المرحلي والتحقق قبل الترحيل
-- PostgreSQL 16 + PostGIS 3.x

BEGIN;

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TYPE staging.import_status AS ENUM (
  'uploaded',
  'profiled',
  'validated',
  'needs_review',
  'approved',
  'rejected',
  'promoted'
);

CREATE TABLE IF NOT EXISTS staging.import_batches (
  batch_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_file_name text NOT NULL,
  source_layer_code text NOT NULL,
  source_sha256 text NOT NULL,
  source_row_count integer,
  submitted_by text,
  submitted_at timestamptz NOT NULL DEFAULT now(),
  status staging.import_status NOT NULL DEFAULT 'uploaded',
  approved_by text,
  approved_at timestamptz,
  notes text,
  UNIQUE (source_sha256, source_layer_code)
);

CREATE TABLE IF NOT EXISTS staging.tourism_sites_raw (
  staging_id bigserial PRIMARY KEY,
  batch_id uuid NOT NULL REFERENCES staging.import_batches(batch_id) ON DELETE CASCADE,
  source_row_number integer NOT NULL,
  source_record_id text,
  layer_code text NOT NULL,
  name_ar_raw text,
  name_en_raw text,
  municipality_raw text,
  tourism_region_raw text,
  latitude_raw text,
  longitude_raw text,
  national_category_raw text,
  category_code_raw text,
  subcategory_raw text,
  address_raw text,
  phone_raw text,
  web_or_social_raw text,
  description_raw text,
  verification_status_raw text,
  verification_priority_raw text,
  source_type_raw text,
  source_files_raw text,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  loaded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (batch_id, source_row_number)
);

CREATE TABLE IF NOT EXISTS staging.validation_results (
  validation_id bigserial PRIMARY KEY,
  staging_id bigint NOT NULL REFERENCES staging.tourism_sites_raw(staging_id) ON DELETE CASCADE,
  rule_code text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('info','warning','error','critical')),
  field_name text,
  observed_value text,
  message_ar text NOT NULL,
  suggested_action_ar text,
  is_resolved boolean NOT NULL DEFAULT false,
  resolved_by text,
  resolved_at timestamptz,
  resolution_note text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.normalized_sites (
  staging_id bigint PRIMARY KEY REFERENCES staging.tourism_sites_raw(staging_id) ON DELETE CASCADE,
  normalized_name_ar text,
  normalized_name_en text,
  normalized_phone text,
  normalized_municipality_name text,
  latitude double precision,
  longitude double precision,
  geom geometry(Point, 4326),
  normalized_category_code text,
  normalized_verification_status text,
  normalized_source_reference text,
  completeness_score numeric(5,2),
  spatial_valid boolean,
  duplicate_candidate boolean NOT NULL DEFAULT false,
  normalization_notes jsonb NOT NULL DEFAULT '{}'::jsonb,
  normalized_at timestamptz NOT NULL DEFAULT now(),
  CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);

CREATE TABLE IF NOT EXISTS staging.duplicate_candidates (
  candidate_id bigserial PRIMARY KEY,
  staging_id bigint NOT NULL REFERENCES staging.tourism_sites_raw(staging_id) ON DELETE CASCADE,
  existing_site_id uuid,
  candidate_staging_id bigint REFERENCES staging.tourism_sites_raw(staging_id) ON DELETE CASCADE,
  name_similarity numeric(5,4),
  distance_meters numeric(12,2),
  municipality_match boolean,
  category_match boolean,
  confidence_score numeric(5,4),
  recommendation text CHECK (recommendation IN ('merge','keep_separate','manual_review')),
  reviewed_by text,
  reviewed_at timestamptz,
  review_decision text,
  UNIQUE (staging_id, existing_site_id, candidate_staging_id)
);

CREATE TABLE IF NOT EXISTS audit.import_events (
  event_id bigserial PRIMARY KEY,
  batch_id uuid REFERENCES staging.import_batches(batch_id) ON DELETE SET NULL,
  staging_id bigint REFERENCES staging.tourism_sites_raw(staging_id) ON DELETE SET NULL,
  event_type text NOT NULL,
  actor text,
  event_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_staging_raw_batch ON staging.tourism_sites_raw(batch_id);
CREATE INDEX IF NOT EXISTS idx_staging_raw_layer ON staging.tourism_sites_raw(layer_code);
CREATE INDEX IF NOT EXISTS idx_validation_staging ON staging.validation_results(staging_id);
CREATE INDEX IF NOT EXISTS idx_validation_unresolved ON staging.validation_results(is_resolved) WHERE is_resolved = false;
CREATE INDEX IF NOT EXISTS idx_normalized_geom ON staging.normalized_sites USING gist(geom);
CREATE INDEX IF NOT EXISTS idx_duplicate_staging ON staging.duplicate_candidates(staging_id);

CREATE OR REPLACE VIEW staging.v_batch_quality_summary AS
SELECT
  b.batch_id,
  b.source_file_name,
  b.source_layer_code,
  b.status,
  count(DISTINCT r.staging_id) AS total_rows,
  count(v.validation_id) FILTER (WHERE v.severity = 'critical' AND NOT v.is_resolved) AS critical_issues,
  count(v.validation_id) FILTER (WHERE v.severity = 'error' AND NOT v.is_resolved) AS error_issues,
  count(v.validation_id) FILTER (WHERE v.severity = 'warning' AND NOT v.is_resolved) AS warning_issues,
  round(avg(n.completeness_score), 2) AS average_completeness,
  count(*) FILTER (WHERE n.duplicate_candidate) AS duplicate_candidates
FROM staging.import_batches b
LEFT JOIN staging.tourism_sites_raw r ON r.batch_id = b.batch_id
LEFT JOIN staging.validation_results v ON v.staging_id = r.staging_id
LEFT JOIN staging.normalized_sites n ON n.staging_id = r.staging_id
GROUP BY b.batch_id;

COMMIT;
