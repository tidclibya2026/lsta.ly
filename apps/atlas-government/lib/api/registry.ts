import { LstaApiError } from "./review";
import type { NearbyResponse, RegistryDetails, RegistryFilters, RegistryPage, RegistrySummary, SiteAttribute, SiteDocument, SiteProfile, SiteRelationship, SiteVersion } from "./registry-types";
import { isStaticDemo, withBasePath } from "../deployment-path";

const API_URL = process.env.NEXT_PUBLIC_LSTA_API_URL || "http://127.0.0.1:8000";
export const REGISTRY_ROLE = process.env.NEXT_PUBLIC_LSTA_REVIEWER_ROLE || "reviewer";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 12000);
  try { const response = await fetch(`${API_URL}${path}`, { ...options, cache: "no-store", signal: controller.signal, headers: { "Content-Type": "application/json", "X-LSTA-Reviewer-Role": REGISTRY_ROLE, ...options.headers } }); if (!response.ok) { const body = await response.json().catch(() => ({})); throw new LstaApiError(body.detail || "تعذر تنفيذ طلب السجل", response.status); } return await response.json() as T; } finally { clearTimeout(timer); }
}
interface DemoSites { demo: true; items: RegistryPage["items"]; total: number; limit: number; offset: number; details: RegistryDetails }
async function demoSites(): Promise<DemoSites> { const response = await fetch(withBasePath("/data/demo/demo-sites.json")); if (!response.ok) throw new LstaApiError("تعذر تحميل بيانات العرض"); return response.json() as Promise<DemoSites>; }
function internalOnly<T>(): Promise<T> { return Promise.reject(new LstaApiError("هذه العملية متاحة داخل البيئة الحكومية الداخلية فقط", 403)); }
export function buildRegistryQuery(filters: object): string { const query = new URLSearchParams(); Object.entries(filters).forEach(([key, value]) => value !== undefined && value !== "" && query.set(key, String(value))); return query.toString(); }
export const registryApi = {
  summary: async () => isStaticDemo() ? (await (await fetch(withBasePath("/data/demo/demo-summary.json"))).json() as {registry: RegistrySummary}).registry : request<RegistrySummary>("/api/v1/registry/summary"),
  sites: async (filters: RegistryFilters) => isStaticDemo() ? await demoSites() : request<RegistryPage>(`/api/v1/registry/sites?${buildRegistryQuery(filters)}`),
  site: async (id: string) => isStaticDemo() ? (await demoSites()).details : request<RegistryDetails>(`/api/v1/registry/sites/${id}`),
  profile: (id: string, profile: Partial<SiteProfile>) => isStaticDemo() ? internalOnly<SiteProfile>() : request<SiteProfile>(`/api/v1/registry/sites/${id}/profile`, { method: "PUT", body: JSON.stringify(profile) }),
  attributes: (id: string) => isStaticDemo() ? Promise.resolve([] as SiteAttribute[]) : request<SiteAttribute[]>(`/api/v1/registry/sites/${id}/attributes`),
  media: (id: string) => isStaticDemo() ? Promise.resolve([]) : request<Array<Record<string, unknown>>>(`/api/v1/registry/sites/${id}/media`),
  documents: (id: string) => isStaticDemo() ? Promise.resolve([] as SiteDocument[]) : request<SiteDocument[]>(`/api/v1/registry/sites/${id}/documents`),
  relationships: (id: string) => isStaticDemo() ? Promise.resolve([] as SiteRelationship[]) : request<SiteRelationship[]>(`/api/v1/registry/sites/${id}/relationships`),
  nearby: (id: string, filters: { radius_meters: number; source: string; geometry_type?: string; has_name?: boolean; limit: number }) => isStaticDemo() ? Promise.resolve({ center_site: { national_id: id, name: "المدينة القديمة طرابلس" }, radius_meters: filters.radius_meters, total_results: 0, results: [], query_time_ms: 0 }) : request<NearbyResponse>(`/api/v1/registry/sites/${id}/nearby?${buildRegistryQuery(filters)}`),
  refreshRelationships: (id: string, payload: { radius_meters: number; source: string; relationship_type: string; limit: number }) => isStaticDemo() ? internalOnly<{ created: number; items: SiteRelationship[] }>() : request<{ created: number; items: SiteRelationship[] }>(`/api/v1/registry/sites/${id}/relationships/refresh`, { method: "POST", body: JSON.stringify(payload) }),
  verifyRelationship: (id: string, relationshipId: string, decision: "verify" | "reject") => isStaticDemo() ? internalOnly<SiteRelationship>() : request<SiteRelationship>(`/api/v1/registry/sites/${id}/relationships/${relationshipId}/${decision}`, { method: "POST", body: "{}" }),
  versions: (id: string) => isStaticDemo() ? Promise.resolve([] as SiteVersion[]) : request<SiteVersion[]>(`/api/v1/registry/sites/${id}/versions`),
  quality: (id: string) => isStaticDemo() ? Promise.resolve([]) : request<Array<Record<string, unknown>>>(`/api/v1/registry/sites/${id}/quality-snapshots`),
};
