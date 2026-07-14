import type { ReactNode } from "react";
export function ErrorState({ title = "تعذر إتمام العملية", description, action }: { title?: string; description?: string; action?: ReactNode }) { return <section className="dsState error" role="alert"><span aria-hidden="true">!</span><h3>{title}</h3>{description && <p>{description}</p>}{action}</section>; }
