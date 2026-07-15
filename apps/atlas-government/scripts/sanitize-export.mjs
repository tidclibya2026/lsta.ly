import { existsSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { extname, join, relative } from "node:path";

const out = new URL("../out/", import.meta.url).pathname.replace(/^\/(.:)/, "$1");
const privateReview = join(out, "data", "review");
if (existsSync(privateReview)) rmSync(privateReview, { recursive: true, force: true });

const forbiddenExtensions = new Set([".kml", ".kmz", ".env", ".sqlite", ".db"]);
const forbiddenText = ["localhost:8000", "internal_notes", "reviewer_id"];
const violations = [];
function walk(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const full = join(directory, entry.name);
    if (entry.isDirectory()) walk(full);
    else {
      const path = relative(out, full);
      if (forbiddenExtensions.has(extname(entry.name).toLowerCase()) || entry.name === ".env") violations.push(path);
      if (/\.(?:html|js|json|txt|xml|geojson)$/i.test(entry.name)) {
        const contents = readFileSync(full, "utf8");
        for (const pattern of forbiddenText) if (contents.includes(pattern)) violations.push(`${path}: ${pattern}`);
      }
    }
  }
}
walk(out);
if (violations.length) throw new Error(`Unsafe static export:\n${violations.join("\n")}`);
console.log("Static export security scan passed.");
