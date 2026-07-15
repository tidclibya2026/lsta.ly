"use client";

import { useMemo, useState } from "react";
import { isStaticDemo, withBasePath } from "@/lib/deployment-path";

export type RightsStatus = "unknown" | "pending_review" | "approved_internal" | "approved_public" | "restricted";
export interface MediaReference { local_media_url?: string | null; original_url?: string | null; rights_status?: RightsStatus }
const PLACEHOLDER = "/images/placeholders/site-image.svg";

export function resolveMediaCandidates(image: string | MediaReference, staticDemo = false): string[] {
  const item: MediaReference = typeof image === "string" ? { original_url: image, rights_status: "unknown" } : image;
  if (staticDemo && item.rights_status !== "approved_public") return [withBasePath(PLACEHOLDER)];
  const values = [item.local_media_url ? withBasePath(item.local_media_url) : "", item.original_url || "", withBasePath(PLACEHOLDER)];
  return [...new Set(values.filter(Boolean))];
}

function GalleryImage({ image, alt, onAvailability }: { image: string | MediaReference; alt: string; onAvailability: (available: boolean) => void }) {
  const candidates = useMemo(() => resolveMediaCandidates(image, isStaticDemo()), [image]);
  const [index, setIndex] = useState(0);
  const unavailable = candidates[index] === withBasePath(PLACEHOLDER);
  return <figure className={unavailable ? "mediaUnavailable" : ""}><img src={candidates[index]} alt={unavailable ? "الصورة غير متاحة" : alt} loading="lazy" referrerPolicy="no-referrer" onLoad={() => onAvailability(!unavailable)} onError={() => { const next = Math.min(index + 1, candidates.length - 1); setIndex(next); if (next === candidates.length - 1) onAvailability(false); }} /><figcaption>{unavailable ? "الصورة غير متاحة" : alt}</figcaption></figure>;
}

export function ImageGallery({ images, alt }: { images: Array<string | MediaReference>; alt: string }) {
  const [availability, setAvailability] = useState<Record<number, boolean>>({});
  if (!images.length) return null;
  const available = Object.values(availability).filter(Boolean).length;
  const unavailable = images.length - available;
  return <section><div className="mediaCounters" aria-live="polite"><span>الصور المتاحة: {available}</span><span>الصور غير المتاحة: {unavailable}</span></div><div className="dsGallery" aria-label="معرض الصور">{images.map((image, index) => <GalleryImage image={image} alt={`${alt} ${index + 1}`} onAvailability={(value) => setAvailability(current => current[index] === value ? current : { ...current, [index]: value })} key={`${typeof image === "string" ? image : image.local_media_url || image.original_url}-${index}`} />)}</div></section>;
}
