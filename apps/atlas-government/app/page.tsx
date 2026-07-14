import { NationalAtlasMap } from "@/components/maps";
import { MetricBar, StatCard } from "@/components/data-display";
import { Alert } from "@/components/feedback";
import { TextInput } from "@/components/forms";
import { GovernmentShell, SectionHeader, Topbar } from "@/components/layout";
import { Badge, Button, Card, Tabs } from "@/components/ui";
import { alerts, categories, kpis } from "@/lib/dashboard-data";

export default function MinisterDashboard() {
  const maxCategory = Math.max(...categories.map((item) => item.value));
  return <GovernmentShell>
    <Topbar eyebrow="دولة ليبيا · وزارة السياحة والصناعات التقليدية" title="لوحة الوزير التنفيذية" actions={<><Button variant="secondary">طباعة الموجز</Button><div className="user">معالي الوزير<br /><span>صانع قرار</span></div></>} />
    <Alert tone="warning">الأرقام المعروضة في هذه النسخة تجمع بين بيانات عمل فعلية وقيم تصميمية، ولا تعتمد للنشر العام قبل الربط النهائي بقاعدة LSTA الوطنية.</Alert>
    <section className="kpiGrid" aria-label="المؤشرات الرئيسية">{kpis.map((kpi) => <StatCard {...kpi} key={kpi.label} />)}</section>
    <section className="mainGrid">
      <Card className="mapPanel"><SectionHeader eyebrow="المشهد المكاني الوطني" title="خريطة متابعة المواقع والجاهزية" actions={<Tabs ariaLabel="وضع الخريطة" items={[{ id: "sites", label: "المواقع" }, { id: "quality", label: "الجودة" }, { id: "investment", label: "الاستثمار" }]} />} /><NationalAtlasMap /></Card>
      <Card className="alertsPanel"><SectionHeader eyebrow="الإنذار المبكر" title="التنبيهات ذات الأولوية" actions={<Badge tone="warning">{alerts.length}</Badge>} /><ul>{alerts.map((alert, index) => <li key={alert}><i>{index + 1}</i><span>{alert}</span></li>)}</ul></Card>
    </section>
    <section className="lowerGrid">
      <Card><SectionHeader eyebrow="التركيب القطاعي" title="أكبر طبقات الأطلس" /><div className="bars">{categories.map((category) => <MetricBar label={category.name} value={category.value} max={maxCategory} key={category.name} />)}</div></Card>
      <Card className="qualityCard"><SectionHeader eyebrow="مؤشر الجودة الوطني" title="جاهزية البيانات للاعتماد" /><div className="score">94.7<small>%</small></div><div className="meter"><i /></div><p>المؤشر سيحسب لاحقًا مباشرة من اكتمال الهوية والموقع والمصدر وحالة التحقق.</p></Card>
      <Card className="aiCard"><SectionHeader eyebrow="مساعد الوزير" title="استعلام تنفيذي ذكي" /><p>مثال: اعرض البلديات الأعلى في عدد الفنادق، ثم حدد الفجوات الاستثمارية.</p><div className="prompt"><TextInput label="سؤال مساعد الوزير" aria-label="سؤال مساعد الوزير" placeholder="اكتب سؤالك التنفيذي..." /><Button>تحليل</Button></div><small>سيتم الربط بخدمة ذكاء اصطناعي مؤسسية مع إظهار المصادر ودرجة الثقة.</small></Card>
    </section>
  </GovernmentShell>;
}
