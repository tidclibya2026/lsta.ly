import type { DiscoveryResult } from "@/lib/api/discovery-types"; import { DiscoveryResultCard } from "./DiscoveryResultCard";
export function DiscoveryResults({items}:{items:DiscoveryResult[]}){return <div className="discoveryResults">{items.map((item,index)=><DiscoveryResultCard key={item.national_id||item.feature_id||index} item={item}/>)}</div>}
