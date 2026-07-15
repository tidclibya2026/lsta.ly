import assert from "node:assert/strict";
import test from "node:test";
import { resolveMediaCandidates } from "../components/data-display/ImageGallery";

test("يفضل الصورة المحلية ثم الأصلية ثم placeholder", () => {
  const values = resolveMediaCandidates({ local_media_url: "/media/old-tripoli/a.jpg", original_url: "https://example.org/a.jpg", rights_status: "approved_public" }, false);
  assert.equal(values[0], "/media/old-tripoli/a.jpg");
  assert.equal(values[1], "https://example.org/a.jpg");
  assert.match(values[2], /site-image\.svg$/);
});

test("يمنع الصورة غير المعتمدة في static-demo", () => {
  const values = resolveMediaCandidates({ original_url: "https://example.org/a.jpg", rights_status: "pending_review" }, true);
  assert.deepEqual(values, ["/images/placeholders/site-image.svg"]);
});

test("يدعم رابطًا مكسورًا وعدة صور عبر قائمة fallback مستقلة", () => {
  const broken = resolveMediaCandidates("https://expired.example/a.jpg", false);
  const local = resolveMediaCandidates({ local_media_url: "/media/b.jpg", rights_status: "approved_internal" }, false);
  assert.equal(broken.length, 2);
  assert.equal(local[0], "/media/b.jpg");
});
