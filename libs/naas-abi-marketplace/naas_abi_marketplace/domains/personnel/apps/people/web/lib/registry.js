/**
 * What exists. Configuration picks from this and nothing else.
 *
 * Adding a page or a profile section means adding a renderer here and to the
 * matching list in config_loader.py, in the same change.
 */

import { mountHome } from "../components/pages/home/HomePage.js";
import { mountOntology } from "../components/pages/ontology/OntologyPage.js";
import { mountProfile } from "../components/pages/profile/ProfilePage.js";
import { mountResults } from "../components/pages/results/ResultsPage.js";
import { REGISTERED_SECTION_IDS } from "../components/profile/sections.js";

const PAGE_MOUNTS = {
  home: mountHome,
  results: mountResults,
  profile: mountProfile,
  ontology: mountOntology,
};

export const REGISTERED_PAGE_IDS = Object.freeze(Object.keys(PAGE_MOUNTS));
export { REGISTERED_SECTION_IDS };

export function mountPage(pageId, view, context) {
  const mount = PAGE_MOUNTS[pageId] || PAGE_MOUNTS.home;
  return mount(view, context);
}
