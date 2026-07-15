"use client";
import { DescriptionList, ImageGallery, StatusBadge } from "@/components/data-display";
import { Drawer } from "@/components/ui";
import { atlasLayers } from "@/lib/national-atlas-data";
import type { AtlasGeoJSONProperties } from "@/lib/national-atlas-types";
import type { ReviewDisplayProperties } from "@/lib/old-tripoli-review";

export type MapSelectedFeature = { kind: "sample"; properties: AtlasGeoJSONProperties } | { kind: "review"; geometryType: string; properties: ReviewDisplayProperties };
const labels = { verified: "متحقق", under_review: "قيد المراجعة", sample: "نموذجي" } as const;

export function MapFeatureDrawer({ selected, onClose }: { selected: MapSelectedFeature | null; onClose: () => void }) {
  if (!selected) return null;
  if (selected.kind === "sample") {
    const item = selected.properties;
    return <Drawer open modal={false} title={item.name} onClose={onClose}><DescriptionList items={[{ label: "الفئة", value: atlasLayers.find((layer) => layer.id === item.category)?.label ?? item.category }, { label: "البلدية", value: item.municipality }, { label: "حالة التحقق", value: labels[item.verificationStatus] }, { label: "المصدر", value: item.source }]} />{item.image && <ImageGallery images={[item.image]} alt={item.name} />}</Drawer>;
  }
  const item = selected.properties; let images: string[] = []; let localImages: string[] = [];
  try { images = JSON.parse(item.image_urls) as string[]; } catch { images = []; }
  try { localImages = JSON.parse(item.local_media_urls) as string[]; } catch { localImages = []; }
  const resolvedImages = images.slice(0, 6).map((original_url, index) => ({ local_media_url: localImages[index] || null, original_url, rights_status: "unknown" as const }));
  const details = [{ label: "feature_id", value: item.feature_id }, ...(selected.geometryType === "LineString" ? [{ label: "النوع", value: item.review_kind }] : []), { label: "الوصف", value: item.description || "لا يوجد وصف" }, ...(item.proposed_name ? [{ label: "الاسم المقترح", value: item.proposed_name }] : []), ...(selected.geometryType === "Point" ? [{ label: "المجلد", value: item.folder || "—" }, { label: "المصدر", value: item.source }] : []), ...(selected.geometryType === "Polygon" ? [{ label: "المساحة التقريبية", value: item.approximate_area_m2 ? `${item.approximate_area_m2.toLocaleString("ar-LY")} م²` : "غير متاحة" }] : []), { label: "حالة المراجعة", value: item.review_status }];
  return <Drawer open modal={false} title={item.name || item.proposed_name || "عنصر بلا اسم"} onClose={onClose}><div className="drawerStatus"><StatusBadge status={item.verification_status === "verified" ? "verified" : item.needs_review ? "under_review" : "unverified"} /></div><DescriptionList items={details} />{selected.geometryType === "LineString" && <p className="reviewPopupWarning">هذا العنصر لا يمثل بالضرورة موقعًا سياحيًا مستقلًا.</p>}<ImageGallery images={resolvedImages} alt={item.name || "صورة الموقع"} /></Drawer>;
}
