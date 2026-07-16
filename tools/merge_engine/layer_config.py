"""Configuration loader for reusable national layer intake."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED={"layer_code","entity_type","excel_sheet","excel_id_field","name_ar_field","municipality_field","category_field","merge_weights","distance_thresholds","required_fields","review_rules"}
def load_layer_config(path:Path)->dict[str,Any]:
    data=yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,dict):
        raise ValueError("Layer config must be a YAML object")
    missing=REQUIRED-set(data)
    if missing:
        raise ValueError(f"Layer config is missing: {', '.join(sorted(missing))}")
    return data
