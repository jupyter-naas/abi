import { mountPage as mountDashboardPage } from "../components/pages/dashboard/DashboardPage.js";
import { mountPage as mountGraphPage } from "../components/pages/graph/GraphPage.js";
import { mountPage as mountProcessesPage } from "../components/pages/processes/ProcessesPage.js";
import { mountPage as mountLogsPage } from "../components/pages/logs/LogsPage.js?v=10";

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
