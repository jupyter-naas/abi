import { mountPage as mountDashboardPage } from "../components/pages/dashboard/DashboardPage.js";
import { mountPage as mountProcessesPage } from "../components/pages/processes/ProcessesPage.js";
import { mountPage as mountLogsPage } from "../components/pages/logs/LogsPage.js?v=11";

// The graph page belongs to the people module (a person's 7-bucket graph is
// people intelligence, not HR); the personnel module serves it under this
// app's API prefix, so it loads from there.
const GRAPH_PAGE_URL = "/api/personnel-cockpit/graph-page/GraphPage.js";

async function mountGraphPage(el, ctx) {
  const { mountPage } = await import(GRAPH_PAGE_URL);
  return mountPage(el, ctx);
}

const PAGE_MOUNTS = {
  dashboard: mountDashboardPage,
  graph: mountGraphPage,
  processes: mountProcessesPage,
  logs: mountLogsPage,
};

export const PAGE_IDS = Object.freeze(Object.keys(PAGE_MOUNTS));

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
