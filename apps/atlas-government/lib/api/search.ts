import { LstaApiError } from "./review";
import type { AutocompleteItem, SearchFilters, SearchResponse, SearchResult } from "./search-types";
import { isStaticDemo } from "../deployment-path";

const URL = process.env.NEXT_PUBLIC_LSTA_API_URL || "http://127.0.0.1:8000";
const ROLE = process.env.NEXT_PUBLIC_LSTA_REVIEWER_ROLE || "reviewer";

const demoItem: SearchResult = {
  result_type: "site", source: "registry", national_id: "LSTA-OLD-TRIPOLI-000001", feature_id: null,
  name_ar: "المدينة القديمة طرابلس", name_en: "Old City of Tripoli", normalized_name: "المدينه القديمه طرابلس",
  description_excerpt: "نتيجة تجريبية محلية محدودة للسجل الوطني.", geometry_type: "Point", category: "تراث",
  municipality: "طرابلس المركز", verification_status: "approved", publication_status: "internal", review_status: null,
  quality_score: 85, has_images: false, image_count: 0, primary_image: null, centroid: [13.1808, 32.8959], bbox: null,
  distance_meters: null, relevance_score: 100, matched_fields: ["name_ar"], highlighted_name: null,
  highlighted_description: null, map_geometry_summary: { centroid: [13.1808, 32.8959] },
  detail_url: "/sites/LSTA-OLD-TRIPOLI-000001", is_review_data: false,
};

async function request<T>(path: string, retries = 1): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(`${URL}${path}`, { cache: "no-store", signal: controller.signal, headers: { "X-LSTA-Reviewer-Role": ROLE } });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new LstaApiError(body.detail || "تعذر البحث", response.status);
    }
    return await response.json() as T;
  } catch (error) {
    if (retries > 0 && !(error instanceof LstaApiError && (error.status ?? 500) < 500)) return request<T>(path, retries - 1);
    if (error instanceof LstaApiError) throw error;
    throw new LstaApiError(error instanceof Error ? error.message : "تعذر الاتصال بمحرك البحث");
  } finally { clearTimeout(timer); }
}

export function buildSearchQuery(filters: object) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => value !== undefined && value !== "" && query.set(key, String(value)));
  return query.toString();
}

function demoSearch(filters: SearchFilters): SearchResponse {
  const q = filters.q.trim().toLocaleLowerCase("ar");
  const items = q.length >= 2 && (`${demoItem.name_ar} ${demoItem.name_en} ${demoItem.national_id}`).toLocaleLowerCase("ar").includes(q) ? [demoItem] : [];
  return { items, total: items.length, total_count: items.length, limit: filters.limit, offset: filters.offset, has_more: false, query_time_ms: 0, is_demo: true };
}

export const searchApi = {
  search: (filters: SearchFilters) => isStaticDemo() ? Promise.resolve(demoSearch(filters)) : request<SearchResponse>(`/api/v1/search?${buildSearchQuery(filters)}`),
  autocomplete: (q: string, source = "all") => isStaticDemo()
    ? Promise.resolve({ items: demoSearch({ q, source: "registry", limit: 10, offset: 0 }).items.map(item => ({ label: item.name_ar || "", secondary_label: item.national_id, type: "site", source: item.source, national_id: item.national_id, detail_url: item.detail_url })) })
    : request<{items: AutocompleteItem[]}>(`/api/v1/search/autocomplete?${buildSearchQuery({ q, source, limit: 10 })}`),
  facets: () => isStaticDemo() ? Promise.resolve({ source_counts: { registry: 1 } }) : request<Record<string, Record<string, number>>>("/api/v1/search/facets"),
};
