/**
 * What exists. Configuration picks from this and nothing else.
 *
 * Adding a page or a profile section means adding a renderer here and to the
 * matching list in config_loader.py, in the same change.
 */

// Load only the requested page. In particular, the ontology canvas and layout
// engine must not delay a directory that never draws them.
const PAGE_LOADERS = {
  home: () => import("../components/pages/home/HomePage.js").then((m) => m.mountHome),
  results: () => import("../components/pages/results/ResultsPage.js").then((m) => m.mountResults),
  profile: () => import("../components/pages/profile/ProfilePage.js").then((m) => m.mountProfile),
  ontology: () => import("../components/pages/ontology/OntologyPage.js").then((m) => m.mountOntology),
};

export const REGISTERED_PAGE_IDS = Object.freeze(Object.keys(PAGE_LOADERS));

/** Start the active page's module requests while the shell is still loading. */
export function preloadPage(pageId) {
  return (PAGE_LOADERS[pageId] || PAGE_LOADERS.home)();
}

export async function mountPage(pageId, view, context) {
  const mount = await preloadPage(pageId);
  return mount(view, context);
}
