from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_database_engine, session_factory
from app.models import FeatureReview, ImportFeature
from app.models.tables import REVIEW_STAGES

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "review" / "old_tripoli_review_sample.csv"


def prepare_review_sample(session: Session, *, limit: int = 10, output: Path = DEFAULT_OUTPUT) -> list[ImportFeature]:
    features = list(
        session.scalars(
            select(ImportFeature)
            .where(ImportFeature.geometry_type == "Point", ImportFeature.missing_name.is_(False))
            .order_by(ImportFeature.source_feature_id)
            .limit(limit)
        )
    )
    for feature in features:
        existing = set(
            session.scalars(select(FeatureReview.review_stage).where(FeatureReview.import_feature_id == feature.id))
        )
        for stage in REVIEW_STAGES:
            if stage not in existing:
                session.add(
                    FeatureReview(
                        import_feature_id=feature.id, review_stage=stage, decision="pending", reviewer_role="unassigned"
                    )
                )
    session.flush()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        fields = [
            "id",
            "source_feature_id",
            "name_ar",
            "geometry_type",
            "folder_name",
            "review_status",
            "promotion_eligible",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for feature in features:
            writer.writerow(
                {
                    "id": feature.id,
                    "source_feature_id": feature.source_feature_id,
                    "name_ar": feature.name_ar,
                    "geometry_type": feature.geometry_type,
                    "folder_name": feature.properties.get("folder_name", ""),
                    "review_status": feature.review_status,
                    "promotion_eligible": feature.promotion_eligible,
                }
            )
    return features


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="تجهيز عينة مراجعة المدينة القديمة دون اعتماد تلقائي")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    factory = session_factory(create_database_engine(get_settings().database_url))
    with factory.begin() as session:
        features = prepare_review_sample(session, limit=args.limit, output=args.output)
    print(f"تم تجهيز {len(features)} سجلًا للمراجعة دون اعتماد: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
