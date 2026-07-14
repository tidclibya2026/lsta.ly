import type { ReactNode } from "react";
export function EmptyState({ title = "لا توجد بيانات", description, action }: { title?: string; description?: string; action?: ReactNode }) { return <section className="dsState" aria-label={title}><span aria-hidden="true">◇</span><h3>{title}</h3>{description && <p>{description}</p>}{action}</section>; }
