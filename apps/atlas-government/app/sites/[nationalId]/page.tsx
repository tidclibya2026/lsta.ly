"use client";

import maplibregl from "maplibre-gl";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { DescriptionList } from "@/components/data-display/DescriptionList";
import { ImageGallery } from "@/components/data-display/ImageGallery";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { GovernmentShell } from "@/components/layout/GovernmentShell";
import { SiteAttributesEditor, SiteAuditTimeline, SiteCompletenessPanel, SiteDocumentsPanel, SiteProfileForm, SiteProfileHeader, SiteQualityPanel, SiteRelationshipsPanel, SiteVersionTimeline } from "@/components/registry";
import { Card } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { Tabs } from "@/components/ui/Tabs";
import { REGISTRY_ROLE, registryApi } from "@/lib/api/registry";
import type { RegistryDetails, SiteAttribute, SiteDocument, SiteVersion } from "@/lib/api/registry-types";

function coordinates(geometry: GeoJSON.Geometry | null): [number, number] {
  let point: [number, number] = [13.18, 32.89];
  let found = false;
  const visit = (value: unknown) => { if (!found && Array.isArray(value) && typeof value[0] === "number" && typeof value[1] === "number") { point = [value[0], value[1]]; found = true; } else if (!found && Array.isArray(value)) value.forEach(visit); };
  if (geometry) visit(geometry.coordinates);
  return point;
}

function SiteMap({ site }: { site: RegistryDetails }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || !site.geometry) return;
    const geometry = site.geometry;
    const map = new maplibregl.Map({ container: ref.current, center: coordinates(geometry), zoom: 16, style: { version: 8, sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256 } }, layers: [{ id: "osm", type: "raster", source: "osm" }] } });
    map.addControl(new maplibregl.NavigationControl(), "top-left");
    map.on("load", () => { map.addSource("site", { type: "geojson", data: { type: "Feature", properties: {}, geometry } as never }); map.addLayer(geometry.type === "Point" ? { id: "site-point", type: "circle", source: "site", paint: { "circle-radius": 10, "circle-color": "#b08a3c", "circle-stroke-color": "#092b49", "circle-stroke-width": 3 } } : { id: "site-shape", type: "line", source: "site", paint: { "line-color": "#b08a3c", "line-width": 5 } }); });
    return () => map.remove();
  }, [site]);
  return <div className="registryMap" ref={ref} />;
}

export default function SitePage() {
  const { nationalId } = useParams<{ nationalId: string }>();
  const [site, setSite] = useState<RegistryDetails | null>(null);
  const [attributes, setAttributes] = useState<SiteAttribute[]>([]);
  const [documents, setDocuments] = useState<SiteDocument[]>([]);
  const [versions, setVersions] = useState<SiteVersion[]>([]);
  const [media, setMedia] = useState<Array<Record<string, unknown>>>([]);
  const [quality, setQuality] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const load = useCallback(async () => { setLoading(true); setError(""); try { const [details, attrs, docs, versionItems, mediaItems, qualityItems] = await Promise.all([registryApi.site(nationalId), registryApi.attributes(nationalId), registryApi.documents(nationalId), registryApi.versions(nationalId), registryApi.media(nationalId), registryApi.quality(nationalId)]); setSite(details); setAttributes(attrs); setDocuments(docs); setVersions(versionItems); setMedia(mediaItems); setQuality(qualityItems); } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تحميل ملف الموقع"); } finally { setLoading(false); } }, [nationalId]);
  useEffect(() => { void load(); }, [load]);
  if (loading) return <GovernmentShell active="السجل الوطني"><div className="reviewLoading"><LoadingSpinner /></div></GovernmentShell>;
  if (!site) return <GovernmentShell active="السجل الوطني"><ErrorState description={error} /></GovernmentShell>;
  const canEdit = ["editor", "data_manager", "system_admin"].includes(REGISTRY_ROLE);
  const images = media.map((item) => String(item.url || "")).filter(Boolean);
  const overview = <div className="reviewDetailGrid"><Card><h3>البيانات الأساسية</h3><DescriptionList items={[{ label: "المعرّف الوطني", value: site.national_id }, { label: "الاسم العربي", value: site.name_ar }, { label: "الاسم الإنجليزي", value: site.name_en }, { label: "حالة التحقق", value: site.verification_status }, { label: "حالة النشر", value: site.publication_status }]} /></Card><Card><h3>الملف السياحي</h3><p>{site.profile.short_description_ar || site.description || "لا يوجد وصف"}</p></Card><Card className="reviewWide"><SiteCompletenessPanel value={site.completeness} /></Card></div>;
  return <GovernmentShell active="السجل الوطني"><div className="reviewPage"><SiteProfileHeader site={site} canEdit={canEdit} onEdit={() => setEditing(true)} />{error && <p className="reviewInlineError">{error}</p>}<Tabs ariaLabel="ملف الموقع الوطني" items={[
    { id: "overview", label: "نظرة عامة", content: overview },
    { id: "map", label: "الخريطة", content: <div className="registryBody">{site.geometry ? <SiteMap site={site} /> : <EmptyState title="لا توجد هندسة" />}</div> },
    { id: "images", label: "الصور", content: <div className="registryBody">{images.length ? <ImageGallery images={images} alt={site.name_ar} /> : <EmptyState title="لا توجد صور" />}</div> },
    { id: "attributes", label: "الخصائص", content: <div className="registryBody"><SiteAttributesEditor items={attributes} /></div> },
    { id: "documents", label: "الوثائق", content: <div className="registryBody"><SiteDocumentsPanel items={documents} /></div> },
    { id: "relationships", label: "العلاقات المكانية", content: <SiteRelationshipsPanel nationalId={site.national_id} center={coordinates(site.geometry)} /> },
    { id: "quality", label: "الجودة", content: <div className="registryBody"><SiteCompletenessPanel value={site.completeness} /><SiteQualityPanel snapshots={quality} /></div> },
    { id: "versions", label: "الإصدارات", content: <div className="registryBody"><SiteVersionTimeline items={versions} /></div> },
    { id: "audit", label: "التدقيق", content: <div className="registryBody"><SiteAuditTimeline items={site.audit_timeline} /></div> },
  ]} /><Dialog open={editing} title="تحرير ملف الموقع" onClose={() => setEditing(false)}><SiteProfileForm value={site.profile} onSave={async (value) => { await registryApi.profile(nationalId, value); setEditing(false); await load(); }} /></Dialog></div></GovernmentShell>;
}
