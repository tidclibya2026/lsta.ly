import assert from "node:assert/strict";
import test from "node:test";
import { buildSearchQuery } from "./api/search";

test("يبني معاملات البحث النصي والمكاني مع pagination", () => {
  const query = new URLSearchParams(buildSearchQuery({ q: "المدينة القديمة", source: "all", center_lat: 32.8958, center_lon: 13.1807, radius_meters: 500, limit: 20, offset: 0 }));
  assert.equal(query.get("q"), "المدينة القديمة");
  assert.equal(query.get("radius_meters"), "500");
  assert.equal(query.get("limit"), "20");
});

test("لا يرسل الفلاتر الفارغة إلى Search API", () => {
  const query = new URLSearchParams(buildSearchQuery({ q: "طرابلس", geometry_type: "", has_images: undefined }));
  assert.equal(query.has("geometry_type"), false);
  assert.equal(query.has("has_images"), false);
});
