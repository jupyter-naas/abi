/**
 * The person graph page (graph_page/GraphPage.js, served under the API prefix),
 * for the views that draw with it: a profile's graph and a search's network.
 */
import { API_BASE } from "./config.js";

/** The graph page's stylesheet, scoped by the API under .profile-graph, loaded once. */
function ensureGraphStylesheet() {
  if (document.querySelector("link[data-graph-view-css]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `${API_BASE}/graph-view.css`;
  link.dataset.graphViewCss = "";
  document.head.append(link);
}

/**
 * Mount ``view`` (``{ root, data, config }`` from a graph route) in ``host``,
 * which must carry the ``profile-graph`` class. ``options`` go to
 * ``mountGraphPage``. Returns the page's disposer.
 */
export async function mountGraphView(host, loadView, options = {}) {
  ensureGraphStylesheet();
  const [view, graphModule] = await Promise.all([
    loadView(),
    import(`${API_BASE}/graph-page/GraphPage.js`),
  ]);
  if (!host.isConnected) return () => {};
  graphModule.configureGraph(view.config);
  host.innerHTML = "";
  return graphModule.mountGraphPage(host, view.data, {
    rootId: view.root,
    syncUrl: false,
    ...options,
  });
}
