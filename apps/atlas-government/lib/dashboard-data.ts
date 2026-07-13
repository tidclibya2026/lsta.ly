export type Kpi = {
  label: string;
  value: string;
  note: string;
  status: "positive" | "warning" | "neutral";
};

export const kpis: Kpi[] = [
  { label: "إجمالي المواقع", value: "8,215", note: "رصيد الأطلس العامل", status: "neutral" },
  { label: "المواقع المعتمدة", value: "7,342", note: "بعد التحقق المؤسسي", status: "positive" },
  { label: "قيد المراجعة", value: "412", note: "بيانات أو موقع أو مصدر", status: "warning" },
  { label: "جودة البيانات", value: "94.7%", note: "مؤشر مركب أولي", status: "positive" },
  { label: "فرص الاستثمار", value: "130", note: "ضمن الخارطة الاستثمارية", status: "neutral" },
  { label: "تنبيهات حرجة", value: "7", note: "إحداثيات تحتاج مراجعة", status: "warning" },
];

export const alerts = [
  "7 مواقع بإحداثيات غير صالحة أو خارج النطاق المتوقع.",
  "طبقات الإيواء والمطاعم والمقاهي تحتاج استكمال إسناد البلدية.",
  "طبقة المدن القديمة مرشحة كأول دفعة Staging تجريبية.",
  "لا تنشر أي قيمة إلى Visit Libya قبل اجتياز بوابات الاعتماد.",
];

export const categories = [
  { name: "الأسواق", value: 4363 },
  { name: "المواقع الأثرية", value: 2372 },
  { name: "المواقع الطبيعية", value: 1534 },
  { name: "المقاهي", value: 1282 },
  { name: "المطاعم", value: 1062 },
  { name: "مواقع الجذب", value: 920 },
];
