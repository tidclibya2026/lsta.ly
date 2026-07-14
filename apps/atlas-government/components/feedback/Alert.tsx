import type { ReactNode } from "react";
export function Alert({ children, tone = "info", title }: { children: ReactNode; tone?: "info" | "success" | "warning" | "danger"; title?: string }) { return <div className={`dsAlert ${tone}`} role={tone === "danger" ? "alert" : "status"}>{title && <strong>{title}</strong>}<div>{children}</div></div>; }
