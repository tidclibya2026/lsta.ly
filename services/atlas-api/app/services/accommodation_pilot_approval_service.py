from app.models import MergeDecision

STAGES=(("technical","pilot_technical_reviewer"),("gis","pilot_gis_reviewer"),("data","pilot_data_reviewer"),("final","pilot_final_authorizer"))
def get_pilot_approval_status(proposal): return {x:next((d.decision for d in proposal.decisions if d.review_stage==x),"pending") for x,_ in STAGES}
def validate_review_sequence(proposal,stage):
    names=[x for x,_ in STAGES];idx=names.index(stage);state=get_pilot_approval_status(proposal)
    if any(state[x] not in {"accepted","approved_merge"} for x in names[:idx]):raise ValueError("review stages cannot be skipped")
def submit_pilot_stage_decision(session,proposal,stage,reference):
    validate_review_sequence(proposal,stage);role=dict(STAGES)[stage];decision="approved_merge" if stage=="final" else "accepted"
    row=MergeDecision(proposal_id=proposal.id,decision=decision,review_stage=stage,reviewer_role=role,reviewer_reference=reference,decision_reason="controlled five-hotel pilot",decision_metadata={"pilot":True,"resolved_high_conflicts":False});proposal.decisions.append(row);session.flush()
    if stage=="final":proposal.review_status="approved_merge"
    return row
def create_pilot_review_plan(proposal):return [{"stage":s,"role":r}for s,r in STAGES]
def validate_separation_of_duties(proposal):return len({d.reviewer_reference for d in proposal.decisions if d.review_stage in dict(STAGES)})>=4
def finalize_pilot_approval(session,proposal):return submit_pilot_stage_decision(session,proposal,"final","pilot-final-authorizer")
