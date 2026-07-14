import assert from "node:assert/strict";
import test from "node:test";
import { approximatePolygonArea, convertReviewFeature } from "./old-tripoli-review";

test("converts a point into the institutional review model", () => {
  const result = convertReviewFeature({
    type: "Feature",
    id: "f-1",
    geometry: { type: "Point", coordinates: [13.18, 32.89] },
    properties: { feature_id: "f-1", name_ar: "متحف", description_text: "وصف", image_urls: ["https://example.org/a.jpg"], verification_status: "unverified" },
  });
  assert.equal(result.feature?.properties.name, "متحف");
  assert.equal(result.feature?.properties.review_kind, "موقع سياحي مستقل");
  assert.equal(result.feature?.properties.needs_review, true);
});

test("rejects unsupported geometry without crashing", () => {
  const result = convertReviewFeature({ geometry: { type: "MultiPoint", coordinates: [] }, properties: {} });
  assert.equal(result.feature, null);
  assert.deepEqual(result.issues, ["unsupported_geometry:MultiPoint"]);
});

test("handles missing properties and estimates polygon area", () => {
  const result = convertReviewFeature({ geometry: { type: "Polygon", coordinates: [[[13, 32], [13.01, 32], [13.01, 32.01], [13, 32]]] }, properties: {} }, 4);
  assert.equal(result.feature?.id, "OLD-TRIPOLI-UNKNOWN-5");
  assert.ok((result.feature?.properties.approximate_area_m2 ?? 0) > 0);
  assert.ok(result.issues.includes("missing_name"));
  assert.ok(approximatePolygonArea([]) === 0);
});
