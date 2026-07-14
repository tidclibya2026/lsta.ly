import { IconButton } from "@/components/ui";
export function MapToolbar({ onReset, disabled }: { onReset: () => void; disabled?: boolean }) { return <div className="dsMapToolbar" role="toolbar" aria-label="أدوات الخريطة"><IconButton label="إعادة التمركز على ليبيا" onClick={onReset} disabled={disabled}>⌖</IconButton></div>; }
