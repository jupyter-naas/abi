/**
 * Canonical client route: /{entitySlug}/{pageId}
 * SPA fallback: api/dev_server.py serves index.html for these paths.
 */
export { PAGE_IDS, mountPageFor, isRegisteredPage } from "../../lib/registry.js";
