"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { DataTable, type DataColumn } from "@/components/data-display/DataTable";
import { StatCard } from "@/components/data-display/StatCard";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { SearchInput } from "@/components/forms/SearchInput";
import { Select } from "@/components/forms/Select";
import { GovernmentShell } from "@/components/layout/GovernmentShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { registryApi } from "@/lib/api/registry";
import type { RegistryPage, RegistrySite, RegistrySummary } from "@/lib/api/registry-types";

const LIMIT = 25;
export default function SitesPage() {
  const [summary, setSummary] = useState<RegistrySummary | null>(null);
  const [page, setPage] = useState<RegistryPage>({ items: [], total: 0, limit: LIMIT, offset: 0 });
  const [filters, setFilters] = useState({ search: "", verification_status: "", publication_status: "", completeness_min: 0 });
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => { setLoading(true); setError(""); try { const [metrics, sites] = await Promise.all([registryApi.summary(), registryApi.sites({ ...filters, limit: LIMIT, offset })]); setSummary(metrics); setPage(sites); } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تحميل السجل"); } finally { setLoading(false); } }, [filters, offset]);
  useEffect(() => { void load(); }, [load]);
  const columns: DataColumn<RegistrySite>[] = [
    { key: "name", header: "الموقع الوطني", render: (item) => <div><strong>{item.name_ar}</strong><small className="reviewMuted">{item.name_en || item.national_id}</small></div> },
    { key: "verification", header: "التحقق", render: (item) => <Badge tone={item.verification_status === "approved" ? "success" : "neutral"}>{item.verification_status}</Badge> },
    { key: "publication", header: "النشر", render: (item) => <Badge tone={item.publication_status === "internal" ? "warning" : "success"}>{item.publication_status}</Badge> },
    { key: "score", header: "الاكتمال", render: (item) => <strong>{item.profile_completeness_score}/100</strong> },
    { key: "open", header: "", render: (item) => <Link className="reviewOpen" href={`/sites/${item.national_id}`}>فتح ملف الموقع</Link> },
  ];
  return <GovernmentShell active="السجل الوطني"><div className="reviewPage"><PageHeader eyebrow="National Asset Registry" title="السجل الوطني للأصول السياحية" />
    {summary && <section className="registryStats"><StatCard label="إجمالي المواقع" value={String(summary.total_sites)} /><StatCard label="المعتمد" value={String(summary.approved)} status="positive" /><StatCard label="الداخلي" value={String(summary.internal)} /><StatCard label="المؤرشف" value={String(summary.archived)} status="warning" /><StatCard label="متوسط الاكتمال" value={`${summary.average_completeness}%`} /></section>}
    <section className="reviewFilters"><SearchInput label="البحث" value={filters.search} onChange={(event) => { setOffset(0); setFilters({ ...filters, search: event.target.value }); }} /><Select label="حالة التحقق" value={filters.verification_status} onChange={(event) => setFilters({ ...filters, verification_status: event.target.value })} options={[{ value: "", label: "كل الحالات" }, { value: "approved", label: "معتمد" }, { value: "draft", label: "مسودة" }, { value: "archived", label: "مؤرشف" }]} /><Select label="حالة النشر" value={filters.publication_status} onChange={(event) => setFilters({ ...filters, publication_status: event.target.value })} options={[{ value: "", label: "كل حالات النشر" }, { value: "internal", label: "داخلي" }, { value: "approved_public", label: "معتمد عام" }]} /><Select label="حد الاكتمال" value={String(filters.completeness_min)} onChange={(event) => setFilters({ ...filters, completeness_min: Number(event.target.value) })} options={[{ value: "0", label: "كل الدرجات" }, { value: "50", label: "50% فأكثر" }, { value: "75", label: "75% فأكثر" }]} /></section>
    {loading ? <div className="reviewLoading"><LoadingSpinner /></div> : error ? <ErrorState description={error} action={<Button onClick={() => void load()}>إعادة المحاولة</Button>} /> : page.items.length ? <><DataTable columns={columns} rows={page.items} rowKey={(item) => item.id} /><footer className="reviewPagination"><span>{offset + 1}–{Math.min(offset + LIMIT, page.total)} من {page.total}</span><div><Button variant="secondary" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>السابق</Button><Button variant="secondary" disabled={offset + LIMIT >= page.total} onClick={() => setOffset(offset + LIMIT)}>التالي</Button></div></footer></> : <EmptyState title="لا توجد مواقع مطابقة" />}
  </div></GovernmentShell>;
}
