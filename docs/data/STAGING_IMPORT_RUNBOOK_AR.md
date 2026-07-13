# دليل تشغيل الاستيراد المرحلي لبيانات الأطلس

## الغرض
يحدد هذا الدليل المسار الرسمي لاستقبال ملفات Excel الخاصة بطبقات أطلس ليبيا السياحي، وفحصها، وتوثيق مشكلاتها، ثم اعتمادها قبل نقلها إلى قاعدة البيانات الوطنية.

## المبادئ الحاكمة
1. يمنع الاستيراد المباشر إلى جداول الإنتاج.
2. يحتفظ النظام بالصف الأصلي كاملًا داخل `raw_payload`.
3. ترتبط كل دفعة استيراد ببصمة SHA-256 لمنع إعادة تحميل الملف نفسه دون قصد.
4. لا يتم دمج السجلات المشتبه بتكرارها آليًا.
5. لا ينشر أي سجل إلى Visit Libya إلا بعد الاعتماد البشري.
6. أي تعديل بعد الاعتماد يجب أن يدخل في السجل التاريخي.

## ترتيب التشغيل

### 1. تجهيز قاعدة البيانات
نفذ ملفات الترحيل بالترتيب:

```bash
psql "$DATABASE_URL" -f database/migrations/001_national_atlas_schema.sql
psql "$DATABASE_URL" -f database/migrations/002_staging_import_pipeline.sql
```

### 2. تثبيت المتطلبات

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r tools/requirements.txt
```

على Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r tools\requirements.txt
```

### 3. فحص تجريبي دون قاعدة بيانات

```bash
python tools/import_atlas_xlsx.py \
  "أطلس_ليبيا_السياحي_2026_طبقة_الفنادق.xlsx" \
  --layer hotels \
  --dry-run
```

يعرض الأمر عدد الصفوف وبصمة الملف وعدد مشكلات الجودة المكتشفة، ولا يكتب أي بيانات.

### 4. الاستيراد إلى Staging

```bash
python tools/import_atlas_xlsx.py \
  "أطلس_ليبيا_السياحي_2026_طبقة_الفنادق.xlsx" \
  --layer hotels \
  --database-url "$DATABASE_URL" \
  --submitted-by "فريق بيانات مركز المعلومات والتوثيق السياحي"
```

القيم المسموح بها في `--layer`:

- `hotels`
- `resorts_villages`
- `restaurants`
- `cafes`
- `thematic_layers`

## مراحل حالة الدفعة

| الحالة | المعنى |
|---|---|
| uploaded | تم تسجيل الملف |
| profiled | تم تحميل الصفوف وإجراء الفحص الأولي |
| validated | اجتازت القواعد الآلية |
| needs_review | توجد مسائل تحتاج مراجعة بشرية |
| approved | اعتمدت الدفعة |
| rejected | رفضت مع توثيق السبب |
| promoted | نقلت السجلات المعتمدة إلى النموذج الوطني |

## الاستعلامات التشغيلية

### ملخص جودة الدفعات

```sql
SELECT *
FROM staging.v_batch_quality_summary
ORDER BY submitted_at DESC;
```

### المشكلات غير المعالجة

```sql
SELECT
  b.source_file_name,
  r.source_row_number,
  r.name_ar_raw,
  v.rule_code,
  v.severity,
  v.message_ar,
  v.suggested_action_ar
FROM staging.validation_results v
JOIN staging.tourism_sites_raw r ON r.staging_id = v.staging_id
JOIN staging.import_batches b ON b.batch_id = r.batch_id
WHERE v.is_resolved = false
ORDER BY
  CASE v.severity
    WHEN 'critical' THEN 1
    WHEN 'error' THEN 2
    WHEN 'warning' THEN 3
    ELSE 4
  END,
  b.source_file_name,
  r.source_row_number;
```

## قواعد الاعتماد الأولية

لا تعتمد الدفعة عندما يوجد واحد من الآتي:

- خط عرض أو طول غير صالح وغير معالج.
- اسم موقع مفقود.
- مصدر مرجعي مفقود.
- معرف مصدري مكرر داخل الدفعة.
- اشتباه تكرار لم يراجع بشريًا.

يسمح بقبول سجل بلا بلدية فقط عندما يتم إسناد البلدية مكانيًا باستخدام حدود إدارية معتمدة ثم يراجعها موظف مخول.

## الفصل بين الأطلس وVisit Libya

قاعدة الأطلس هي المرجع الوطني المؤسسي. منصة Visit Libya لا تقرأ جداول `staging` إطلاقًا، بل تستهلك فقط الواجهة أو الـView المخصصة للسجلات المعتمدة والمنشورة للعامة.
