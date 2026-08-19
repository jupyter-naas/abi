import { PAGE_IDS } from "./pages.js";
import { mountPage as mountWorkforcePage } from "../components/pages/workforce/WorkforcePage.js";
import { mountPage as mountGraphPage } from "../components/pages/graph/GraphPage.js";
import { mountPage as mountProcessesPage } from "../components/pages/processes/ProcessesPage.js";
import { mountPage as mountLogsPage } from "../components/pages/logs/LogsPage.js";

export { PAGE_IDS };

const PAGE_MOUNTS = {
  workforce: mountWorkforcePage,
  graph: mountGraphPage,
  processes: mountProcessesPage,
  logs: mountLogsPage,
};

/**
 * Mount a page into its section element.
 * @returns {Promise<(() => void) | void>} optional dispose callback
 */
export async function mountPageFor(pageId, el, ctx) {
  const mount = PAGE_MOUNTS[pageId];
  if (!mount) throw new Error(`Unknown page: ${pageId}`);
  return mount(el, ctx);
}

export function isRegisteredPage(pageId) {
  return pageId in PAGE_MOUNTS;
}
