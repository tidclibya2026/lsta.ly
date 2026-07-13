-- LSTA municipality spatial assignment v1
-- Conservative workflow: proposes municipality matches; never overwrites source values automatically.

CREATE SCHEMA IF NOT EXISTS gis;

CREATE TABLE IF NOT EXISTS gis.municipality_assignment_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL REFERENCES staging.import_batches(batch_id),
    boundary_source text NOT NULL,
    boundary_version text NOT NULL,
    executed_by text NOT NULL,
    executed_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','failed','reviewed')),
    notes text
);

CREATE TABLE IF NOT EXISTS gis.municipality_assignment_candidates (
    candidate_id bigserial PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES gis.municipality_assignment_runs(run_id) ON DELETE CASCADE,
    staging_id bigint NOT NULL REFERENCES staging.tourism_sites_raw(staging_id) ON DELETE CASCADE,
    municipality_id uuid REFERENCES core.administrative_units(administrative_unit_id),
    assignment_method text NOT NULL CHECK (assignment_method IN ('contains','intersects_boundary','nearest','manual')),
    distance_m numeric(12,2),
    confidence numeric(5,2) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    is_primary boolean NOT NULL DEFAULT false,
    review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','accepted','rejected','needs_field_check')),
    reviewed_by text,
    reviewed_at timestamptz,
    review_note text,
    UNIQUE (run_id, staging_id, municipality_id, assignment_method)
);

CREATE INDEX IF NOT EXISTS idx_municipality_candidates_run
    ON gis.municipality_assignment_candidates(run_id, review_status);
CREATE INDEX IF NOT EXISTS idx_municipality_candidates_staging
    ON gis.municipality_assignment_candidates(staging_id);

-- Generate exact polygon containment candidates.
INSERT INTO gis.municipality_assignment_candidates (
    run_id, staging_id, municipality_id, assignment_method, distance_m, confidence, is_primary
)
SELECT
    %(run_id)s,
    n.staging_id,
    a.administrative_unit_id,
    'contains',
    0,
    100,
    true
FROM staging.normalized_sites n
JOIN staging.tourism_sites_raw r ON r.staging_id = n.staging_id
JOIN core.administrative_units a
  ON a.unit_type = 'municipality'
 AND a.geom IS NOT NULL
 AND n.geom IS NOT NULL
 AND ST_Covers(a.geom, n.geom)
WHERE r.batch_id = %(batch_id)s
  AND NULLIF(BTRIM(r.municipality_raw), '') IS NULL
ON CONFLICT DO NOTHING;

-- Boundary ambiguity: points covered by more than one municipality are downgraded for review.
WITH ambiguous AS (
    SELECT run_id, staging_id
    FROM gis.municipality_assignment_candidates
    WHERE run_id = %(run_id)s AND assignment_method = 'contains'
    GROUP BY run_id, staging_id
    HAVING COUNT(*) > 1
)
UPDATE gis.municipality_assignment_candidates c
SET confidence = 70,
    is_primary = false,
    review_status = 'pending',
    review_note = 'نقطة واقعة على حد إداري أو ضمن تداخل هندسي؛ تتطلب مراجعة GIS.'
FROM ambiguous a
WHERE c.run_id = a.run_id AND c.staging_id = a.staging_id;

-- Nearest municipality fallback within a controlled 10 km radius.
INSERT INTO gis.municipality_assignment_candidates (
    run_id, staging_id, municipality_id, assignment_method, distance_m, confidence, is_primary
)
SELECT
    %(run_id)s,
    n.staging_id,
    nearest.administrative_unit_id,
    'nearest',
    nearest.distance_m,
    CASE
      WHEN nearest.distance_m <= 1000 THEN 85
      WHEN nearest.distance_m <= 5000 THEN 65
      ELSE 45
    END,
    true
FROM staging.normalized_sites n
JOIN staging.tourism_sites_raw r ON r.staging_id = n.staging_id
CROSS JOIN LATERAL (
    SELECT a.administrative_unit_id,
           ST_Distance(a.geom::geography, n.geom::geography) AS distance_m
    FROM core.administrative_units a
    WHERE a.unit_type = 'municipality' AND a.geom IS NOT NULL
    ORDER BY a.geom <-> n.geom
    LIMIT 1
) nearest
WHERE r.batch_id = %(batch_id)s
  AND n.geom IS NOT NULL
  AND NULLIF(BTRIM(r.municipality_raw), '') IS NULL
  AND nearest.distance_m <= 10000
  AND NOT EXISTS (
      SELECT 1 FROM gis.municipality_assignment_candidates c
      WHERE c.run_id = %(run_id)s AND c.staging_id = n.staging_id
  )
ON CONFLICT DO NOTHING;

CREATE OR REPLACE VIEW gis.v_municipality_assignment_review AS
SELECT
    c.candidate_id,
    c.run_id,
    r.batch_id,
    r.source_record_id,
    r.name_ar_raw,
    r.latitude_raw,
    r.longitude_raw,
    a.name_ar AS proposed_municipality,
    c.assignment_method,
    c.distance_m,
    c.confidence,
    c.review_status,
    c.review_note
FROM gis.municipality_assignment_candidates c
JOIN staging.tourism_sites_raw r ON r.staging_id = c.staging_id
LEFT JOIN core.administrative_units a ON a.administrative_unit_id = c.municipality_id;

-- Only reviewed and accepted candidates may update normalized staging values.
-- This statement is intentionally separated from candidate generation.
UPDATE staging.normalized_sites n
SET municipality_id = c.municipality_id,
    normalized_municipality_name = a.name_ar
FROM gis.municipality_assignment_candidates c
JOIN core.administrative_units a ON a.administrative_unit_id = c.municipality_id
WHERE n.staging_id = c.staging_id
  AND c.review_status = 'accepted'
  AND c.is_primary = true
  AND n.municipality_id IS NULL;
