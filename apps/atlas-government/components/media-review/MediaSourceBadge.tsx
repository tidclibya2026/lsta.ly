import { Badge } from "@/components/ui/Badge";export function MediaSourceBadge({source}:{source:string}){return <Badge tone={source.includes("google")?"warning":"neutral"}>{source}</Badge>}
