import { Card } from "../ui/Card";
export function StatCard({ label, value, note, status = "neutral" }: { label: string; value: string; note?: string; status?: "positive" | "warning" | "neutral" }) { return <Card className={`dsStatCard ${status}`}><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</Card>; }
