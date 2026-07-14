import type {
  AtlasGeoJSONFeatureCollection,
  AtlasLayerDefinition,
  AtlasLocation,
} from "./national-atlas-types";

export const atlasLayers: readonly AtlasLayerDefinition[] = [
  { id: "hotels", label: "الفنادق", color: "#0d5c8d" },
  { id: "resorts", label: "القرى والمنتجعات", color: "#1e8e63" },
  { id: "restaurants", label: "المطاعم", color: "#c56b2c" },
  { id: "cafes", label: "المقاهي", color: "#8b5e3c" },
  { id: "unesco", label: "مواقع اليونسكو", color: "#7c4d9e" },
  { id: "development", label: "مناطق التنمية والاستثمار", color: "#d7a83c" },
];

// بيانات داخلية نموذجية فقط، مصممة لتوضيح واجهة الخريطة إلى حين ربط LSTA API.
export const sampleAtlasLocations: readonly AtlasLocation[] = [
  { id: "hotel-tripoli", name: "فندق طرابلس المركزي (نموذجي)", category: "hotels", municipality: "طرابلس المركز", verificationStatus: "under_review", source: "سجل LSTA التجريبي", coordinates: [13.1913, 32.8872] },
  { id: "resort-farwa", name: "منتجع فروة الساحلي (نموذجي)", category: "resorts", municipality: "زوارة", verificationStatus: "sample", source: "بيانات العرض الداخلية", coordinates: [11.797, 33.084] },
  { id: "restaurant-benghazi", name: "مطعم بنغازي التراثي (نموذجي)", category: "restaurants", municipality: "بنغازي", verificationStatus: "under_review", source: "سجل LSTA التجريبي", coordinates: [20.0667, 32.1167] },
  { id: "cafe-misrata", name: "مقهى المدينة القديمة (نموذجي)", category: "cafes", municipality: "مصراتة", verificationStatus: "sample", source: "بيانات العرض الداخلية", coordinates: [15.0925, 32.3754] },
  { id: "unesco-leptis", name: "موقع لبدة الكبرى", category: "unesco", municipality: "الخمس", verificationStatus: "verified", source: "قائمة التراث العالمي – نموذج عرض", coordinates: [14.2946, 32.6383] },
  { id: "unesco-ghadames", name: "مدينة غدامس القديمة", category: "unesco", municipality: "غدامس", verificationStatus: "verified", source: "قائمة التراث العالمي – نموذج عرض", coordinates: [9.5007, 30.1337] },
  { id: "development-sabha", name: "منطقة سبها للتنمية السياحية (نموذجي)", category: "development", municipality: "سبها", verificationStatus: "under_review", source: "سيناريو استثماري تجريبي", coordinates: [14.4283, 27.0377] },
  { id: "development-tobruk", name: "محور طبرق الساحلي (نموذجي)", category: "development", municipality: "طبرق", verificationStatus: "sample", source: "بيانات العرض الداخلية", coordinates: [23.9764, 32.0836] },
];

export const sampleAtlasGeoJSON: AtlasGeoJSONFeatureCollection = {
  type: "FeatureCollection",
  features: sampleAtlasLocations.map(({ coordinates, ...properties }) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [...coordinates] },
    properties,
  })),
};

