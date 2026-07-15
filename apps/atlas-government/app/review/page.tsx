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
import { Card } from "@/components/ui/Card";
import { reviewApi } from "@/lib/api/review";
import type { PaginatedFeatures, ReviewFeature, ReviewSummary } from "@/lib/api/types";
import { isStaticDemo } from "@/lib/deployment-path";

const LIMIT = 25;
const statusLabel: Record<string, string> = { pending_review: "قيد المراجعة", accepted: "مقبول", rejected: "مرفوض", needs_correction: "يحتاج تصحيح" };

export default function ReviewPage() {
  const [summary, setSummary] = useState<ReviewSummary | null>(null);
  const [data, setData] = useState<PaginatedFeatures>({ items: [], total: 0, limit: LIMIT, offset: 0 });
  const [filters, setFilters] = useState({ search: "", geometry_type: "", review_status: "", review_stage: "" });
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => { if (isStaticDemo()) { setLoading(false); return; } setLoading(true); setError(""); try { const [metrics, features] = await Promise.all([reviewApi.summary(), reviewApi.features({ ...filters, limit: LIMIT, offset })]); setSummary(metrics); setData(features); } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تحميل البيانات"); } finally { setLoading(false); } }, [filters, offset]);
  useEffect(() => { void load(); }, [load]);

  if (isStaticDemo()) return <GovernmentShell active="المراجعة الوطنية"><div className="reviewPage"><PageHeader eyebrow="Government Alpha" title="بوابة المراجعة الوطنية" /><Card><h2>بوابة المراجعة التشغيلية متاحة داخل البيئة الحكومية الداخلية.</h2><p>لا تتضمن نسخة العرض العام سجلات Staging أو قرارات المراجعين أو إجراءات الاعتماد والترقية.</p></Card></div></GovernmentShell>;
  const columns: DataColumn<ReviewFeature>[] = [
    { key: "name", header: "السجل", render: (row) => <div><strong>{row.name_ar || "عنصر بلا اسم"}</strong><small className="reviewMuted">{row.source_feature_id}</small></div> },
    { key: "geometry", header: "الهندسة", render: (row) => row.geometry_type },
    { key: "status", header: "الحالة", render: (row) => <Badge tone={row.review_status === "accepted" ? "success" : row.review_status === "rejected" ? "danger" : "warning"}>{statusLabel[row.review_status] || row.review_status}</Badge> },
    { key: "quality", header: "الجودة", render: (row) => <strong>{row.quality_score}/100</strong> },
    { key: "images", header: "الصور", render: (row) => row.image_count },
    { key: "eligible", header: "الترقية", render: (row) => <Badge tone={row.promotion_eligible ? "success" : "neutral"}>{row.promotion_eligible ? "مؤهل" : "غير مؤهل"}</Badge> },
    { key: "open", header: "", render: (row) => <Link className="reviewOpen" href={`/review/${row.id}`}>فتح</Link> },
  ];
  const lastPage = offset + LIMIT >= data.total;
  return <GovernmentShell active="المراجعة الوطنية"><div className="reviewPage"><PageHeader eyebrow="Government Alpha" title="بوابة المراجعة الوطنية" />
    {summary && <section className="reviewStats" aria-label="مؤشرات المراجعة"><StatCard label="إجمالي العناصر" value={String(summary.total_features)} /><StatCard label="قيد المراجعة" value={String(summary.pending_review)} status="warning" /><StatCard label="المؤهلة للترقية" value={String(summary.eligible_for_promotion)} status="positive" /><StatCard label="تمت ترقيتها" value={String(summary.promoted)} /><StatCard label="المسماة" value={String(summary.named_features)} /><StatCard label="غير المسماة" value={String(summary.unnamed_features)} status="warning" /></section>}
    <section className="reviewFilters" aria-label="فلاتر السجلات"><SearchInput label="البحث" placeholder="الاسم أو المعرّف" value={filters.search} onChange={(event) => { setOffset(0); setFilters({ ...filters, search: event.target.value }); }} /><Select label="نوع الهندسة" value={filters.geometry_type} onChange={(event) => { setOffset(0); setFilters({ ...filters, geometry_type: event.target.value }); }} options={[{ value: "", label: "كل الهندسات" }, { value: "Point", label: "نقاط" }, { value: "LineString", label: "خطوط" }, { value: "Polygon", label: "مضلعات" }]} /><Select label="الحالة" value={filters.review_status} onChange={(event) => { setOffset(0); setFilters({ ...filters, review_status: event.target.value }); }} options={[{ value: "", label: "كل الحالات" }, { value: "pending_review", label: "قيد المراجعة" }, { value: "accepted", label: "مقبول" }, { value: "rejected", label: "مرفوض" }, { value: "needs_correction", label: "يحتاج تصحيح" }]} /><Select label="مرحلة المراجعة" value={filters.review_stage} onChange={(event) => { setOffset(0); setFilters({ ...filters, review_stage: event.target.value }); }} options={[{ value: "", label: "كل المراحل" }, { value: "technical", label: "تقنية" }, { value: "gis", label: "GIS" }, { value: "data", label: "بيانات" }, { value: "final", label: "نهائية" }]} /></section>
    {loading ? <div className="reviewLoading"><LoadingSpinner label="تحميل سجلات المراجعة" /></div> : error ? <ErrorState title="تعذر تحميل بوابة المراجعة" description={error} action={<Button onClick={() => void load()}>إعادة المحاولة</Button>} /> : data.items.length === 0 ? <EmptyState title="لا توجد سجلات مطابقة" /> : <><DataTable columns={columns} rows={data.items} rowKey={(row) => row.id} caption="سجلات المراجعة الوطنية" /><footer className="reviewPagination"><span>عرض {offset + 1}–{Math.min(offset + LIMIT, data.total)} من {data.total}</span><div><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>السابق</Button><Button variant="secondary" disabled={lastPage} onClick={() => setOffset(offset + LIMIT)}>التالي</Button></div></footer></>}
  </div></GovernmentShell>;
}
