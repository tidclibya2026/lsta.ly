-- تهيئة PostgreSQL/PostGIS المحلية لمنصة أطلس ليبيا السياحي الذكي LSTA.
-- يُنفّذ هذا الملف مرة واحدة فقط عند إنشاء Volume جديد وفارغ.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS atlas;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS audit;

-- استعلامات تحقق اختيارية (للتشغيل اليدوي فقط):
-- SELECT PostGIS_Version();
-- SELECT extname, extversion FROM pg_extension WHERE extname IN ('postgis', 'pg_trgm', 'pgcrypto');
-- SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('atlas', 'staging', 'audit');
