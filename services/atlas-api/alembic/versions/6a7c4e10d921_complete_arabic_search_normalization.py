"""complete Arabic search normalization

Revision ID: 6a7c4e10d921
Revises: 04582d2f4d34
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "6a7c4e10d921"
down_revision: Union[str, None] = "04582d2f4d34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("normalized_name_ar", sa.Text(), nullable=True), schema="atlas")
    op.add_column("sites", sa.Column("normalized_name_en", sa.Text(), nullable=True), schema="atlas")
    op.add_column("import_features", sa.Column("normalized_name_ar", sa.Text(), nullable=True), schema="staging")
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION atlas.normalize_arabic_search(value text)
        RETURNS text AS $$
          SELECT trim(regexp_replace(
            translate(
              regexp_replace(lower(unaccent(coalesce(value, ''))),
                '[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06edـ]', '', 'g'),
              'إأآٱىة', 'اااايه'
            ), '\s+', ' ', 'g'))
        $$ LANGUAGE sql IMMUTABLE PARALLEL SAFE;

        CREATE OR REPLACE FUNCTION atlas.update_site_search_vector() RETURNS trigger AS $$
        BEGIN
          NEW.normalized_name_ar := atlas.normalize_arabic_search(NEW.name_ar);
          NEW.normalized_name_en := lower(unaccent(trim(regexp_replace(coalesce(NEW.name_en, ''), '\s+', ' ', 'g'))));
          NEW.search_vector := to_tsvector('simple', unaccent(concat_ws(' ',
            NEW.national_id, NEW.normalized_name_ar, NEW.normalized_name_en, NEW.description)));
          RETURN NEW;
        END $$ LANGUAGE plpgsql;

        CREATE OR REPLACE FUNCTION staging.update_feature_search_vector() RETURNS trigger AS $$
        BEGIN
          NEW.normalized_name_ar := atlas.normalize_arabic_search(NEW.name_ar);
          NEW.search_vector := to_tsvector('simple', unaccent(concat_ws(' ',
            NEW.source_feature_id, NEW.normalized_name_ar, NEW.properties->>'name_en',
            NEW.properties->>'description_text', NEW.properties->>'folder_name')));
          RETURN NEW;
        END $$ LANGUAGE plpgsql;

        UPDATE atlas.sites SET name_ar = name_ar;
        UPDATE staging.import_features SET name_ar = name_ar;
        """
    )


def downgrade() -> None:
    op.drop_column("import_features", "normalized_name_ar", schema="staging")
    op.drop_column("sites", "normalized_name_en", schema="atlas")
    op.drop_column("sites", "normalized_name_ar", schema="atlas")
    op.execute("DROP FUNCTION IF EXISTS atlas.normalize_arabic_search(text)")
