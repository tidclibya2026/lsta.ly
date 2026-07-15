export interface MetadataEntry { catalog_code:string;entry_type:string;title_ar:string;title_en?:string|null;description_ar?:string|null;classification_level:string;lifecycle_status:string;verification_status:string;publication_status:string;completeness:number;metadata_json?:Record<string,unknown> }
export interface MetadataPage { items:MetadataEntry[];total:number;limit:number;offset:number;demo?:boolean }
export interface LineageNode { id:string;type:string;reference:string;title:string;system:string }
export interface LineageEdge { id:string;source:string;target:string;type:string;status:string }
export interface LineageGraph { nodes:LineageNode[];edges:LineageEdge[];demo?:boolean }
export interface MetadataFilters { search?:string;entry_type?:string;lifecycle_status?:string;verification_status?:string;publication_status?:string;classification_level?:string;limit?:number;offset?:number }
