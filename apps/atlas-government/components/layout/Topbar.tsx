"use client";

import type { ReactNode } from "react";
import { GlobalSearchBox } from "@/components/search/GlobalSearchBox";
import { withBasePath } from "@/lib/deployment-path";
import { PageHeader } from "./PageHeader";

export function Topbar({ title, eyebrow, actions }: { title: string; eyebrow?: string; actions?: ReactNode }) {
  return <div className="governmentTopbar"><PageHeader title={title} eyebrow={eyebrow} actions={actions} /><GlobalSearchBox onSubmit={(query) => { window.location.href = withBasePath(`/search/?q=${encodeURIComponent(query)}`); }} /></div>;
}
