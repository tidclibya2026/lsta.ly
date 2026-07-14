# النموذج الوطني لقاعدة بيانات LSTA — Government Alpha

هذه الحزمة تدير مخطط قاعدة البيانات الوطنية واستيراد المدينة القديمة إلى `staging` فقط. لا تتضمن FastAPI، ولا تنشر إلى Visit Libya، ولا تنقل سجلات إلى `atlas.sites`.

## إنشاء البيئة الافتراضية

من مجلد الخدمة:

```powershell
cd D:\lsta.ly\services\atlas-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## تثبيت المتطلبات

```bash
python -m pip install -r requirements.txt
```

## إعداد الاتصال

انسخ ملف المثال، ثم استبدل `<password>` بكلمة مرور PostgreSQL المحلية:

```powershell
Copy-Item .env.example .env
```

الصيغة:

```env
DATABASE_URL=postgresql+psycopg://lsta_admin:<password>@localhost:5432/lsta
```

ملف `.env` مستبعد من Git.

## تشغيل Alembic

اعرض الإصدار الحالي ثم طبّق migrations:

```bash
python -m alembic current
python -m alembic upgrade head
```

لا تستخدم الحزمة `Base.metadata.create_all`؛ Alembic هو المسار الوحيد لإنشاء الجداول.

## استيراد المدينة القديمة إلى Staging

من مجلد الخدمة:

```bash
python -m app.services.import_old_tripoli_to_staging --geojson ../../data/processed/kml/old_tripoli.geojson --manifest ../../data/processed/kml/old_tripoli_manifest.json
```

يمنع المستورد تكرار `SHA-256`. لإعادة بناء دفعات المصدر نفسه مع الإبقاء على سجل مصدر واحد:

```bash
python -m app.services.import_old_tripoli_to_staging --geojson ../../data/processed/kml/old_tripoli.geojson --manifest ../../data/processed/kml/old_tripoli_manifest.json --force
```

لا يكتب المستورد مطلقًا إلى `atlas.sites`.

## التحقق من الأعداد

داخل `psql`:

```sql
SELECT COUNT(*) FROM staging.import_features;
SELECT COUNT(*) FROM atlas.sites;
SELECT geometry_type, COUNT(*)
FROM staging.import_features
GROUP BY geometry_type
ORDER BY geometry_type;
```

المتوقع: 430 عنصرًا في Staging، وصفر في `atlas.sites`، وتوزيع 135 نقطة و285 خطًا و10 مضلعات.

## الاختبارات والجودة

```bash
python -m compileall .
pytest
ruff check .
```
