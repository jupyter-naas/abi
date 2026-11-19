/**
 * Where the app is served.
 *
 * The X module serves the app at `/app-remote/<grant>/applications.x/x_proxy/`,
 * where the grant is per session, so no build can know the path. The export is
 * built with this placeholder as Next's `basePath` (`next.config.js`), and the
 * module's ASGI app (`x_proxy/app.py`) replaces it with the request's
 * `root_path` in every HTML, script, style and payload it serves. So the
 * placeholder below, like every `<Link>` href and `_next/` URL, reaches the
 * browser as the real path. Never build a URL from this string in any other way
 * (split it, or compare against a part of it): only the whole string is
 * rewritten.
 */
export const APP_BASE = "/__x_proxy_app_root__";
