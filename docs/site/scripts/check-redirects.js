#!/usr/bin/env node
// @ts-check

/**
 * Fails when a route of the site before the split into a User guide and a
 * Developer guide (legacy-routes.txt) has neither a page nor a redirect that
 * lands on a page in the build.
 *
 * Run it after `npm run build`, from docs/site: `npm run check:redirects`.
 */

const fs = require("fs");
const path = require("path");
const { legacyRoutes, redirectTarget } = require("../redirects");

const BUILD_DIR = path.join(__dirname, "..", "build");

/** The path of a route as the build writes it: no trailing slash, decoded. */
function normalize(route) {
  const decoded = decodeURI(route).replace(/\/+$/, "");
  return decoded === "" ? "/" : decoded;
}

function htmlOf(route) {
  const file = path.join(BUILD_DIR, route === "/" ? "" : route, "index.html");
  return fs.existsSync(file) ? fs.readFileSync(file, "utf8") : null;
}

/** A redirect page of the client-redirects plugin: a meta refresh to its target. */
function redirectsTo(html) {
  const m = html.match(/http-equiv="refresh"\s+content="0;\s*url=([^"]+)"/);
  return m ? normalize(m[1].replace(/&amp;/g, "&")) : null;
}

function main() {
  const sitemapFile = path.join(BUILD_DIR, "sitemap.xml");
  if (!fs.existsSync(sitemapFile)) {
    console.error(`No build found in ${BUILD_DIR}: run \`npm run build\` first.`);
    process.exit(2);
  }
  // Pages of the build. Redirect pages are not in the sitemap.
  const pages = new Set(
    [...fs.readFileSync(sitemapFile, "utf8").matchAll(/<loc>([^<]+)<\/loc>/g)].map(
      (m) => normalize(new URL(m[1]).pathname),
    ),
  );

  const failures = [];
  let kept = 0;
  let redirected = 0;
  for (const route of legacyRoutes().map(normalize)) {
    const html = htmlOf(route);
    if (html !== null && redirectsTo(html) === null && pages.has(route)) {
      kept++;
      continue;
    }
    const target = redirectTarget(route);
    if (target === null) {
      failures.push(`${route}: no page and no redirect`);
    } else if (!pages.has(normalize(target))) {
      failures.push(`${route}: redirects to ${target}, which is not a page`);
    } else if (html === null) {
      failures.push(`${route}: no redirect page in the build (to ${target})`);
    } else if (redirectsTo(html) !== normalize(target)) {
      failures.push(`${route}: the page in the build does not redirect to ${target}`);
    } else {
      redirected++;
    }
  }

  console.log(
    `Legacy routes: ${kept + redirected + failures.length}; ` +
      `still a page: ${kept}; redirected: ${redirected}; failing: ${failures.length}`,
  );
  if (failures.length > 0) {
    for (const f of failures.slice(0, 50)) console.error(`  ${f}`);
    if (failures.length > 50) console.error(`  ... and ${failures.length - 50} more`);
    process.exit(1);
  }
}

main();
