#!/usr/bin/env python3
"""Generate municipality assignment candidates for an approved staging batch.

The tool is review-first: it proposes spatial matches, exports a CSV review list,
and never accepts or publishes a municipality automatically.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg


def create_run(
    conn: psycopg.Connection[Any],
    batch_id: UUID,
    boundary_source: str,
    boundary_version: str,
    executed_by: str,
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO gis.municipality_assignment_runs
          (batch_id, boundary_source, boundary_version, executed_by)
        VALUES (%s, %s, %s, %s)
        RETURNING run_id
        """,
        (batch_id, boundary_source, boundary_version, executed_by),
    ).fetchone()
    if row is None:
        raise RuntimeError("تعذر إنشاء سجل تشغيل الإسناد المكاني")
    return row[0]


def generate_candidates(conn: psycopg.Connection[Any], run_id: UUID, batch_id: UUID) -> None:
    conn.execute(
        """
        INSERT INTO gis.municipality_assignment_candidates (
          run_id, staging_id, municipality_id, assignment_method,
          distance_m, confidence, is_primary
        )
        SELECT %s, n.staging_id, a.administrative_unit_id,
               'contains', 0, 100, true
        FROM staging.normalized_sites n
        JOIN staging.tourism_sites_raw r ON r.staging_id = n.staging_id
        JOIN core.administrative_units a
          ON a.unit_type = 'municipality'
         AND a.geom IS NOT NULL
         AND n.geom IS NOT NULL
         AND ST_Covers(a.geom, n.geom)
        WHERE r.batch_id = %s
          AND NULLIF(BTRIM(r.municipality_raw), '') IS NULL
        ON CONFLICT DO NOTHING
        """,
        (run_id, batch_id),
    )

    conn.execute(
        """
        WITH ambiguous AS (
          SELECT staging_id
          FROM gis.municipality_assignment_candidates
          WHERE run_id = %s AND assignment_method = 'contains'
          GROUP BY staging_id HAVING COUNT(*) > 1
        )
        UPDATE gis.municipality_assignment_candidates c
        SET confidence = 70, is_primary = false,
            review_note = 'تداخل أو حد إداري؛ تتطلب مراجعة GIS.'
        FROM ambiguous a
        WHERE c.run_id = %s AND c.staging_id = a.staging_id
        """,
        (run_id, run_id),
    )

    conn.execute(
        """
        INSERT INTO gis.municipality_assignment_candidates (
          run_id, staging_id, municipality_id, assignment_method,
          distance_m, confidence, is_primary
        )
        SELECT %s, n.staging_id, nearest.administrative_unit_id, 'nearest',
               nearest.distance_m,
               CASE WHEN nearest.distance_m <= 1000 THEN 85
                    WHEN nearest.distance_m <= 5000 THEN 65 ELSE 45 END,
               true
        FROM staging.normalized_sites n
        JOIN staging.tourism_sites_raw r ON r.staging_id = n.staging_id
        CROSS JOIN LATERAL (
          SELECT a.administrative_unit_id,
                 ST_Distance(a.geom::geography, n.geom::geography) distance_m
          FROM core.administrative_units a
          WHERE a.unit_type = 'municipality' AND a.geom IS NOT NULL
          ORDER BY a.geom <-> n.geom LIMIT 1
        ) nearest
        WHERE r.batch_id = %s
          AND n.geom IS NOT NULL
          AND NULLIF(BTRIM(r.municipality_raw), '') IS NULL
          AND nearest.distance_m <= 10000
          AND NOT EXISTS (
            SELECT 1 FROM gis.municipality_assignment_candidates c
            WHERE c.run_id = %s AND c.staging_id = n.staging_id
          )
        ON CONFLICT DO NOTHING
        """,
        (run_id, batch_id, run_id),
    )

    conn.execute(
        "UPDATE gis.municipality_assignment_runs SET status = 'completed' WHERE run_id = %s",
        (run_id,),
    )


def export_review(conn: psycopg.Connection[Any], run_id: UUID, output: Path) -> int:
    rows = conn.execute(
        """
        SELECT source_record_id, name_ar_raw, latitude_raw, longitude_raw,
               proposed_municipality, assignment_method, distance_m,
               confidence, review_status, review_note
        FROM gis.v_municipality_assignment_review
        WHERE run_id = %s
        ORDER BY confidence DESC, name_ar_raw
        """,
        (run_id,),
    ).fetchall()
    output.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "source_record_id", "name_ar", "latitude", "longitude",
        "proposed_municipality", "assignment_method", "distance_m",
        "confidence", "review_status", "review_note",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="اقتراح البلديات مكانيًا لدفعة Staging")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--batch-id", required=True, type=UUID)
    parser.add_argument("--boundary-source", required=True)
    parser.add_argument("--boundary-version", required=True)
    parser.add_argument("--executed-by", default="TIDC GIS Team")
    parser.add_argument("--output", type=Path, default=Path("reports/generated/municipality_review.csv"))
    args = parser.parse_args()

    with psycopg.connect(args.database_url) as conn, conn.transaction():
        run_id = create_run(
            conn, args.batch_id, args.boundary_source,
            args.boundary_version, args.executed_by,
        )
        generate_candidates(conn, run_id, args.batch_id)
        count = export_review(conn, run_id, args.output)

    print(f"run_id={run_id} candidates={count} review_file={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
