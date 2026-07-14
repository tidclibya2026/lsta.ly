import { LstaApiError } from "./review";
import type { NearbyResponse, RegistryDetails, RegistryFilters, RegistryPage, RegistrySummary, SiteAttribute, SiteDocument, SiteProfile, SiteRelationship, SiteVersion } from "./registry-types";

const API_URL = process.env.NEXT_PUBLIC_LSTA_API_URL || "http://localhost:8000";
export const REGISTRY_ROLE = process.env.NEXT_PUBLIC_LSTA_REVIEWER_ROLE || "reviewer";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 12000);
  try { const response = await fetch(`${API_URL}${path}`, { ...options, cache: "no-store", signal: controller.signal, headers: { "Content-Type": "application/json", "X-LSTA-Reviewer-Role": REGISTRY_ROLE, ...options.headers } }); if (!response.ok) { const body = await response.json().catch(() => ({})); throw new LstaApiError(body.detail || "تعذر تنفيذ طلب السجل", response.status); } return await response.json() as T; } finally { clearTimeout(timer); }
}
export function buildRegistryQuery(filters: object): string { const query = new URLSearchParams(); Object.entries(filters).forEach(([key, value]) => value !== undefined && value !== "" && query.set(key, String(value))); return query.toString(); }
export const registryApi = {
  summary: () => request<RegistrySummary>("/api/v1/registry/summary"),
  sites: (filters: RegistryFilters) => request<RegistryPage>(`/api/v1/registry/sites?${buildRegistryQuery(filters)}`),
  site: (id: string) => request<RegistryDetails>(`/api/v1/registry/sites/${id}`),
  profile: (id: string, profile: Partial<SiteProfile>) => request<SiteProfile>(`/api/v1/registry/sites/${id}/profile`, { method: "PUT", body: JSON.stringify(profile) }),
  attributes: (id: string) => request<SiteAttribute[]>(`/api/v1/registry/sites/${id}/attributes`),
  media: (id: string) => request<Array<Record<string, unknown>>>(`/api/v1/registry/sites/${id}/media`),
  documents: (id: string) => request<SiteDocument[]>(`/api/v1/registry/sites/${id}/documents`),
  relationships: (id: string) => request<SiteRelationship[]>(`/api/v1/registry/sites/${id}/relationships`),
  nearby: (id: string, filters: { radius_meters: number; source: string; geometry_type?: string; has_name?: boolean; limit: number }) => request<NearbyResponse>(`/api/v1/registry/sites/${id}/nearby?${buildRegistryQuery(filters)}`),
  refreshRelationships: (id: string, payload: { radius_meters: number; source: string; relationship_type: string; limit: number }) => request<{ created: number; items: SiteRelationship[] }>(`/api/v1/registry/sites/${id}/relationships/refresh`, { method: "POST", body: JSON.stringify(payload) }),
  verifyRelationship: (id: string, relationshipId: string, decision: "verify" | "reject") => request<SiteRelationship>(`/api/v1/registry/sites/${id}/relationships/${relationshipId}/${decision}`, { method: "POST", body: "{}" }),
  versions: (id: string) => request<SiteVersion[]>(`/api/v1/registry/sites/${id}/versions`),
  quality: (id: string) => request<Array<Record<string, unknown>>>(`/api/v1/registry/sites/${id}/quality-snapshots`),
};
