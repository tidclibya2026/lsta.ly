import { isStaticDemo, withBasePath } from "../deployment-path";
import type { DiscoveryAnalytics, DiscoveryFilters, DiscoveryResponse, DuplicateCandidate, SavedSearch } from "./discovery-types";

const API = process.env.NEXT_PUBLIC_LSTA_API_URL || "http://127.0.0.1:8000";
const ROLE = process.env.NEXT_PUBLIC_LSTA_REVIEWER_ROLE || "reviewer";
export function buildDiscoveryQuery(values: Record<string, unknown>) { const query = new URLSearchParams(); Object.entries(values).forEach(([key,value]) => { if(value !== undefined && value !== null && value !== "") query.set(key,String(value)); }); return query.toString(); }
export function normalizeDiscoveryError(error: unknown) { return error instanceof Error ? error.message : "تعذر الاتصال بمحرك البحث الوطني"; }
async function request<T>(path:string, init?:RequestInit, retry=1):Promise<T>{const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),12000);try{const response=await fetch(`${API}${path}`,{...init,cache:"no-store",signal:controller.signal,headers:{"Content-Type":"application/json","X-LSTA-Reviewer-Role":ROLE,...init?.headers}});if(!response.ok)throw new Error((await response.json().catch(()=>({}))).detail||"تعذر تنفيذ الطلب");return await response.json() as T}catch(error){if(retry>0)return request<T>(path,init,retry-1);throw error}finally{clearTimeout(timer)}}
async function demo<T>(file:string):Promise<T>{const response=await fetch(withBasePath(`/data/demo/${file}`));if(!response.ok)throw new Error("بيانات العرض التجريبي غير متاحة");return response.json() as Promise<T>}
export const discoveryApi={
  search: async(filters:DiscoveryFilters):Promise<DiscoveryResponse>=>{if(isStaticDemo()){const data=await demo<DiscoveryResponse>("demo-discovery.json");const q=filters.q.toLocaleLowerCase("ar");const items=data.items.filter(item=>!q||`${item.name_ar} ${item.name_en} ${item.national_id}`.toLocaleLowerCase("ar").includes(q));return{...data,items,total_count:items.length,is_demo:true}}return request(`/api/v1/discovery/search?${buildDiscoveryQuery(filters as unknown as Record<string,unknown>)}`)},
  autocomplete:(q:string)=>isStaticDemo()?demo<DiscoveryResponse>("demo-discovery.json").then(data=>({items:data.items.filter(item=>(item.name_ar||"").includes(q)).slice(0,10).map(item=>({label:item.name_ar,source:item.source,national_id:item.national_id}))})):request<{items:unknown[]}>(`/api/v1/discovery/autocomplete?${buildDiscoveryQuery({q})}`),
  facets:()=>isStaticDemo()?Promise.resolve({source_counts:{registry:1}}):request<Record<string,unknown>>("/api/v1/discovery/facets"),
  saved:()=>isStaticDemo()?Promise.resolve({items:JSON.parse(localStorage.getItem("lsta-saved-searches")||"[]") as SavedSearch[]}):request<{items:SavedSearch[]}>("/api/v1/discovery/saved-searches"),
  save:async(value:Omit<SavedSearch,"id">)=>{if(isStaticDemo()){const row={...value,id:crypto.randomUUID()};const old=JSON.parse(localStorage.getItem("lsta-saved-searches")||"[]");localStorage.setItem("lsta-saved-searches",JSON.stringify([row,...old]));return row}return request<SavedSearch>("/api/v1/discovery/saved-searches",{method:"POST",body:JSON.stringify(value)})},
  duplicates:()=>isStaticDemo()?demo<{items:DuplicateCandidate[]}>("demo-duplicates.json"):request<{items:DuplicateCandidate[]}>("/api/v1/discovery/duplicates"),
  analytics:()=>isStaticDemo()?demo<DiscoveryAnalytics>("demo-discovery-analytics.json"):request<DiscoveryAnalytics>("/api/v1/discovery/analytics/summary"),
};
