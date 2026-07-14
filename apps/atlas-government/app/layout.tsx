import type { Metadata } from "next";
import "./globals.css";
import "../styles/tokens.css";
import "../styles/utilities.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "./national-atlas-map.css";
import "./design-system.css";
import "./government-alpha.css";
import "./review/review.css";
import "./sites/sites.css";

export const metadata: Metadata = {
  title: "منصة أطلس ليبيا السياحي الذكي | LSTA",
  description: "Libya Smart Tourism Atlas — Government Portal",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ar" dir="rtl"><body>{children}</body></html>;
}
