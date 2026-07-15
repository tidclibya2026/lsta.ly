import type { LineageEdge } from "@/lib/api/metadata-types";export function LineageTimeline({items}:{items:LineageEdge[]}){return <ol>{items.map(e=><li key={e.id}>{e.type} — {e.status}</li>)}</ol>}
