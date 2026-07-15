"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl, { type Map as MapLibreMap, type MapLayerMouseEvent } from "maplibre-gl";
import { atlasLayers, sampleAtlasGeoJSON } from "@/lib/national-atlas-data";
import { ATLAS_LAYER_IDS, type AtlasGeoJSONProperties, type AtlasLayerId } from "@/lib/national-atlas-types";
import { convertReviewFeature, OLD_TRIPOLI_REVIEW_LAYER_ID, type RawGeoJSONFeature, type ReviewDisplayProperties, type ReviewFilter, type ReviewGeoJSONFeature } from "@/lib/old-tripoli-review";
import { LayerTree } from "@/components/maps/LayerTree";
import { MapFeatureDrawer, type MapSelectedFeature } from "@/components/maps/MapFeatureDrawer";
import { MapLegend } from "@/components/maps/MapLegend";
import { MapToolbar } from "@/components/maps/MapToolbar";
import { isStaticDemo, withBasePath } from "@/lib/deployment-path";

const LIBYA_CENTER: [number, number] = [17.2283, 27.5];
const TRIPOLI_CENTER: [number, number] = [13.18, 32.895];
const SOURCE_ID = "lsta-sample-locations";
const REVIEW_SOURCE_ID = OLD_TRIPOLI_REVIEW_LAYER_ID;
const REVIEW_LAYER_IDS = { Point: "old-tripoli-review-points", LineString: "old-tripoli-review-lines", Polygon: "old-tripoli-review-polygons" } as const;
const REVIEW_NOTICE = "هذه البيانات مستخرجة من ملف KML لفريق أطلس ليبيا السياحي، وهي قيد المراجعة ولم تعتمد للنشر العام.";
const reviewFilters: { id: ReviewFilter; label: string }[] = [
  { id: "all", label: "الكل" }, { id: "points", label: "النقاط" }, { id: "routes", label: "المسارات" },
  { id: "polygons", label: "المضلعات" }, { id: "named", label: "العناصر المسماة فقط" }, { id: "needs-review", label: "تحتاج مراجعة" },
];
const layerId = (id: AtlasLayerId) => `lsta-${id}`;
function addReviewLayers(map: MapLibreMap, features: ReviewGeoJSONFeature[], onSelect: (feature: MapSelectedFeature) => void) {
  map.addSource(REVIEW_SOURCE_ID, { type: "geojson", data: { type: "FeatureCollection", features } as never });
  map.addLayer({ id: REVIEW_LAYER_IDS.Polygon, type: "fill", source: REVIEW_SOURCE_ID, filter: ["==", ["geometry-type"], "Polygon"], paint: { "fill-color": "#d7a83c", "fill-opacity": 0.24, "fill-outline-color": "#8c6818" } });
  map.addLayer({ id: REVIEW_LAYER_IDS.LineString, type: "line", source: REVIEW_SOURCE_ID, filter: ["==", ["geometry-type"], "LineString"], paint: { "line-color": "#cf6b32", "line-width": ["interpolate", ["linear"], ["zoom"], 12, 2, 17, 5], "line-opacity": 0.82 } });
  map.addLayer({ id: REVIEW_LAYER_IDS.Point, type: "circle", source: REVIEW_SOURCE_ID, filter: ["==", ["geometry-type"], "Point"], paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 5, 17, 10], "circle-color": "#7c4d9e", "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
  Object.values(REVIEW_LAYER_IDS).forEach((id) => {
    map.on("click", id, (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0]; if (!feature) return;
      onSelect({ kind: "review", properties: feature.properties as ReviewDisplayProperties, geometryType: feature.geometry.type });
    });
    map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
  });
}

function applyReviewFilter(map: MapLibreMap, filter: ReviewFilter) {
  const geometryVisibility: Record<string, boolean> = {
    [REVIEW_LAYER_IDS.Point]: filter === "all" || filter === "points" || filter === "named" || filter === "needs-review",
    [REVIEW_LAYER_IDS.LineString]: filter === "all" || filter === "routes" || filter === "named" || filter === "needs-review",
    [REVIEW_LAYER_IDS.Polygon]: filter === "all" || filter === "polygons" || filter === "named" || filter === "needs-review",
  };
  Object.entries(geometryVisibility).forEach(([id, visible]) => {
    if (!map.getLayer(id)) return;
    map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    const geometry = id === REVIEW_LAYER_IDS.Point ? "Point" : id === REVIEW_LAYER_IDS.LineString ? "LineString" : "Polygon";
    const base: maplibregl.FilterSpecification = ["==", ["geometry-type"], geometry];
    const expression = filter === "named" ? ["all", base, ["==", ["get", "is_named"], true]] : filter === "needs-review" ? ["all", base, ["==", ["get", "needs_review"], true]] : base;
    map.setFilter(id, expression as maplibregl.FilterSpecification);
  });
}

export default function NationalAtlasMap() {
  const containerRef = useRef<HTMLDivElement>(null); const mapRef = useRef<MapLibreMap | null>(null); const reviewLoaded = useRef(false);
  const [enabledLayers, setEnabledLayers] = useState<Set<AtlasLayerId>>(() => new Set(ATLAS_LAYER_IDS));
  const [ready, setReady] = useState(false); const [error, setError] = useState(false); const [reviewEnabled, setReviewEnabled] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false); const [reviewError, setReviewError] = useState(""); const [reviewInfo, setReviewInfo] = useState("");
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [selectedFeature, setSelectedFeature] = useState<MapSelectedFeature | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({ container: containerRef.current, center: LIBYA_CENTER, zoom: 4.45, minZoom: 3, maxZoom: 18, attributionControl: false,
      style: { version: 8, sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap contributors" } }, layers: [{ id: "osm", type: "raster", source: "osm" }] } });
    mapRef.current = map; map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left"); map.addControl(new maplibregl.FullscreenControl(), "top-left"); map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");
    map.on("load", () => {
      map.addSource(SOURCE_ID, { type: "geojson", data: sampleAtlasGeoJSON });
      atlasLayers.forEach((layer) => {
        map.addLayer({ id: layerId(layer.id), type: "circle", source: SOURCE_ID, filter: ["==", ["get", "category"], layer.id], paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 7, 10, 12], "circle-color": layer.color, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2.5, "circle-opacity": 0.95 } });
        map.on("click", layerId(layer.id), (event: MapLayerMouseEvent) => { const feature = event.features?.[0]; if (!feature) return; setSelectedFeature({ kind: "sample", properties: feature.properties as AtlasGeoJSONProperties }); });
        map.on("mouseenter", layerId(layer.id), () => { map.getCanvas().style.cursor = "pointer"; }); map.on("mouseleave", layerId(layer.id), () => { map.getCanvas().style.cursor = ""; });
      }); setReady(true);
    });
    map.on("error", (event) => { if (event.error?.message.includes("tile")) setError(true); });
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => { const map = mapRef.current; if (map && reviewLoaded.current) applyReviewFilter(map, reviewFilter); }, [reviewFilter]);

  const toggleLayer = (id: AtlasLayerId) => setEnabledLayers((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); const map = mapRef.current; if (map?.getLayer(layerId(id))) map.setLayoutProperty(layerId(id), "visibility", next.has(id) ? "visible" : "none"); return next; });

  const toggleReview = async () => {
    const map = mapRef.current; if (!map || !ready || reviewLoading) return;
    if (reviewEnabled) { Object.values(REVIEW_LAYER_IDS).forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", "none")); setReviewEnabled(false); return; }
    setReviewEnabled(true); setReviewError("");
    if (reviewLoaded.current) { applyReviewFilter(map, reviewFilter); map.flyTo({ center: TRIPOLI_CENTER, zoom: 14 }); return; }
    setReviewLoading(true);
    try {
      const path = isStaticDemo() ? "/data/demo/demo-map.geojson" : "/data/review/old_tripoli.geojson";
      const response = await fetch(withBasePath(path), { cache: "no-store" }); if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const raw = await response.json() as { type?: unknown; features?: unknown };
      if (!Array.isArray(raw.features) || raw.features.length === 0) throw new Error("ملف GeoJSON فارغ");
      const results = raw.features.map((item, index) => convertReviewFeature(item as RawGeoJSONFeature, index));
      const features = results.flatMap((item) => item.feature ? [item.feature] : []);
      const unsupported = results.filter((item) => !item.feature).length; const incomplete = results.filter((item) => item.issues.length > 0).length;
      if (!features.length) throw new Error("لا توجد هندسات مدعومة قابلة للعرض");
      addReviewLayers(map, features, setSelectedFeature); reviewLoaded.current = true; applyReviewFilter(map, reviewFilter);
      setReviewInfo(unsupported || incomplete ? `تم تجاهل ${unsupported} هندسة غير مدعومة، ورُصدت بيانات ناقصة في ${incomplete} عنصر.` : "");
      map.flyTo({ center: TRIPOLI_CENTER, zoom: 14, essential: true });
    } catch (cause) { setReviewEnabled(false); setReviewError(`تعذر تحميل بيانات المراجعة: ${cause instanceof Error ? cause.message : "خطأ غير معروف"}`); }
    finally { setReviewLoading(false); }
  };

  return (
    <section className="nationalAtlas" aria-label="الخريطة الوطنية التفاعلية">
      <div ref={containerRef} className="nationalAtlasCanvas" />
      {!ready && <div className="mapLoading" role="status">جارٍ تجهيز الخريطة الوطنية…</div>}
      <div className="mapSampleNotice"><b>تنبيه:</b> المواقع والخصائص المعروضة بيانات نموذجية داخلية وليست بيانات رسمية معتمدة.</div>
      {reviewEnabled && <div className="reviewDataNotice" role="status">{REVIEW_NOTICE}</div>}
      <aside className="mapLayers" aria-label="التحكم في طبقات الخريطة">
        <div className="mapLayersHead"><strong>طبقات الأطلس</strong><small>{enabledLayers.size} / {atlasLayers.length}</small></div>
        <LayerTree groups={[
          { id: "atlas", label: "الطبقات الوطنية", items: atlasLayers.map((layer) => ({ id: layer.id, label: layer.label, section: layer.id === "hotels" || layer.id === "resorts" ? "الإيواء" : layer.id === "restaurants" || layer.id === "cafes" ? "خدمات الطعام" : layer.id === "unesco" ? "التراث" : "الاستثمار", color: layer.color, enabled: enabledLayers.has(layer.id) })) },
          { id: "review", label: "البيانات قيد المراجعة", items: [{ id: REVIEW_SOURCE_ID, label: "المدينة القديمة طرابلس", color: "#7c4d9e", enabled: reviewEnabled, disabled: !ready || reviewLoading, loading: reviewLoading }] },
        ]} onToggle={(id) => id === REVIEW_SOURCE_ID ? void toggleReview() : toggleLayer(id as AtlasLayerId)} />
        {reviewEnabled && <div className="reviewControls">
          <div className="reviewCounters"><span>الإجمالي <b>430</b></span><span>النقاط <b>135</b></span><span>الخطوط <b>285</b></span><span>المضلعات <b>10</b></span><span>المسماة <b>194</b></span><span>غير المسماة <b>236</b></span></div>
          <div className="reviewFilter" role="group" aria-label="تصفية بيانات المدينة القديمة">{reviewFilters.map((filter) => <button type="button" className={reviewFilter === filter.id ? "active" : ""} onClick={() => setReviewFilter(filter.id)} key={filter.id}>{filter.label}</button>)}</div>
          <MapLegend items={[{ id: "point", label: "موقع سياحي", color: "#7c4d9e" }, { id: "line", label: "مسار أو خط", color: "#cf6b32", symbol: "line" }, { id: "polygon", label: "منطقة أو حد", color: "#d7a83c", symbol: "polygon" }]} />
        </div>}
      </aside>
      <MapToolbar onReset={() => mapRef.current?.flyTo({ center: LIBYA_CENTER, zoom: 4.45, essential: true })} disabled={!ready} />
      {reviewLoading && <div className="reviewMapMessage">جارٍ تحميل بيانات المراجعة…</div>}{reviewError && <div className="reviewMapMessage error">{reviewError}</div>}{reviewInfo && reviewEnabled && <div className="reviewMapMessage">{reviewInfo}</div>}
      {error && <div className="mapTileError">تعذر تحميل بعض بلاطات الخريطة. تحقق من الاتصال بالإنترنت.</div>}
      <MapFeatureDrawer selected={selectedFeature} onClose={() => setSelectedFeature(null)} />
    </section>
  );
}
