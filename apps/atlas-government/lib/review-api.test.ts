import assert from "node:assert/strict";
import test from "node:test";
import { buildReviewQuery } from "./api/review";

test("يبني فلاتر API مع pagination دون القيم الفارغة", () => {
  const query = new URLSearchParams(buildReviewQuery({ geometry_type: "Point", review_status: "", has_images: true, limit: 25, offset: 50 }));
  assert.equal(query.get("geometry_type"), "Point");
  assert.equal(query.get("has_images"), "true");
  assert.equal(query.get("limit"), "25");
  assert.equal(query.get("offset"), "50");
  assert.equal(query.has("review_status"), false);
});
