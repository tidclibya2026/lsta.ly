export interface PilotReadiness{go_no_go:"go"|"no_go"|"unknown";checks:Record<string,boolean|null>;reasons:string[];evaluated_at:string}
export interface PilotCandidate{proposal_id:string;name:string;safety_score:number}
export interface PilotExecutionBatch{id:string;status:string;items:number;dry_run:Record<string,unknown>}
export interface PilotVerificationItem{national_id:string;site_id:string;proposal_id:string;geometry_valid:boolean;version_created:boolean;audit_events_count:number;quality_snapshot_created:boolean;publication_created:boolean;promotion_created:boolean;verification_status:string;issues:string[]}
export interface PilotRollbackPreview{validation:Record<string,unknown>;restore_plan:Record<string,unknown>;writes:number}
export interface PilotReport{scope:number;publication:boolean;promotion:boolean;visit_libya:boolean;verification:PilotVerificationItem[]}
export class PilotApiError extends Error{constructor(message:string,public status?:number){super(message)}}
export type PilotSelection=PilotCandidate[];export type PilotSelectionResult=PilotSelection;export type PilotReviewStage="technical"|"gis"|"data"|"final";export interface PilotReviewStatus{stages:Record<PilotReviewStage,string>};export type PilotDryRunResult=Record<string,unknown>;export interface PilotAuthorization{status:string};export type PilotExecutionProgress=PilotExecutionBatch;export interface PilotVerificationSummary{passed:number;failed:number};
