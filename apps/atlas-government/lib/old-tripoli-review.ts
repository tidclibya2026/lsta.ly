export const OLD_TRIPOLI_REVIEW_LAYER_ID = "old-tripoli-review" as const;

export type ReviewGeometryType = "Point" | "LineString" | "Polygon";
export type ReviewFilter = "all" | "points" | "routes" | "polygons" | "named" | "needs-review";

export interface RawGeoJSONFeature {
  type?: unknown;
  id?: unknown;
  geometry?: { type?: unknown; coordinates?: unknown } | null;
  properties?: Record<string, unknown> | null;
}

export interface ReviewDisplayProperties {
  feature_id: string;
  name: string;
  description: string;
  folder: string;
  source: string;
  verification_status: string;
  image_urls: string;
  local_media_urls: string;
  proposed_name: string;
  review_status: string;
  review_kind: string;
  is_named: boolean;
  needs_review: boolean;
  approximate_area_m2: number;
}

export interface ReviewGeoJSONFeature {
  type: "Feature";
  id: string;
  geometry: { type: ReviewGeometryType; coordinates: unknown };
  properties: ReviewDisplayProperties;
}

export interface ConversionResult {
  feature: ReviewGeoJSONFeature | null;
  issues: string[];
}

export function convertReviewFeature(raw: RawGeoJSONFeature, index = 0): ConversionResult {
  const issues: string[] = [];
  const geometryType = raw.geometry?.type;
  if (!isGeometryType(geometryType)) return { feature: null, issues: [`unsupported_geometry:${String(geometryType ?? "missing")}`] };
  if (!raw.geometry || raw.geometry.coordinates == null) return { feature: null, issues: ["missing_coordinates"] };
  const properties = raw.properties ?? {};
  const featureId = stringValue(properties.feature_id) || stringValue(raw.id) || `OLD-TRIPOLI-UNKNOWN-${index + 1}`;
  if (!properties.feature_id) issues.push("missing_feature_id");
  const name = stringValue(properties.name_ar) || stringValue(properties.name_en);
  const qualityIssues = stringArray(properties.quality_issues);
  const imageUrls = stringArray(properties.image_urls).filter(isSafeImageUrl);
  const localMediaUrls = stringArray(properties.local_media_url ?? properties.local_media_urls);
  const verification = stringValue(properties.verification_status) || "unverified";
  const needsReview = !name || qualityIssues.length > 0 || verification !== "verified";
  if (!name) issues.push("missing_name");
  if (!properties.description_text) issues.push("missing_description");
  return {
    feature: {
      type: "Feature",
      id: featureId,
      geometry: { type: geometryType, coordinates: raw.geometry.coordinates },
      properties: {
        feature_id: featureId,
        name,
        description: stringValue(properties.description_text),
        folder: stringValue(properties.folder_name),
        source: stringValue(properties.source_file) || "ملف KML للمدينة القديمة طرابلس",
        verification_status: verification,
        image_urls: JSON.stringify(imageUrls),
        local_media_urls: JSON.stringify(localMediaUrls),
        proposed_name: stringValue(properties.proposed_name),
        review_status: needsReview ? "يحتاج مراجعة" : "مراجع",
        review_kind: geometryType === "Point" ? "موقع سياحي مستقل" : geometryType === "LineString" ? "مسار أو عنصر خطي" : "منطقة أو حد",
        is_named: Boolean(name),
        needs_review: needsReview,
        approximate_area_m2: geometryType === "Polygon" ? approximatePolygonArea(raw.geometry.coordinates) : 0,
      },
    },
    issues,
  };
}

export function approximatePolygonArea(coordinates: unknown): number {
  if (!Array.isArray(coordinates) || !Array.isArray(coordinates[0])) return 0;
  const ring = coordinates[0] as unknown[];
  if (ring.length < 3) return 0;
  const valid = ring.filter((point): point is number[] => Array.isArray(point) && typeof point[0] === "number" && typeof point[1] === "number");
  if (valid.length < 3) return 0;
  const meanLat = valid.reduce((sum, point) => sum + point[1], 0) / valid.length;
  const xScale = 111_320 * Math.cos((meanLat * Math.PI) / 180);
  const yScale = 110_540;
  let twiceArea = 0;
  for (let index = 0; index < valid.length; index += 1) {
    const current = valid[index];
    const next = valid[(index + 1) % valid.length];
    twiceArea += current[0] * xScale * next[1] * yScale - next[0] * xScale * current[1] * yScale;
  }
  return Math.round(Math.abs(twiceArea) / 2);
}

function isGeometryType(value: unknown): value is ReviewGeometryType {
  return value === "Point" || value === "LineString" || value === "Polygon";
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function stringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
  if (typeof value === "string") {
    try { const parsed: unknown = JSON.parse(value); return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : []; }
    catch { return []; }
  }
  return [];
}

function isSafeImageUrl(value: string): boolean {
  try { const url = new URL(value); return url.protocol === "https:" || url.protocol === "http:"; }
  catch { return false; }
}
