import type { ReactNode } from "react";
import { isStaticDemo } from "@/lib/deployment-path";
import { Sidebar } from "./Sidebar";

export function GovernmentShell({ children, active = "لوحة الوزير" }: { children: ReactNode; active?: string }) {
  return <main className="shell"><Sidebar active={active} /><section className="workspace">{isStaticDemo() && <div className="publicDemoBanner" role="status">نسخة Government Alpha للعرض العام — الخدمات التشغيلية وقاعدة البيانات تعمل داخل البيئة الحكومية الداخلية.</div>}{children}</section></main>;
}
