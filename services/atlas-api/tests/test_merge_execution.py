from types import SimpleNamespace

from app.services.merge_execution_eligibility_service import validate_latest_decision
from app.services.merge_field_policy_service import apply_plan, build_field_merge_plan
from app.services.merge_rollback_service import preview_rollback


def test_field_policy_keeps_registry_value_when_source_is_empty():
    plan = build_field_merge_plan({"name_ar": "معتمد"}, {"name_ar": ""}, {})
    assert plan[0]["action"] == "keep"
    assert apply_plan({"name_ar": "معتمد"}, plan)["name_ar"] == "معتمد"


def test_geometry_change_requires_explicit_confirmation():
    plan = build_field_merge_plan({"geometry": "old"}, {"geometry": "new"}, {})
    assert plan[0]["source"] == "kml"
    assert plan[0]["requires_confirmation"] is True


def test_pending_proposal_is_not_approved():
    proposal = SimpleNamespace(decisions=[])
    decision, approved = validate_latest_decision(proposal)
    assert decision is None
    assert approved is False


def test_approved_decision_requires_authorized_role():
    proposal = SimpleNamespace(decisions=[SimpleNamespace(decision="approved_merge", reviewer_role="reviewer")])
    assert validate_latest_decision(proposal)[1] is False


def test_rollback_preview_never_writes():
    item = SimpleNamespace(target_site_id=None, pre_merge_snapshot=None, execution_status="completed")
    result = preview_rollback(item)
    assert result["writes"] == 0
    assert result["validation"]["valid"] is False
