import type { ReactNode } from "react";
export interface DescriptionItem { label: string; value: ReactNode }
export function DescriptionList({ items, ariaLabel = "التفاصيل" }: { items: DescriptionItem[]; ariaLabel?: string }) { return <dl className="dsDescriptionList" aria-label={ariaLabel}>{items.map((item, index) => <div key={`${item.label}-${index}`}><dt>{item.label}</dt><dd>{item.value || "—"}</dd></div>)}</dl>; }
