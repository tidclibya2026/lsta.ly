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
import "./search/search.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://tidclibya2026.github.io/lsta.ly/"),
  title: "منصة أطلس ليبيا السياحي الذكي — LSTA",
  description: "منصة وطنية حكومية لإدارة وتحليل وعرض البيانات السياحية المكانية في ليبيا.",
  alternates: { canonical: "https://tidclibya2026.github.io/lsta.ly/" },
  openGraph: { title: "منصة أطلس ليبيا السياحي الذكي — LSTA", description: "منصة وطنية حكومية لإدارة وتحليل وعرض البيانات السياحية المكانية في ليبيا.", url: "https://tidclibya2026.github.io/lsta.ly/", locale: "ar_LY", type: "website" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ar" dir="rtl"><body>{children}</body></html>;
}
