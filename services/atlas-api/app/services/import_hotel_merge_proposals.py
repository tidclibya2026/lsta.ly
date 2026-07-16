from __future__ import annotations

import json
import os
from pathlib import Path

from app.api.deps import SessionLocal
from app.services.merge_proposal_import_service import import_merge_proposals


def project_root() -> Path:
    return Path(os.getenv("LSTA_PROJECT_ROOT", Path(__file__).resolve().parents[4])).resolve()


def main() -> None:
    root = project_root()
    with SessionLocal() as session:
        result = import_merge_proposals(session, excel_path=root / "data/raw/excel/أطلس_ليبيا_السياحي_2026_طبقة_الفنادق.xlsx", kml_path=root / "data/raw/kml/hotels_LY.kml", summary_path=root / "reports/merge/hotels/hotels_kml_excel_match_summary.json", preview_path=root / "reports/merge/hotels/hotels_merge_preview.json", entity_type="hotels", created_by="government_alpha_import")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
