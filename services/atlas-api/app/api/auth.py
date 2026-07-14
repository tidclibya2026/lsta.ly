from typing import Annotated

from fastapi import Header, HTTPException

ALLOWED_REVIEWER_ROLES = {
    "system_admin",
    "data_manager",
    "editor",
    "reviewer",
    "gis_specialist",
    "viewer",
    "decision_maker",
}


def get_reviewer_role(x_lsta_reviewer_role: Annotated[str | None, Header()] = None) -> str:
    role = x_lsta_reviewer_role or "viewer"
    if role not in ALLOWED_REVIEWER_ROLES:
        raise HTTPException(status_code=400, detail="دور المراجع غير صالح")
    return role


def ensure_review_permission(role: str, stage: str, decision: str) -> None:
    if role == "viewer":
        raise HTTPException(status_code=403, detail="المشاهد لا يملك صلاحية إرسال قرارات")
    if decision == "accepted" and stage == "gis" and role not in {"gis_specialist", "system_admin"}:
        raise HTTPException(status_code=403, detail="اعتماد GIS مخصص لاختصاصي GIS أو مدير النظام")
    if decision == "accepted" and stage == "final" and role not in {"decision_maker", "data_manager", "system_admin"}:
        raise HTTPException(status_code=403, detail="الاعتماد النهائي غير مسموح لهذا الدور")


def ensure_promotion_permission(role: str) -> None:
    if role not in {"system_admin", "data_manager", "decision_maker"}:
        raise HTTPException(status_code=403, detail="لا توجد صلاحية لترقية السجل الوطني")


def ensure_registry_edit(role: str) -> None:
    if role not in {"system_admin", "data_manager", "editor", "reviewer"}:
        raise HTTPException(status_code=403, detail="لا توجد صلاحية لتعديل السجل")


def ensure_registry_admin(role: str) -> None:
    if role not in {"system_admin", "data_manager"}:
        raise HTTPException(status_code=403, detail="الأرشفة والاستعادة مخصصة لإدارة البيانات")
