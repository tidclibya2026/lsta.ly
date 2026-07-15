from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DataQualityResult, DataQualityRule


def list_rules(session: Session):
    return list(session.scalars(select(DataQualityRule).order_by(DataQualityRule.rule_code)))


def create_rule(session: Session, data: dict[str, Any]):
    rule = DataQualityRule(**data)
    session.add(rule)
    session.flush()
    return rule


def update_rule(session: Session, code: str, data: dict[str, Any]):
    rule = session.scalar(select(DataQualityRule).where(DataQualityRule.rule_code == code))
    if not rule:
        raise LookupError(code)
    for k, v in data.items():
        if hasattr(rule, k) and k not in {"id", "rule_code"}:
            setattr(rule, k, v)
    session.flush()
    return rule


def execute_rule(
    session: Session, rule: DataQualityRule, entity_type: str, entity_id: str, value: Any, evaluated_by: str = "system"
) -> DataQualityResult:
    op = rule.rule_expression.get("operator")
    passed = (value is not None and value != "") if op in {"not_empty", "not_null"} else True
    status = "passed" if passed else ("warning" if rule.severity in {"info", "warning"} else "failed")
    result = DataQualityResult(
        rule_id=rule.id,
        entity_type=entity_type,
        entity_id=entity_id,
        status=status,
        score=100 if passed else 0,
        issue_details={} if passed else {"field": rule.target_field},
        evaluated_by=evaluated_by,
    )
    session.add(result)
    session.flush()
    return result


def execute_rules_for_entity(
    session: Session, entity_type: str, entity_id: str, values: dict[str, Any], evaluated_by: str = "system"
):
    return [
        execute_rule(session, r, entity_type, entity_id, values.get(r.target_field or ""), evaluated_by)
        for r in list_rules(session)
        if r.target_entity == entity_type
    ]


def get_quality_results(session: Session, entity_type: str | None = None):
    stmt = select(DataQualityResult)
    if entity_type:
        stmt = stmt.where(DataQualityResult.entity_type == entity_type)
    return list(session.scalars(stmt.order_by(DataQualityResult.evaluated_at.desc())))


def get_quality_summary(session: Session):
    return dict(
        session.execute(select(DataQualityResult.status, func.count()).group_by(DataQualityResult.status)).all()
    )


def calculate_dataset_quality_score(session: Session, entity_type: str) -> float:
    value = session.scalar(
        select(func.avg(DataQualityResult.score)).where(DataQualityResult.entity_type == entity_type)
    )
    return round(float(value or 0), 2)
