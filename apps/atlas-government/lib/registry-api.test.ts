import assert from "node:assert/strict";
import test from "node:test";
import { buildRegistryQuery } from "./api/registry";

test("يبني فلاتر السجل مع pagination ويتجاهل القيم الفارغة", () => {
  const query = new URLSearchParams(buildRegistryQuery({ search: "السرايا", verification_status: "approved", publication_status: "", limit: 25, offset: 0 }));
  assert.equal(query.get("search"), "السرايا");
  assert.equal(query.get("verification_status"), "approved");
  assert.equal(query.get("limit"), "25");
  assert.equal(query.has("publication_status"), false);
});

test("يبني معاملات البحث المكاني دون تحميل بيانات غير مطلوبة", () => {
  const query = new URLSearchParams(buildRegistryQuery({ radius_meters: 2000, source: "staging", geometry_type: "Point", has_name: true, limit: 25 }));
  assert.equal(query.get("radius_meters"), "2000");
  assert.equal(query.get("source"), "staging");
  assert.equal(query.get("geometry_type"), "Point");
  assert.equal(query.get("has_name"), "true");
  assert.equal(query.get("limit"), "25");
});
