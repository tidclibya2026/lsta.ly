export function Skeleton({ width = "100%", height = 16 }: { width?: string; height?: number }) { return <span className="dsSkeleton" aria-hidden="true" style={{ width, height }} />; }
