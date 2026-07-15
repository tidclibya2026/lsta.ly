import { MetadataEntryCard } from "./MetadataEntryCard";import type { MetadataEntry } from "@/lib/api/metadata-types";
export function MetadataCatalogTable({items}:{items:MetadataEntry[]}){return <div className="metadataGrid">{items.map(entry=><MetadataEntryCard key={entry.catalog_code} entry={entry}/>)}</div>}
