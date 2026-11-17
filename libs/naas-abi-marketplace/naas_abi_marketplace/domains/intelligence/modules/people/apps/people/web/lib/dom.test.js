import assert from "node:assert/strict";
import { it } from "node:test";

// config.js (imported by dom.js) reads the page's <meta> at import.
globalThis.document ??= { querySelector: () => null, documentElement: { dataset: {} } };
const { safeHref } = await import("./dom.js");
const { SECTION_RENDERERS } = await import("../components/profile/sections.js");

it("keeps links to http(s) URLs", () => {
  assert.equal(safeHref("https://example.com/a?b=1"), "https://example.com/a?b=1");
  assert.equal(safeHref(" HTTP://example.com "), "HTTP://example.com");
  for (const value of [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    " javascript:alert(1)",
    "java\tscript:alert(1)",
    "data:text/html,<script>1</script>",
    "vbscript:x",
    "//example.com",
    "/relative",
    "",
    null,
    undefined,
  ]) {
    assert.equal(safeHref(value), "", String(value));
  }
});

it("keeps mailto: and tel: to contacts the server built", () => {
  assert.equal(safeHref("mailto:a@example.com", { contact: true }), "mailto:a@example.com");
  assert.equal(safeHref("tel:+3312", { contact: true }), "tel:+3312");
  assert.equal(safeHref("mailto:a@example.com"), "");
  assert.equal(safeHref("javascript:alert(1)", { contact: true }), "");
});

it("renders graph-sourced links only when they are web URLs", () => {
  const certifications = SECTION_RENDERERS.certifications(
    [
      { name: "A", credential_url: "javascript:alert(document.domain)" },
      { name: "B", credential_url: "https://cert.example.com/b" },
    ],
    [],
  );
  assert.ok(!certifications.includes("javascript:"));
  assert.ok(certifications.includes('href="https://cert.example.com/b"'));

  const sources = SECTION_RENDERERS.sources([
    { label: "Bad", url: "javascript:alert(1)" },
    { label: "Good", url: "https://example.com/source" },
  ]);
  assert.ok(!sources.includes('href="javascript:'));
  assert.ok(sources.includes('href="https://example.com/source"'));
});
