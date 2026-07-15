import assert from "node:assert/strict";
import test from "node:test";
import { buildDiscoveryQuery, normalizeDiscoveryError } from "./api/discovery";

test("يبني استعلام الاكتشاف مع pagination والفلاتر المكانية", () => {
  const query = new URLSearchParams(buildDiscoveryQuery({ q: "المدينة القديمة", source: "all", radius_meters: 500, limit: 20, offset: 0, empty: "", missing: undefined }));
  assert.equal(query.get("q"), "المدينة القديمة");
  assert.equal(query.get("radius_meters"), "500");
  assert.equal(query.has("missing"), false);
  assert.equal(query.has("empty"), false);
});

test("يوحد رسالة أخطاء API", () => {
  assert.equal(normalizeDiscoveryError(new Error("network")), "network");
  assert.match(normalizeDiscoveryError(null), /محرك البحث/);
});
