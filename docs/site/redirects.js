// @ts-check

/**
 * Where every page of the site was before docs/ was split into a User guide
 * and a Developer guide, and where it is now.
 *
 * `legacy-routes.txt` lists every route of the build made before the split, one
 * per line. `redirectTarget` maps one of them to its new route, and
 * `redirects()` turns the whole list into the `redirects` option of
 * `@docusaurus/plugin-client-redirects`. `scripts/check-redirects.js` fails the
 * build when a legacy route has neither a page nor a redirect that lands on one.
 *
 * Client-side redirects (a page with a meta refresh and a script) rather than a
 * Cloudflare Pages `_redirects` file: docs.naas.ai is not served by the
 * `abi-docs` Pages project, so a `_redirects` file here cannot be shown to
 * apply to it. These work wherever the build is hosted.
 */

const fs = require("fs");
const path = require("path");

const LEGACY_ROUTES_FILE = path.join(__dirname, "legacy-routes.txt");

/** Old route -> new route, for pages that were renamed or regrouped. */
const EXACT = {
  "/capabilities/overview": "/user-guide/build/overview",

  // Merged deployment pages.
  "/architecture/deployment-models": "/user-guide/deploy/deployment-models",
  "/capabilities/enterprise/deploy_api_to_production":
    "/user-guide/deploy/production",

  "/capabilities/developer-toolchain/cli": "/user-guide/reference/cli",
  "/capabilities/developer-toolchain/publish_remote_agents":
    "/user-guide/deploy/publish_remote_agents",
  "/capabilities/developer-toolchain/makefile":
    "/developer-guide/toolchain/makefile",
  "/capabilities/developer-toolchain/manage_dependencies":
    "/developer-guide/toolchain/manage_dependencies",
  "/capabilities/developer-toolchain/run_python_scripts":
    "/developer-guide/toolchain/run_python_scripts",
  "/capabilities/developer-toolchain/test_python_scripts":
    "/developer-guide/toolchain/test_python_scripts",
  "/capabilities/developer-toolchain/setup_git_remote":
    "/developer-guide/contributing/setup_git_remote",
  "/capabilities/developer-toolchain/backporting-to-v2":
    "/developer-guide/releasing/backporting-to-v2",

  "/capabilities/enterprise/marketplace-install":
    "/user-guide/build/modules/marketplace/marketplace-install",
  "/capabilities/enterprise/marketplace-overview":
    "/user-guide/build/modules/marketplace/marketplace-overview",
  "/capabilities/enterprise/marketplace-publish":
    "/user-guide/build/modules/marketplace/marketplace-publish",

  // The generated index pages of the old top-level categories.
  "/category/get-started": "/user-guide/get-started",
  "/category/capabilities": "/user-guide/build",
  "/category/agents": "/user-guide/build/agents",
  "/category/knowledge-graph": "/user-guide/build/knowledge-graph",
  "/category/modules": "/user-guide/build/modules",
  "/category/remote-modules-sdk": "/user-guide/build/sdk",
  "/category/applications": "/user-guide/build/applications",
  "/category/enterprise": "/user-guide/deploy",
  "/category/upgrade-to-30": "/user-guide/upgrade",
  "/category/updates": "/user-guide/release-notes",
  "/category/architecture": "/developer-guide/architecture",
  "/category/developer-toolchain": "/developer-guide/toolchain",
  "/category/reference": "/developer-guide/reference",
};

/** Old folder -> new folder, for folders that moved whole. */
const PREFIXES = [
  ["/get-started/", "/user-guide/get-started/"],
  ["/capabilities/agents/", "/user-guide/build/agents/"],
  ["/capabilities/applications/", "/user-guide/build/applications/"],
  ["/capabilities/knowledge-graph/", "/user-guide/build/knowledge-graph/"],
  ["/capabilities/modules/", "/user-guide/build/modules/"],
  ["/capabilities/sdk/", "/user-guide/build/sdk/"],
  ["/capabilities/enterprise/", "/user-guide/deploy/"],
  ["/upgrade/", "/user-guide/upgrade/"],
  ["/updates/", "/user-guide/release-notes/"],
  ["/architecture/", "/developer-guide/architecture/"],
  ["/reference/libraries/", "/developer-guide/reference/libraries/"],
];

/**
 * @param {string} route a route of the site before the split
 * @returns {string | null} its route now, or null when it did not move
 */
function redirectTarget(route) {
  if (Object.prototype.hasOwnProperty.call(EXACT, route)) {
    return EXACT[route];
  }
  for (const [from, to] of PREFIXES) {
    if (route.startsWith(from)) {
      return to + route.slice(from.length);
    }
  }
  return null;
}

/** @returns {string[]} every route of the site before the split */
function legacyRoutes() {
  return fs
    .readFileSync(LEGACY_ROUTES_FILE, "utf8")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

/** @returns {{from: string, to: string}[]} */
function redirects() {
  /** @type {{from: string, to: string}[]} */
  const list = [];
  for (const from of legacyRoutes()) {
    const to = redirectTarget(from);
    if (to !== null) list.push({ from, to });
  }
  return list;
}

module.exports = { legacyRoutes, redirectTarget, redirects };
