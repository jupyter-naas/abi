/** Page metadata (title, banner). Dataset paths live in entity manifest.json. */

export const PAGES = {
  workforce: {
    title: "Workforce",
    banner: {
      type: "info",
      enabled: true,
      text: "Demo roster from the personnel graph — headcount, status mix, and age pyramid.",
    },
  },
  graph: {
    title: "Graph",
    banner: {
      type: "info",
      enabled: true,
      text: "Search a person, then choose how many relationship hops to display around that person.",
    },
  },
  logs: {
    title: "Logs",
    banner: {
      type: "info",
      enabled: true,
      text: "Each card is one ledger entry. Rows are facts in subject → property → object form, with URI-only types and properties. The header summarizes who registered what, in plain language.",
    },
  },
  processes: {
    title: "Processes",
    banner: {
      type: "info",
      enabled: true,
      text: "Birth and Working processes mapped to the BFO 7 buckets. Employment continuants remain in PersonnelOntology for HR records.",
    },
  },
};

export const PAGE_IDS = Object.freeze(Object.keys(PAGES));

export const APP_NAME = "Personnel Cockpit";

export const BANNER_ICONS = {
  info: 'M11.25 11.25h.75v4.5h.75M12 8.25h.008M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  warning:
    'M12 9v3.75m0 3.75h.008M10.363 3.591 2.257 17.727A1.5 1.5 0 0 0 3.557 20h16.886a1.5 1.5 0 0 0 1.3-2.273L13.637 3.591a1.5 1.5 0 0 0-2.274 0Z',
  error:
    'M12 9v3.75m0 3.75h.008M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
};
