import type { FeatureFilters, PaginatedFeatures, ReviewFeatureDetails, ReviewPayload, ReviewSummary } from "./types";
import { isStaticDemo } from "../deployment-path";

const API_URL = process.env.NEXT_PUBLIC_LSTA_API_URL || "http://127.0.0.1:8000";
const REVIEWER_ROLE = process.env.NEXT_PUBLIC_LSTA_REVIEWER_ROLE || "reviewer";
const TIMEOUT_MS = 12_000;

export class LstaApiError extends Error { constructor(message: string, public status?: number) { super(message); } }

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (isStaticDemo()) throw new LstaApiError("بوابة المراجعة متاحة داخل البيئة الحكومية الداخلية فقط", 403);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${API_URL}${path}`, { ...options, cache: "no-store", signal: controller.signal, headers: { "Content-Type": "application/json", "X-LSTA-Reviewer-Role": REVIEWER_ROLE, ...options.headers } });
    if (!response.ok) { const body = await response.json().catch(() => ({})); throw new LstaApiError(body.detail || "تعذر تنفيذ طلب منصة LSTA", response.status); }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof LstaApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") throw new LstaApiError("انتهت مهلة الاتصال بالخادم");
    throw new LstaApiError(error instanceof Error ? error.message : "تعذر الاتصال بالخادم");
  } finally { clearTimeout(timeout); }
}

export function buildReviewQuery(filters: FeatureFilters = {}): string {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => value !== undefined && value !== "" && query.set(key, String(value)));
  return query.toString();
}

export const reviewApi = {
  summary: () => request<ReviewSummary>("/api/v1/review/summary"),
  features: (filters: FeatureFilters = {}) => request<PaginatedFeatures>(`/api/v1/review/features?${buildReviewQuery(filters)}`),
  feature: (id: string) => request<ReviewFeatureDetails>(`/api/v1/review/features/${id}`),
  review: (id: string, payload: ReviewPayload) => request(`/api/v1/review/features/${id}/reviews`, { method: "POST", body: JSON.stringify(payload) }),
  promote: (id: string) => request<{ site_id: string; national_id: string; status: string }>(`/api/v1/review/features/${id}/promote`, { method: "POST", body: "{}" }),
};
export { REVIEWER_ROLE };
