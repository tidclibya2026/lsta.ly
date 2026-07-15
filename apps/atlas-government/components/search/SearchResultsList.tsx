import type { SearchResult } from "@/lib/api/search-types";import { SearchResultCard } from "./SearchResultCard";
export function SearchResultsList({items}:{items:SearchResult[]}){return <div className="searchResults">{items.map((item,index)=><SearchResultCard item={item} key={`${item.source}-${item.national_id||item.feature_id}-${index}`}/>)}</div>}
