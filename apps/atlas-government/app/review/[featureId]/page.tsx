"use client";

import maplibregl from "maplibre-gl";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { MetricBar } from "@/components/data-display/MetricBar";
import { ImageGallery } from "@/components/data-display/ImageGallery";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { Select } from "@/components/forms/Select";
import { TextArea } from "@/components/forms/TextArea";
import { GovernmentShell } from "@/components/layout/GovernmentShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { Tabs } from "@/components/ui/Tabs";
import { REVIEWER_ROLE, reviewApi } from "@/lib/api/review";
import type { ReviewDecision, ReviewFeatureDetails, ReviewStage } from "@/lib/api/types";
import { isStaticDemo } from "@/lib/deployment-path";

function SingleFeatureMap({ feature }: { feature: ReviewFeatureDetails }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current || !feature.geometry) return;
    const geometry = feature.geometry;
    const map = new maplibregl.Map({ container: container.current, center: [13.18, 32.89], zoom: 14, style: { version: 8, sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap" } }, layers: [{ id: "osm", type: "raster", source: "osm" }] } });
    map.addControl(new maplibregl.NavigationControl(), "top-left");
    map.on("load", () => {
      map.addSource("review-feature", { type: "geojson", data: { type: "Feature", properties: {}, geometry } as never });
      if (feature.geometry_type === "Point") map.addLayer({ id: "review-point", type: "circle", source: "review-feature", paint: { "circle-radius": 9, "circle-color": "#b08a3c", "circle-stroke-color": "#092b49", "circle-stroke-width": 3 } });
      else if (feature.geometry_type === "LineString") map.addLayer({ id: "review-line", type: "line", source: "review-feature", paint: { "line-color": "#b08a3c", "line-width": 5 } });
      else map.addLayer({ id: "review-area", type: "fill", source: "review-feature", paint: { "fill-color": "#b08a3c", "fill-opacity": 0.3, "fill-outline-color": "#092b49" } });
      const points: [number, number][] = [];
      const collect = (value: unknown) => { if (Array.isArray(value) && typeof value[0] === "number" && typeof value[1] === "number") points.push([value[0], value[1]]); else if (Array.isArray(value)) value.forEach(collect); };
      collect(geometry.coordinates);
      if (points.length === 1) map.flyTo({ center: points[0], zoom: 17 });
      else if (points.length > 1) { const bounds = points.reduce((box, point) => box.extend(point), new maplibregl.LngLatBounds(points[0], points[0])); map.fitBounds(bounds, { padding: 60, maxZoom: 17 }); }
    });
    return () => map.remove();
  }, [feature]);
  return <div className="reviewFeatureMap" ref={container} aria-label="خريطة السجل المحدد" />;
}

export default function ReviewFeaturePage() {
  const { featureId } = useParams<{ featureId: string }>();
  const [feature, setFeature] = useState<ReviewFeatureDetails | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<ReviewDecision | null>(null);
  const [stage, setStage] = useState<ReviewStage>("technical");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const load = useCallback(async () => { if (isStaticDemo()) { setLoading(false); return; } setLoading(true); setError(""); try { setFeature(await reviewApi.feature(featureId)); } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تحميل السجل"); } finally { setLoading(false); } }, [featureId]);
  useEffect(() => { void load(); }, [load]);
  const submit = async () => { if (!dialog) return; setSaving(true); try { await reviewApi.review(featureId, { review_stage: stage, decision: dialog, notes, reviewer_role: REVIEWER_ROLE }); setDialog(null); setNotes(""); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر حفظ القرار"); } finally { setSaving(false); } };
  const promote = async () => { setSaving(true); try { await reviewApi.promote(featureId); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر ترقية السجل"); } finally { setSaving(false); } };
  if (isStaticDemo()) return <GovernmentShell active="المراجعة الوطنية"><div className="reviewPage"><PageHeader title="بوابة المراجعة الوطنية" /><Card><h2>بوابة المراجعة التشغيلية متاحة داخل البيئة الحكومية الداخلية.</h2><p>لا تُعرض تفاصيل المراجعة أو التدقيق في النسخة العامة.</p></Card></div></GovernmentShell>;
  if (loading) return <GovernmentShell active="المراجعة الوطنية"><div className="reviewLoading"><LoadingSpinner /></div></GovernmentShell>;
  if (error && !feature) return <GovernmentShell active="المراجعة الوطنية"><ErrorState description={error} action={<Button onClick={() => void load()}>إعادة المحاولة</Button>} /></GovernmentShell>;
  if (!feature) return null;
  const overview = <div className="reviewDetailGrid"><Card><h3>البيانات الأساسية</h3><dl className="reviewDl"><dt>المعرّف</dt><dd>{feature.source_feature_id}</dd><dt>الاسم</dt><dd>{feature.name_ar || "بلا اسم"}</dd><dt>المجلد</dt><dd>{feature.folder_name || "—"}</dd><dt>نوع الهندسة</dt><dd>{feature.geometry_type}</dd><dt>حالة المراجعة</dt><dd>{feature.review_status}</dd></dl></Card><Card><h3>جودة البيانات</h3><strong className="qualityScore">{feature.quality.quality_score}/100</strong>{Object.entries(feature.quality.quality_breakdown).map(([key, item]) => <MetricBar key={key} label={key} value={item.earned} max={item.weight} displayValue={`${item.earned}/${item.weight}`} />)}</Card><Card className="reviewWide"><h3>الوصف المنظف</h3><p className="reviewDescription">{feature.description_text || "لا يوجد وصف"}</p><h3>HTML الأصلي</h3><pre className="reviewCode">{feature.description_html || "لا يوجد"}</pre></Card></div>;
  const gis = <div><SingleFeatureMap feature={feature} /><Card><h3>فحوص الهندسة</h3>{Object.entries(feature.eligibility.checks).map(([key, value]) => <Badge key={key} tone={value ? "success" : "danger"}>{key}: {value ? "نعم" : "لا"}</Badge>)}</Card></div>;
  const images = <div className="reviewImages">{feature.images.length ? <ImageGallery images={feature.images.map(original_url => ({ original_url, rights_status: "unknown" }))} alt={feature.name_ar || "صورة السجل"} /> : <p>لا توجد صور.</p>}</div>;
  const metadata = <div className="reviewDetailGrid"><Card><h3>ExtendedData</h3><pre className="reviewCode">{JSON.stringify(feature.extended_data, null, 2)}</pre></Card><Card><h3>Validation issues</h3><pre className="reviewCode">{JSON.stringify(feature.validation_issues, null, 2)}</pre></Card><Card className="reviewWide"><h3>Properties</h3><pre className="reviewCode">{JSON.stringify(feature.properties, null, 2)}</pre></Card></div>;
  const reviews = <div className="reviewTimeline">{(["technical", "gis", "data", "final"] as ReviewStage[]).map((item) => { const record = feature.reviews.find((review) => review.review_stage === item); return <Card key={item}><h3>{item}</h3><Badge tone={record?.decision === "accepted" ? "success" : record?.decision === "rejected" ? "danger" : "warning"}>{record?.decision || "pending"}</Badge><p>{record?.notes || "لا توجد ملاحظات"}</p><small>{record?.reviewer_role || "لم يراجع"}</small></Card>; })}</div>;
  const audit = <div className="reviewTimeline">{feature.audit_timeline.length ? feature.audit_timeline.map((item) => <Card key={item.id}><h3>{item.action}</h3><time>{new Date(item.created_at).toLocaleString("ar-LY")}</time><pre className="reviewCode">{JSON.stringify(item.details, null, 2)}</pre></Card>) : <p>لا توجد أحداث تدقيق.</p>}</div>;
  return <GovernmentShell active="المراجعة الوطنية"><div className="reviewPage"><PageHeader eyebrow={feature.source_feature_id} title={feature.name_ar || "عنصر يحتاج تسمية"} actions={<div className="reviewActions"><Button variant="secondary" onClick={() => setDialog("accepted")}>اعتماد</Button><Button variant="danger" onClick={() => setDialog("rejected")}>رفض</Button><Button variant="secondary" onClick={() => setDialog("needs_correction")}>يحتاج تصحيح</Button>{feature.promotion_eligible && !feature.promotion_record && <Button loading={saving} onClick={() => void promote()}>Promote</Button>}</div>} />{error && <p className="reviewInlineError" role="alert">{error}</p>}<Tabs ariaLabel="تفاصيل سجل المراجعة" items={[{ id: "overview", label: "نظرة عامة", content: overview }, { id: "gis", label: "GIS", content: gis }, { id: "images", label: "الصور", content: images }, { id: "metadata", label: "البيانات الوصفية", content: metadata }, { id: "reviews", label: "المراجعات", content: reviews }, { id: "audit", label: "التدقيق", content: audit }]} />
    <Dialog open={dialog !== null} title="تأكيد قرار المراجعة" onClose={() => setDialog(null)}><div className="reviewDialog"><Select label="مرحلة المراجعة" value={stage} onChange={(event) => setStage(event.target.value as ReviewStage)} options={[{ value: "technical", label: "تقنية" }, { value: "gis", label: "GIS" }, { value: "data", label: "بيانات" }, { value: "final", label: "نهائية" }]} /><TextArea label="ملاحظات القرار" value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} /><p>سيُسجل القرار باسم الدور: <strong>{REVIEWER_ROLE}</strong></p><div className="reviewActions"><Button loading={saving} onClick={() => void submit()}>تأكيد</Button><Button variant="ghost" onClick={() => setDialog(null)}>إلغاء</Button></div></div></Dialog>
  </div></GovernmentShell>;
}
