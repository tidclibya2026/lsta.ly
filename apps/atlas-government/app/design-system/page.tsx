import { DesignSystemShowcase } from "./DesignSystemShowcase";
import { GovernmentShell, PageHeader } from "@/components/layout";
import { Alert } from "@/components/feedback";
import { designTokens } from "@/lib/design-system/tokens";

export default function DesignSystemPage() {
  return <GovernmentShell active=""><PageHeader eyebrow="Government Alpha" title="نظام التصميم الحكومي LSTA" /><Alert tone="info">مرجع داخلي للمكونات والحالات والتوكنز. جميع المكونات تدعم العربية واتجاه RTL.</Alert><section className="dsCard"><h2>ألوان الهوية</h2><div className="dsTokenGrid">{Object.entries(designTokens.colors).map(([name, value]) => <div className="dsToken" style={{ background: value, color: name === "white" || name === "lightGray" ? "#132238" : "#fff" }} key={name}><strong>{name}</strong><br />{value}</div>)}</div></section><DesignSystemShowcase /></GovernmentShell>;
}
