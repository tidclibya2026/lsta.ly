import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
export function GovernmentShell({ children, active = "لوحة الوزير" }: { children: ReactNode; active?: string }) { return <main className="shell"><Sidebar active={active} /><section className="workspace">{children}</section></main>; }
