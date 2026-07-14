# سجل التغييرات — LSTA

يعتمد هذا السجل أسلوبًا مبسطًا متوافقًا مع Semantic Versioning.

## [0.1.0-government-alpha] — 2026-07-14

### أضيف

- بوابة حكومية باستخدام Next.js وTypeScript.
- نظام تصميم حكومي عربي RTL.
- خريطة MapLibre GL JS مع أدوات التحكم والطبقات.
- مستورد KML/KMZ مع GeoJSON وCSV وJSON وتقارير الجودة.
- Docker وPostgreSQL/PostGIS.
- مخططات `atlas` و`staging` و`audit`.
- استيراد 430 عنصرًا من طبقة المدينة القديمة طرابلس إلى Staging.
- دورة مراجعة Technical / GIS / Data / Final.
- بوابة المراجعة الوطنية مع البحث والفلاتر والترقية المنضبطة.
- محرك جودة البيانات.
- أول سجل وطني تجريبي: `LSTA-OLD-TRIPOLI-000001`.
- Site Profile Engine والخصائص والوثائق والإصدارات والتدقيق.
- Spatial Relationship Engine مع ST_DWithin والمسافات المترية.
- عشرة مرشحين لعلاقات مكانية بحالة `pending_review`.
- FastAPI وواجهات Registry وReview وSpatial.
- اختبارات Backend وFrontend وفحوص TypeScript وRuff وBuild.

### ضوابط الإصدار

- لا نشر إلى Visit Libya.
- لا ترقية تلقائية لسجلات إضافية.
- لا تضمين للبيانات الخام أو الأسرار.
- الإصدار مخصص للتطوير والمراجعة الحكومية الداخلية.

### مخطط لما بعد الإصدار

- National Search Engine.
- Metadata Catalog.
- Publishing Engine.
- OIDC/Keycloak بدل صلاحيات Header المؤقتة.
- إدارة الوسائط والتخزين المؤسسي.
- التكامل الانتقائي مع Visit Libya.
