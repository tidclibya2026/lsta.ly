import { Badge } from "../ui/Badge";
export function StatusBadge({ status }: { status: "verified" | "under_review" | "unverified" | "draft" }) { const config = { verified: ["معتمد", "success"], under_review: ["قيد المراجعة", "warning"], unverified: ["غير متحقق", "danger"], draft: ["مسودة", "neutral"] } as const; const [label, tone] = config[status]; return <Badge tone={tone}>{label}</Badge>; }
