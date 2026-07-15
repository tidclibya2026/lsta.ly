"""metadata catalog and lineage

Revision ID: 7b8d5f21ea32
Revises: 6a7c4e10d921
"""

from typing import Sequence, Union

from alembic import op

revision: str = "7b8d5f21ea32"
down_revision: Union[str, None] = "6a7c4e10d921"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SQL = r"""
CREATE SCHEMA IF NOT EXISTS metadata;
CREATE TABLE metadata.catalog_entries (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), catalog_code varchar(160) UNIQUE NOT NULL, entry_type varchar(40) NOT NULL, title_ar varchar(500) NOT NULL, title_en varchar(500), description_ar text, description_en text, owning_organization varchar(500) NOT NULL, steward_name varchar(300), technical_owner varchar(300), source_system varchar(300), source_reference text, classification_level varchar(30) NOT NULL DEFAULT 'internal' CHECK (classification_level IN ('public','internal','restricted','confidential')), sensitivity_level varchar(20) NOT NULL DEFAULT 'low' CHECK (sensitivity_level IN ('none','low','medium','high')), lifecycle_status varchar(30) NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN ('draft','active','deprecated','archived')), verification_status varchar(40) NOT NULL DEFAULT 'draft', publication_status varchar(40) NOT NULL DEFAULT 'internal', metadata_standard varchar(100) NOT NULL DEFAULT 'LSTA', metadata_json jsonb NOT NULL DEFAULT '{}', keywords text[] NOT NULL DEFAULT '{}', tags text[] NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), archived_at timestamptz);
CREATE TABLE metadata.catalog_fields (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), catalog_entry_id uuid NOT NULL REFERENCES metadata.catalog_entries(id) ON DELETE CASCADE, field_name varchar(200) NOT NULL, label_ar varchar(300) NOT NULL, label_en varchar(300), data_type varchar(100) NOT NULL, description_ar text, description_en text, nullable boolean NOT NULL DEFAULT true, required boolean NOT NULL DEFAULT false, is_identifier boolean NOT NULL DEFAULT false, is_spatial boolean NOT NULL DEFAULT false, is_sensitive boolean NOT NULL DEFAULT false, validation_rules jsonb NOT NULL DEFAULT '{}', allowed_values jsonb, unit varchar(100), source_field varchar(200), display_order integer NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(catalog_entry_id,field_name));
CREATE TABLE metadata.data_lineage_nodes (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), node_type varchar(40) NOT NULL, node_reference text NOT NULL, title varchar(500) NOT NULL, system_name varchar(200) NOT NULL, metadata_json jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(node_type,node_reference));
CREATE TABLE metadata.data_lineage_edges (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_node_id uuid NOT NULL REFERENCES metadata.data_lineage_nodes(id), target_node_id uuid NOT NULL REFERENCES metadata.data_lineage_nodes(id), transformation_type varchar(40) NOT NULL, transformation_reference text, process_name varchar(300) NOT NULL, process_version varchar(80), executed_by varchar(200), executed_at timestamptz NOT NULL DEFAULT now(), status varchar(20) NOT NULL DEFAULT 'success' CHECK(status IN ('success','failed','partial','pending')), metadata_json jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(source_node_id,target_node_id,transformation_type), CHECK(source_node_id<>target_node_id));
CREATE TABLE metadata.data_quality_rules (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), rule_code varchar(160) UNIQUE NOT NULL, name_ar varchar(500) NOT NULL, name_en varchar(500), description text NOT NULL, target_entity varchar(160) NOT NULL, target_field varchar(160), rule_type varchar(40) NOT NULL, severity varchar(20) NOT NULL, rule_expression jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE metadata.data_quality_results (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), rule_id uuid NOT NULL REFERENCES metadata.data_quality_rules(id), entity_type varchar(160) NOT NULL, entity_id text NOT NULL, status varchar(20) NOT NULL CHECK(status IN ('passed','failed','warning','skipped')), score numeric(5,2), issue_details jsonb NOT NULL DEFAULT '{}', evaluated_at timestamptz NOT NULL DEFAULT now(), evaluated_by varchar(200) NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE metadata.dataset_versions (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), catalog_entry_id uuid NOT NULL REFERENCES metadata.catalog_entries(id), version_number integer NOT NULL, version_label varchar(160) NOT NULL, checksum varchar(64), schema_snapshot jsonb NOT NULL DEFAULT '{}', row_count bigint, spatial_feature_count bigint, created_by varchar(200), created_at timestamptz NOT NULL DEFAULT now(), release_notes text, UNIQUE(catalog_entry_id,version_number));
CREATE INDEX ix_catalog_entry_type ON metadata.catalog_entries(entry_type); CREATE INDEX ix_catalog_lifecycle ON metadata.catalog_entries(lifecycle_status); CREATE INDEX ix_catalog_verification ON metadata.catalog_entries(verification_status); CREATE INDEX ix_catalog_publication ON metadata.catalog_entries(publication_status); CREATE INDEX ix_catalog_keywords_gin ON metadata.catalog_entries USING gin(keywords); CREATE INDEX ix_catalog_tags_gin ON metadata.catalog_entries USING gin(tags); CREATE INDEX ix_catalog_fields_entry ON metadata.catalog_fields(catalog_entry_id); CREATE INDEX ix_lineage_node_type_reference ON metadata.data_lineage_nodes(node_type,node_reference); CREATE INDEX ix_lineage_source ON metadata.data_lineage_edges(source_node_id); CREATE INDEX ix_lineage_target ON metadata.data_lineage_edges(target_node_id); CREATE INDEX ix_lineage_transformation ON metadata.data_lineage_edges(transformation_type); CREATE INDEX ix_quality_target ON metadata.data_quality_rules(target_entity); CREATE INDEX ix_quality_severity ON metadata.data_quality_rules(severity); CREATE INDEX ix_dataset_versions_entry ON metadata.dataset_versions(catalog_entry_id);
INSERT INTO metadata.catalog_entries(catalog_code,entry_type,title_ar,owning_organization,source_system,source_reference,classification_level,sensitivity_level,lifecycle_status,verification_status,publication_status,metadata_standard,metadata_json,keywords,tags) VALUES
('LSTA-DS-OLD-TRIPOLI-KML','source_file','ملف KML للمدينة القديمة طرابلس','منصة أطلس ليبيا السياحي الذكي','Google My Maps','المدينة القديمة طرابلس','internal','medium','active','imported','internal','LSTA Metadata 1.0','{"sha256":"701dc1d488b399805f474505cfcc829a56d2a64cdbd2b976c6f4aff0e5e2d188"}','{KML,طرابلس}','{source}'),
('LSTA-DS-OLD-TRIPOLI-STAGING','dataset','بيانات المدينة القديمة في Staging','منصة أطلس ليبيا السياحي الذكي','PostgreSQL/PostGIS','staging.import_features','internal','medium','active','pending_review','internal','LSTA Metadata 1.0','{"row_count":430}','{staging,طرابلس}','{dataset}'),
('LSTA-REGISTRY-SITES','registry','السجل الوطني للمواقع السياحية','منصة أطلس ليبيا السياحي الذكي','PostgreSQL/PostGIS','atlas.sites','internal','low','active','approved','internal','LSTA Metadata 1.0','{}','{registry,sites}','{national}'),
('LSTA-API-REVIEW','api_endpoint','واجهة بوابة المراجعة','منصة أطلس ليبيا السياحي الذكي','FastAPI','/api/v1/review','internal','medium','active','approved','internal','LSTA Metadata 1.0','{}','{API,review}','{service}'),
('LSTA-API-REGISTRY','api_endpoint','واجهة السجل الوطني','منصة أطلس ليبيا السياحي الذكي','FastAPI','/api/v1/registry','internal','low','active','approved','internal','LSTA Metadata 1.0','{}','{API,registry}','{service}'),
('LSTA-API-SEARCH','api_endpoint','واجهة البحث الوطني','منصة أطلس ليبيا السياحي الذكي','FastAPI','/api/v1/search','internal','low','active','approved','internal','LSTA Metadata 1.0','{}','{API,search}','{service}'),
('LSTA-LAYER-OLD-TRIPOLI-REVIEW','map_layer','طبقة مراجعة المدينة القديمة طرابلس','منصة أطلس ليبيا السياحي الذكي','MapLibre','old-tripoli-review','internal','medium','active','pending_review','internal','LSTA Metadata 1.0','{"feature_count":430}','{map,review}','{layer}');
INSERT INTO metadata.data_quality_rules(rule_code,name_ar,description,target_entity,target_field,rule_type,severity,rule_expression) VALUES
('SITE_NAME_AR_REQUIRED','الاسم العربي مطلوب','فحص وجود الاسم العربي','atlas.sites','name_ar','required','error','{"operator":"not_empty"}'),('SITE_GEOMETRY_VALID','هندسة الموقع صالحة','فحص PostGIS','atlas.site_geometries','geometry','spatial','critical','{"operator":"is_valid"}'),('SITE_SOURCE_REQUIRED','مصدر الموقع مطلوب','فحص المصدر','atlas.sites','data_source_id','required','error','{"operator":"not_null"}'),('SITE_NATIONAL_ID_UNIQUE','المعرف الوطني فريد','فحص التفرد','atlas.sites','national_id','uniqueness','critical','{"operator":"unique"}'),('STAGING_FEATURE_ID_REQUIRED','معرف Staging مطلوب','فحص المعرف','staging.import_features','source_feature_id','required','error','{"operator":"not_empty"}'),('STAGING_GEOMETRY_VALID','هندسة Staging صالحة','فحص PostGIS','staging.import_features','geometry','spatial','critical','{"operator":"is_valid"}'),('SOURCE_SHA256_REQUIRED','بصمة المصدر مطلوبة','فحص SHA-256','atlas.data_sources','sha256','format','critical','{"operator":"sha256"}'),('MEDIA_RIGHTS_REQUIRED','حقوق الصورة مطلوبة','فحص الحقوق','atlas.media_assets','rights','required','error','{"operator":"not_empty"}'),('DOCUMENT_SHA256_RECOMMENDED','بصمة الوثيقة موصى بها','فحص الوثيقة','atlas.site_documents','sha256','format','warning','{"operator":"sha256"}'),('MUNICIPALITY_REQUIRED_FOR_PUBLICATION','البلدية مطلوبة للنشر','فحص البلدية','atlas.sites','municipality_id','consistency','error','{"when":"publication"}');
"""

LINEAGE_SQL = r"""
INSERT INTO metadata.data_lineage_nodes(node_type,node_reference,title,system_name,metadata_json)
SELECT 'source_file', ds.sha256, ds.source_file, 'KML Importer', jsonb_build_object('sha256',ds.sha256) FROM atlas.data_sources ds ON CONFLICT DO NOTHING;
INSERT INTO metadata.data_lineage_nodes(node_type,node_reference,title,system_name)
SELECT 'import_batch', b.id::text, 'Import batch '||b.id::text, 'LSTA Staging' FROM staging.import_batches b ON CONFLICT DO NOTHING;
INSERT INTO metadata.data_lineage_nodes(node_type,node_reference,title,system_name)
SELECT 'staging_feature', f.id::text, coalesce(f.name_ar,f.source_feature_id), 'LSTA Staging' FROM staging.import_features f ON CONFLICT DO NOTHING;
INSERT INTO metadata.data_lineage_nodes(node_type,node_reference,title,system_name)
SELECT 'national_site', s.national_id, s.name_ar, 'National Registry' FROM atlas.sites s ON CONFLICT DO NOTHING;
INSERT INTO metadata.data_lineage_nodes(node_type,node_reference,title,system_name)
SELECT 'site_geometry', g.id::text, g.geometry_type||' geometry', 'PostGIS' FROM atlas.site_geometries g ON CONFLICT DO NOTHING;
INSERT INTO metadata.data_lineage_edges(source_node_id,target_node_id,transformation_type,process_name)
SELECT sn.id,bn.id,'imported_from','KML importer' FROM atlas.data_sources ds JOIN staging.import_batches b ON b.data_source_id=ds.id JOIN metadata.data_lineage_nodes sn ON sn.node_type='source_file' AND sn.node_reference=ds.sha256 JOIN metadata.data_lineage_nodes bn ON bn.node_type='import_batch' AND bn.node_reference=b.id::text ON CONFLICT DO NOTHING;
INSERT INTO metadata.data_lineage_edges(source_node_id,target_node_id,transformation_type,process_name)
SELECT bn.id,fn.id,'parsed_into','KML importer' FROM staging.import_features f JOIN metadata.data_lineage_nodes bn ON bn.node_type='import_batch' AND bn.node_reference=f.batch_id::text JOIN metadata.data_lineage_nodes fn ON fn.node_type='staging_feature' AND fn.node_reference=f.id::text ON CONFLICT DO NOTHING;
INSERT INTO metadata.data_lineage_edges(source_node_id,target_node_id,transformation_type,process_name)
SELECT fn.id,sn.id,'promoted_to','Promotion service' FROM staging.promotion_records p JOIN metadata.data_lineage_nodes fn ON fn.node_type='staging_feature' AND fn.node_reference=p.import_feature_id::text JOIN atlas.sites s ON s.id=p.site_id JOIN metadata.data_lineage_nodes sn ON sn.node_type='national_site' AND sn.node_reference=s.national_id WHERE p.status='promoted' ON CONFLICT DO NOTHING;
INSERT INTO metadata.data_lineage_edges(source_node_id,target_node_id,transformation_type,process_name)
SELECT sn.id,gn.id,'linked_to','Registry service' FROM atlas.site_geometries g JOIN atlas.sites s ON s.id=g.site_id JOIN metadata.data_lineage_nodes sn ON sn.node_type='national_site' AND sn.node_reference=s.national_id JOIN metadata.data_lineage_nodes gn ON gn.node_type='site_geometry' AND gn.node_reference=g.id::text ON CONFLICT DO NOTHING;
"""


def upgrade() -> None:
    connection = op.get_bind()
    connection.exec_driver_sql(SQL)
    connection.exec_driver_sql(LINEAGE_SQL)


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS metadata CASCADE")
