/** Page metadata (title, banner). Dataset paths live in entity manifest.json. */

export const PAGES = {
  workforce: {
    title: "Workforce",
    banner: {
      type: "info",
      enabled: true,
      text: "Demo roster from the personnel graph: headcount, job families, and status mix.",
    },
  },
  graph: {
    title: "Graph",
    banner: {
      type: "info",
      enabled: true,
      text: "Distance counts hops from the selected person, who roots the graph. 1 is what they bear or carry: acts of working, roles, missions, skills, profile document. 2 is what those acts reach: organization, site, temporal region, contract, remuneration. 3 is the instants bounding each temporal region.",
    },
  },
  processes: {
    title: "Processes",
    banner: {
      type: "info",
      enabled: true,
      text: "Acts of Working and Studying mapped to the BFO 7 buckets. Employment continuants remain in PersonnelOntology for HR records.",
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
