from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_database_engine, session_factory
from app.models import MediaReviewItem


def import_review_csv(session: Session, path: Path) -> dict[str, int]:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    before = int(session.scalar(select(func.count()).select_from(MediaReviewItem)) or 0)
    for row in rows:
        values = {
            "feature_id": row["feature_id"],
            "site_name": row.get("site_name") or None,
            "original_url": row["original_url"],
            "normalized_url": row.get("normalized_url") or row["original_url"],
            "domain": row.get("domain") or "",
            "source_type": row.get("status") or "unavailable",
            "review_status": row.get("review_status") or "pending_review",
            "rights_status": row.get("rights_status") or "unknown",
            "download_status": "not_requested",
        }
        session.execute(
            insert(MediaReviewItem)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["feature_id", "original_url"])
        )
    session.flush()
    inserted = int(session.scalar(select(func.count()).select_from(MediaReviewItem)) or 0) - before
    return {"read": len(rows), "inserted": inserted, "duplicates": len(rows) - inserted}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    engine = create_database_engine(get_settings().database_url)
    with session_factory(engine).begin() as session:
        result = import_review_csv(session, args.input)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
