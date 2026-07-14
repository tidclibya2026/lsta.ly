import type { ReactNode } from "react";
import { PageHeader } from "./PageHeader";
export function Topbar({ title, eyebrow, actions }: { title: string; eyebrow?: string; actions?: ReactNode }) { return <PageHeader title={title} eyebrow={eyebrow} actions={actions} />; }
