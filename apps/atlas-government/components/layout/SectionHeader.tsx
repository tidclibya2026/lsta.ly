import type { ReactNode } from "react";
export function SectionHeader({ eyebrow, title, actions }: { eyebrow?: string; title: string; actions?: ReactNode }) { return <header className="dsSectionHeader"><div>{eyebrow && <span>{eyebrow}</span>}<h2>{title}</h2></div>{actions}</header>; }
