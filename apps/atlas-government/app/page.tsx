import { alerts, categories, kpis } from "@/lib/dashboard-data";

const menu = ["لوحة الوزير", "الخريطة الوطنية", "المؤشرات", "الاستثمار", "الدراسات", "جودة البيانات", "الذكاء الاصطناعي", "الإدارة"];

export default function MinisterDashboard() {
  const maxCategory = Math.max(...categories.map((item) => item.value));

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brandMark">LSTA</span>
          <div><strong>أطلس ليبيا السياحي الذكي</strong><small>المنصة الحكومية التنفيذية</small></div>
        </div>
        <nav aria-label="القائمة الرئيسية">
          {menu.map((item, index) => <a className={index === 0 ? "active" : ""} href="#" key={item}>{item}</a>)}
        </nav>
        <div className="classification">تصنيف النظام: استخدام حكومي</div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p>دولة ليبيا · وزارة السياحة والصناعات التقليدية</p><h1>لوحة الوزير التنفيذية</h1></div>
          <div className="topActions"><button>طباعة الموجز</button><div className="user">معالي الوزير<br/><span>صانع قرار</span></div></div>
        </header>

        <div className="notice">الأرقام المعروضة في هذه النسخة تجمع بين بيانات عمل فعلية وقيم تصميمية، ولا تعتمد للنشر العام قبل الربط النهائي بقاعدة LSTA الوطنية.</div>

        <section className="kpiGrid" aria-label="المؤشرات الرئيسية">
          {kpis.map((kpi) => (
            <article className={`kpi ${kpi.status}`} key={kpi.label}>
              <span>{kpi.label}</span><strong>{kpi.value}</strong><small>{kpi.note}</small>
            </article>
          ))}
        </section>

        <section className="mainGrid">
          <article className="panel mapPanel">
            <div className="panelHead"><div><span>المشهد المكاني الوطني</span><h2>خريطة متابعة المواقع والجاهزية</h2></div><div className="tabs"><button className="selected">المواقع</button><button>الجودة</button><button>الاستثمار</button></div></div>
            <div className="mapMock" role="img" aria-label="نموذج خريطة ليبيا التنفيذية">
              <div className="libyaShape">ليبيا<div className="pin p1">614</div><div className="pin p2">381</div><div className="pin p3">141</div></div>
              <div className="mapLegend"><span>● معتمد</span><span>● قيد المراجعة</span><span>● يحتاج تحقق</span></div>
            </div>
          </article>

          <article className="panel alertsPanel">
            <div className="panelHead"><div><span>الإنذار المبكر</span><h2>التنبيهات ذات الأولوية</h2></div><b>{alerts.length}</b></div>
            <ul>{alerts.map((alert, index) => <li key={alert}><i>{index + 1}</i><span>{alert}</span></li>)}</ul>
          </article>
        </section>

        <section className="lowerGrid">
          <article className="panel">
            <div className="panelHead"><div><span>التركيب القطاعي</span><h2>أكبر طبقات الأطلس</h2></div></div>
            <div className="bars">{categories.map((category) => <div className="barRow" key={category.name}><span>{category.name}</span><div><i style={{width: `${(category.value / maxCategory) * 100}%`}} /></div><b>{category.value.toLocaleString("ar-LY")}</b></div>)}</div>
          </article>

          <article className="panel qualityCard">
            <div className="panelHead"><div><span>مؤشر الجودة الوطني</span><h2>جاهزية البيانات للاعتماد</h2></div></div>
            <div className="score">94.7<small>%</small></div>
            <div className="meter"><i /></div>
            <p>المؤشر سيحسب لاحقًا مباشرة من اكتمال الهوية والموقع والمصدر وحالة التحقق.</p>
          </article>

          <article className="panel aiCard">
            <div className="panelHead"><div><span>مساعد الوزير</span><h2>استعلام تنفيذي ذكي</h2></div></div>
            <p>مثال: اعرض البلديات الأعلى في عدد الفنادق، ثم حدد الفجوات الاستثمارية.</p>
            <div className="prompt"><input aria-label="سؤال مساعد الوزير" placeholder="اكتب سؤالك التنفيذي..."/><button>تحليل</button></div>
            <small>سيتم الربط بخدمة ذكاء اصطناعي مؤسسية مع إظهار المصادر ودرجة الثقة.</small>
          </article>
        </section>
      </section>
    </main>
  );
}
