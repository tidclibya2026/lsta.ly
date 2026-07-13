import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "لوحة الوزير | أطلس ليبيا السياحي الذكي",
  description: "الواجهة الحكومية التنفيذية لمنصة أطلس ليبيا السياحي الذكي",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ar" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
