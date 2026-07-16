from pathlib import Path

from tools.merge_engine.layer_config import load_layer_config
from tools.merge_engine.models import MatchCandidate
from tools.merge_engine.engine import _enforce_one_to_one


def test_all_layer_configs_are_valid() -> None:
    for name in ("hotels", "resorts", "restaurants", "cafes"):
        config = load_layer_config(Path("config/layers") / f"{name}.yml")
        assert config["review_rules"]["automatic_merge"] is False
        assert config["review_rules"]["one_to_one"] is True


def test_one_to_one_matching_remains_deterministic() -> None:
    candidates = [MatchCandidate("E1", "K1", "A", "A", 100, 0, True, True, 100, "ready_merge", []), MatchCandidate("E1", "K2", "A", "A", 90, 10, True, True, 90, "needs_review", [])]
    accepted, rejected = _enforce_one_to_one(candidates)
    assert len(accepted) == 1 and accepted[0].kml_id == "K1"
    assert len(rejected) == 1
