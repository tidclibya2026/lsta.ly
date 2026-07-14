# منصة أطلس ليبيا السياحي الذكي
## Libya Smart Tourism Atlas — LSTA

منصة وطنية حكومية لإدارة وتكامل وتحليل ومراجعة ونشر البيانات الجغرافية السياحية في دولة ليبيا، بإشراف **وزارة السياحة والصناعات التقليدية** وتنفيذ **مركز المعلومات والتوثيق السياحي**.

> **الشعار المؤسسي:** بيانات موثوقة… قرارات ذكية… سياحة مستدامة.

## حالة الإصدار

الإصدار الحالي: **Government Alpha v0.1.0**

هذا الإصدار مخصص للتطوير والمراجعة المؤسسية، ولا يمثل نسخة عامة نهائية ولا يجيز نشر البيانات إلى Visit Libya أو أي قناة عامة دون اعتماد رسمي.

## القدرات المنفذة

- بوابة حكومية مبنية بـ Next.js وTypeScript وواجهة عربية RTL.
- نظام تصميم حكومي موحد وقابل لإعادة الاستخدام.
- خريطة وطنية تفاعلية باستخدام MapLibre GL JS.
- مستورد KML/KMZ مع استخراج الوصف والوسائط والبيانات الوصفية.
- PostgreSQL/PostGIS عبر Docker.
- قاعدة Staging منفصلة عن السجل الوطني.
- بوابة مراجعة واعتماد متعددة المراحل.
- محرك جودة بيانات بدرجات وقواعد قابلة للتدقيق.
- سجل وطني للمواقع السياحية وملف متكامل لكل موقع.
- محرك العلاقات المكانية والبحث عن العناصر القريبة.
- FastAPI مع واجهات Typed وصلاحيات مؤقتة تعتمد الأدوار.
- سجل تدقيق وإصدارات تاريخية للتعديلات.

## المعمارية

```text
مصادر البيانات
KML / KMZ / GeoJSON / Excel / الدراسات / الصور
        ↓
Importer + Validation
        ↓
Staging Database
        ↓
Review Workflow
        ↓
National Registry (PostgreSQL + PostGIS)
        ↓
FastAPI
        ↓
Government Portal / GIS / Reports / Future Integrations
```

## هيكل المستودع

```text
apps/atlas-government     واجهة الحكومة ولوحات المراجعة والسجل
services/atlas-api        FastAPI ونماذج البيانات والخدمات
infrastructure            Docker وPostGIS
 tools/kml_importer        مستورد KML/KMZ
 data                      بيانات خام ومعالجة محلية غير مخصصة للنشر العام
 docs                      الوثائق المؤسسية والفنية
```

## التشغيل المحلي

### 1. PostGIS

```powershell
Copy-Item .\infrastructure\.env.example .\infrastructure\.env
docker compose --env-file .\infrastructure\.env -f .\infrastructure\docker-compose.yml up -d
```

### 2. Backend

```powershell
cd services\atlas-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

توثيق API:

```text
http://localhost:8000/docs
```

### 3. Government Portal

```powershell
cd apps\atlas-government
npm install
npm run dev
```

الواجهة:

```text
http://localhost:3000
```

## فحوص الجودة

### Frontend

```powershell
cd apps\atlas-government
npm test
npm run typecheck
npm run build
```

### Backend

```powershell
cd services\atlas-api
pytest
ruff check .
python -m compileall app
```

## حوكمة البيانات

- لا تنتقل البيانات من Staging إلى السجل الوطني دون مراجعة موثقة.
- لا ينشر أي سجل للعامة دون اعتماد رسمي.
- كل تعديل مهم ينشئ سجل تدقيق ونسخة تاريخية.
- ملفات المصدر الأصلية لا تعدل أثناء الاستيراد.
- البيانات الخام والأسرار وملفات البيئة لا ترفع إلى المستودع العام.

## الأمان

يرجى الإبلاغ عن الثغرات وفق [SECURITY.md](SECURITY.md)، وعدم نشر تفاصيل أمنية في Issues العامة.

## المساهمة

راجع [CONTRIBUTING.md](CONTRIBUTING.md) قبل تقديم أي تعديل.

## الترخيص

هذا المستودع حكومي ومصدره متاح للمراجعة، لكنه **ليس مشروعًا مفتوح المصدر** ما لم يصدر تفويض كتابي صريح. راجع [LICENSE](LICENSE).

## الجهة المنفذة

**مركز المعلومات والتوثيق السياحي**  
وزارة السياحة والصناعات التقليدية — دولة ليبيا  
2026
