import type { ReactNode } from "react";
export function PageHeader({ eyebrow, title, actions }: { eyebrow?: string; title: string; actions?: ReactNode }) { return <header className="dsPageHeader"><div>{eyebrow && <p>{eyebrow}</p>}<h1>{title}</h1></div>{actions && <div className="dsPageActions">{actions}</div>}</header>; }
