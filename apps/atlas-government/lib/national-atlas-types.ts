export const ATLAS_LAYER_IDS = [
  "hotels",
  "resorts",
  "restaurants",
  "cafes",
  "unesco",
  "development",
] as const;

export type AtlasLayerId = (typeof ATLAS_LAYER_IDS)[number];
export type VerificationStatus = "verified" | "under_review" | "sample";

export interface AtlasLocation {
  id: string;
  name: string;
  category: AtlasLayerId;
  municipality: string;
  verificationStatus: VerificationStatus;
  source: string;
  coordinates: readonly [longitude: number, latitude: number];
  image?: string;
}

export interface AtlasLayerDefinition {
  id: AtlasLayerId;
  label: string;
  color: string;
}

export interface AtlasGeoJSONProperties {
  id: string;
  name: string;
  category: AtlasLayerId;
  municipality: string;
  verificationStatus: VerificationStatus;
  source: string;
  image?: string;
}

export interface AtlasGeoJSONFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: AtlasGeoJSONProperties;
}

export interface AtlasGeoJSONFeatureCollection {
  type: "FeatureCollection";
  features: AtlasGeoJSONFeature[];
}

