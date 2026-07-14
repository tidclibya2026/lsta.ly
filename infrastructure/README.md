# البنية التحتية المحلية — منصة أطلس ليبيا السياحي الذكي LSTA

تشغّل هذه الحزمة PostgreSQL 16 مع PostGIS محليًا لأغراض التطوير. لا تتضمن API أو جداول تطبيقات، ولا تنشر أي بيانات إلى Visit Libya.

## 1. إعداد متغيرات البيئة

من جذر المشروع، انسخ ملف المثال إلى ملف محلي غير متعقب:

```powershell
Copy-Item infrastructure/.env.example infrastructure/.env
```

غيّر `POSTGRES_PASSWORD` في `infrastructure/.env` إلى كلمة مرور محلية قوية. لا ترفع الملف إلى Git.

تحقق من إعداد Compose قبل التشغيل:

```bash
docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml config
```

## 2. تشغيل PostGIS

```bash
docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml up -d
```

عند إنشاء مخزن البيانات للمرة الأولى، يفعّل `init.sql` إضافات PostGIS و`pg_trgm` و`pgcrypto` وينشئ مخططات `atlas` و`staging` و`audit` فقط.

## 3. التحقق من الحالة

```bash
docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml ps
```

انتظر حتى تظهر خدمة `lsta-postgres` بالحالة `healthy`.

## 4. عرض السجلات

```bash
docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml logs -f lsta-postgres
```

استخدم `Ctrl+C` للخروج من متابعة السجلات دون إيقاف الخدمة.

## 5. الاتصال بقاعدة البيانات

```bash
docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml exec lsta-postgres psql -U lsta_admin -d lsta
```

إذا عدّلت `POSTGRES_USER` أو `POSTGRES_DB` في `.env`، استخدم القيم الجديدة في أمر الاتصال.

## 6. اختبار PostGIS

داخل جلسة `psql` نفّذ:

```sql
SELECT PostGIS_Version();
```

وللتنفيذ مباشرة من الطرفية:

```bash
docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml exec lsta-postgres psql -U lsta_admin -d lsta -c "SELECT PostGIS_Version();"
```

## 7. إيقاف الخدمة

```bash
docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml stop
```

## 8. حذف الحاوية دون حذف البيانات

يحذف الأمر التالي الحاوية والشبكة، ويُبقي Volume المسمى `lsta_postgres_data`:

```bash
docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml down
```

يمكن استعادة القاعدة وبياناتها لاحقًا بتشغيل `up -d` مجددًا.

## 9. حذف البيانات بالكامل عند الحاجة

> تحذير: هذا الإجراء نهائي ويحذف قاعدة البيانات المحلية كاملة.

```bash
docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml down -v
```

لا تستخدم `-v` إذا كنت تريد الاحتفاظ بالبيانات.
