-- Libya Smart Tourism Atlas (LSTA)
-- Core PostgreSQL/PostGIS schema — Version 1.0

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE verification_status AS ENUM (
  'draft',
  'under_review',
  'desk_verified',
  'field_verification_required',
  'approved',
  'archived'
);

CREATE TYPE verification_priority AS ENUM ('high', 'medium', 'low');
CREATE TYPE publication_status AS ENUM ('internal', 'institutional', 'public', 'visit_libya');

CREATE TABLE organizations (
  organization_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name_ar text NOT NULL,
  name_en text,
  organization_type text,
  is_data_owner boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE administrative_units (
  administrative_unit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name_ar text NOT NULL,
  name_en text,
  unit_type text NOT NULL,
  parent_id uuid REFERENCES administrative_units(administrative_unit_id),
  geom geometry(MultiPolygon, 4326),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE development_circles (
  development_circle_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name_ar text NOT NULL,
  name_en text,
  description_ar text,
  source_reference text,
  planning_horizon text,
  geom geometry(MultiPolygon, 4326) NOT NULL,
  verification_status verification_status NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE spatial_development_zones (
  spatial_zone_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name_ar text NOT NULL,
  zone_type text NOT NULL,
  priority_score numeric(5,2),
  methodology_version text,
  geom geometry(MultiPolygon, 4326) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE site_categories (
  category_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  name_ar text NOT NULL,
  name_en text,
  parent_id uuid REFERENCES site_categories(category_id),
  is_public boolean NOT NULL DEFAULT true,
  sort_order integer NOT NULL DEFAULT 0
);

CREATE TABLE tourism_sites (
  site_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  legacy_master_id text,
  name_ar text NOT NULL,
  name_en text,
  promotional_name_ar text,
  promotional_name_en text,
  category_id uuid NOT NULL REFERENCES site_categories(category_id),
  municipality_id uuid REFERENCES administrative_units(administrative_unit_id),
  development_circle_id uuid REFERENCES development_circles(development_circle_id),
  spatial_zone_id uuid REFERENCES spatial_development_zones(spatial_zone_id),
  data_owner_id uuid REFERENCES organizations(organization_id),
  geom geometry(Point, 4326) NOT NULL,
  address_ar text,
  address_en text,
  short_description_ar text,
  short_description_en text,
  sustainability_score numeric(5,2) CHECK (sustainability_score BETWEEN 0 AND 100),
  verification_status verification_status NOT NULL DEFAULT 'draft',
  verification_priority verification_priority NOT NULL DEFAULT 'medium',
  publication_status publication_status NOT NULL DEFAULT 'internal',
  source_reference text NOT NULL,
  verified_at timestamptz,
  record_version integer NOT NULL DEFAULT 1,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT unique_legacy_master_id UNIQUE NULLS NOT DISTINCT (legacy_master_id)
);

CREATE INDEX tourism_sites_geom_gix ON tourism_sites USING gist (geom);
CREATE INDEX development_circles_geom_gix ON development_circles USING gist (geom);
CREATE INDEX spatial_development_zones_geom_gix ON spatial_development_zones USING gist (geom);
CREATE INDEX administrative_units_geom_gix ON administrative_units USING gist (geom);
CREATE INDEX tourism_sites_category_idx ON tourism_sites(category_id);
CREATE INDEX tourism_sites_verification_idx ON tourism_sites(verification_status);
CREATE INDEX tourism_sites_publication_idx ON tourism_sites(publication_status);

CREATE TABLE accommodation_details (
  site_id uuid PRIMARY KEY REFERENCES tourism_sites(site_id) ON DELETE CASCADE,
  facility_type text,
  star_rating numeric(2,1),
  rooms_count integer CHECK (rooms_count >= 0),
  beds_count integer CHECK (beds_count >= 0),
  chalets_count integer CHECK (chalets_count >= 0),
  operating_status text,
  license_number text,
  license_expiry_date date
);

CREATE TABLE food_service_details (
  site_id uuid PRIMARY KEY REFERENCES tourism_sites(site_id) ON DELETE CASCADE,
  establishment_type text,
  cuisine_type text,
  seating_capacity integer CHECK (seating_capacity >= 0),
  opening_hours jsonb,
  service_level text
);

CREATE TABLE media_assets (
  media_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES tourism_sites(site_id) ON DELETE CASCADE,
  media_type text NOT NULL,
  storage_key text NOT NULL,
  title_ar text,
  title_en text,
  is_primary boolean NOT NULL DEFAULT false,
  copyright_holder text,
  license_type text,
  verification_status verification_status NOT NULL DEFAULT 'under_review',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE data_sources (
  source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_name text NOT NULL,
  source_type text NOT NULL,
  organization_id uuid REFERENCES organizations(organization_id),
  reference_uri text,
  issued_at date,
  imported_at timestamptz NOT NULL DEFAULT now(),
  checksum text
);

CREATE TABLE site_source_links (
  site_id uuid NOT NULL REFERENCES tourism_sites(site_id) ON DELETE CASCADE,
  source_id uuid NOT NULL REFERENCES data_sources(source_id) ON DELETE CASCADE,
  source_record_key text,
  confidence_score numeric(5,2),
  PRIMARY KEY (site_id, source_id, source_record_key)
);

CREATE TABLE verification_history (
  verification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id uuid NOT NULL REFERENCES tourism_sites(site_id) ON DELETE CASCADE,
  previous_status verification_status,
  new_status verification_status NOT NULL,
  action_type text NOT NULL,
  notes text,
  evidence jsonb,
  changed_by uuid,
  changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE record_change_history (
  change_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  version_no integer NOT NULL,
  changed_fields jsonb NOT NULL,
  change_reason text,
  changed_by uuid,
  changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE studies_and_reports (
  document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title_ar text NOT NULL,
  title_en text,
  document_type text NOT NULL,
  issuing_organization_id uuid REFERENCES organizations(organization_id),
  publication_year integer,
  storage_key text,
  extracted_text text,
  metadata jsonb,
  verification_status verification_status NOT NULL DEFAULT 'under_review',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE document_chunks (
  chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES studies_and_reports(document_id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  chunk_text text NOT NULL,
  embedding vector(1536),
  metadata jsonb,
  UNIQUE(document_id, chunk_index)
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tourism_sites_set_updated_at
BEFORE UPDATE ON tourism_sites
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER development_circles_set_updated_at
BEFORE UPDATE ON development_circles
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Public API view: only approved records explicitly marked for Visit Libya.
CREATE VIEW visit_libya_sites_v1 AS
SELECT
  s.site_id,
  s.name_ar,
  s.name_en,
  c.code AS category_code,
  c.name_ar AS category_name_ar,
  s.short_description_ar,
  s.short_description_en,
  ST_Y(s.geom) AS latitude,
  ST_X(s.geom) AS longitude,
  s.address_ar,
  s.address_en,
  s.updated_at
FROM tourism_sites s
JOIN site_categories c ON c.category_id = s.category_id
WHERE s.verification_status = 'approved'
  AND s.publication_status = 'visit_libya'
  AND s.is_active = true;
