/* ABI Desktop frontend — vanilla JS clone of the Nexus shell. */

const $ = (id) => document.getElementById(id);

/* ---------- lucide icons (paths lifted from lucide-react, as used by Nexus) ---------- */

const ICONS = {
  "message-square": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  "code-xml": '<path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/>',
  waypoints:
    '<circle cx="12" cy="4.5" r="2.5"/><path d="m10.2 6.3-3.9 3.9"/><circle cx="4.5" cy="12" r="2.5"/><path d="M7 12h10"/><circle cx="19.5" cy="12" r="2.5"/><path d="m13.8 17.7 3.9-3.9"/><circle cx="12" cy="19.5" r="2.5"/>',
  blocks:
    '<path d="M10 3v11a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1z"/><path d="M21 9v11a1 1 0 0 1-1 1h-6a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1z"/><path d="M21 3v5a1 1 0 0 1-1 1h-6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1z"/><path d="M10 18v3a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1z"/>',
  settings:
    '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  "panel-left": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  "arrow-up": '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
  square: '<rect width="18" height="18" x="3" y="3" rx="2"/>',
  bot: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  folder:
    '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
  "chevron-right": '<path d="m9 18 6-6-6-6"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  save: '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
  "file-plus":
    '<path d="M4 22h14a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v4"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M3 15h6"/><path d="M6 12v6"/>',
  "folder-plus":
    '<path d="M12 10v6"/><path d="M9 13h6"/><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  pencil:
    '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
  trash:
    '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
  terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
  "chevron-up": '<path d="m18 15-6-6-6 6"/>',
  "refresh-cw":
    '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  server:
    '<rect width="20" height="8" x="2" y="2" rx="2" ry="2"/><rect width="20" height="8" x="2" y="14" rx="2" ry="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.01" y1="18" y2="18"/>',
  cpu:
    '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  cloud:
    '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>',
  "hard-drive":
    '<line x1="22" x2="2" y1="12" y2="12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><line x1="6" x2="6.01" y1="16" y2="16"/><line x1="10" x2="10.01" y1="16" y2="16"/>',
  wifi: '<path d="M12 20h.01"/><path d="M2 8.82a15 15 0 0 1 20 0"/><path d="M5 12.859a10 10 0 0 1 14 0"/><path d="M8.5 16.429a5 5 0 0 1 7 0"/>',
  "wifi-off":
    '<path d="M12 20h.01"/><path d="M8.5 16.429a5 5 0 0 1 7 0"/><path d="M5 12.859a10 10 0 0 1 5.17-2.69"/><path d="M19 12.859a10 10 0 0 0-2.007-1.523"/><path d="M2 8.82a15 15 0 0 1 4.177-2.643"/><path d="M22 8.82a15 15 0 0 0-11.288-3.764"/><path d="m2 2 20 20"/>',
  "chevron-down": '<path d="m6 9 6 6 6-6"/>',
  wrench:
    '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  "loader-circle": '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
  "external-link": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  "scroll-text":
    '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
};

function icon(name, size = 18) {
  return (
    `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
    `stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">` +
    `${ICONS[name] || ""}</svg>`
  );
}

function mountIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon, Number(el.dataset.size || 18)) + el.innerHTML;
    delete el.dataset.icon;
  });
}

/* ---------- state ---------- */

const SECTION_META = {
  chat: { title: "Chat", panel: "chat-panel" },
  code: { title: "Code", panel: "code-panel" },
  graph: { title: "Knowledge Graph", panel: "graph-panel" },
  events: { title: "Events", panel: "events-panel" },
  settings: { title: "Settings", panel: "settings-panel" },
};

const SECTION_VIEWS = ["chat", "code", "graph", "events", "settings"];

const DEFAULT_SECTION = "chat";

/** Rail hash slugs; `ide` is an alias for the Code section. */
const SECTION_HASH_ALIASES = { ide: "code" };

const SETTINGS_TABS = ["general", "servers", "models"];

function sectionToHashSlug(section, settingsTab = null) {
  if (section === "settings" && settingsTab && settingsTab !== "general") {
    return `settings/${settingsTab}`;
  }
  return section;
}

function parseSectionHash(rawHash) {
  const hash = (rawHash || "").replace(/^#/, "").trim().toLowerCase();
  if (!hash) {
    return { section: DEFAULT_SECTION, settingsTab: null, valid: false };
  }

  const parts = hash.split("/").filter(Boolean);
  let slug = parts[0];
  if (SECTION_HASH_ALIASES[slug]) slug = SECTION_HASH_ALIASES[slug];

  if (!SECTION_META[slug]) {
    return { section: DEFAULT_SECTION, settingsTab: null, valid: false };
  }

  let settingsTab = null;
  if (slug === "settings" && parts.length > 1) {
    settingsTab = parts[1];
    if (!SETTINGS_TABS.includes(settingsTab)) settingsTab = "general";
  }

  return { section: slug, settingsTab, valid: true };
}

function setSectionHash(section, settingsTab = null, { replace = false } = {}) {
  const slug = sectionToHashSlug(section, settingsTab);
  const target = `#${slug}`;
  if (location.hash === target) return;
  const scrollY = window.scrollY;
  const method = replace ? "replaceState" : "pushState";
  history[method](null, "", target);
  window.scrollTo(0, scrollY);
}

function applySectionHash({ replaceMissing = false } = {}) {
  const parsed = parseSectionHash(location.hash);
  if (!parsed.valid) {
    if (replaceMissing || !location.hash) {
      history.replaceState(null, "", `#${DEFAULT_SECTION}`);
    }
    switchSection(DEFAULT_SECTION, { updateHash: false });
    return;
  }

  switchSection(parsed.section, { updateHash: false });
  if (parsed.section === "settings" && parsed.settingsTab) {
    switchSettingsTab(parsed.settingsTab, { updateHash: false });
  }
}

function onSectionHashChange() {
  applySectionHash();
}

const ACTIVE_CONTEXT_SPARQL =
  "PREFIX abid: <http://ontology.naas.ai/abi/desktop#>\n" +
  "PREFIX abi: <http://ontology.naas.ai/abi/>\n" +
  "SELECT ?kind ?section ?agent ?harness ?bucketLabel ?modelRef ?label ?site WHERE {\n" +
  "  {\n" +
  "    GRAPH ?g {\n" +
  "      ?route a abid:SectionRoute ;\n" +
  "             abid:forSection ?section ;\n" +
  "             abid:harnessAgent ?agent .\n" +
  "      BIND(\"route\" AS ?kind)\n" +
  "      OPTIONAL { ?route abid:usesHarness ?harness . }\n" +
  "      OPTIONAL { ?route abid:mapsToBfoProcess ?bucket . }\n" +
  "    }\n" +
  "    OPTIONAL {\n" +
  "      GRAPH <http://ontology.naas.ai/abi/desktop#system> {\n" +
  "        ?bucket <http://www.w3.org/2000/01/rdf-schema#label> ?bucketLabel .\n" +
  "      }\n" +
  "    }\n" +
  "  }\n" +
  "  UNION\n" +
  "  {\n" +
  "    GRAPH ?g {\n" +
  "      ?m a abi:LanguageModel ;\n" +
  "         abi:modelRef ?modelRef ;\n" +
  "         abi:hostedAt ?site .\n" +
  "      BIND(\"model\" AS ?kind)\n" +
  "      OPTIONAL { ?m <http://www.w3.org/2000/01/rdf-schema#label> ?label . }\n" +
  "    }\n" +
  "  }\n" +
  "} ORDER BY ?kind ?section ?modelRef";

const SAMPLE_QUERIES = [
  { name: "All triples", query: "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 50" },
  {
    name: "Entity types & counts",
    query: "SELECT ?type (COUNT(*) AS ?count) WHERE {\n  ?s a ?type\n} GROUP BY ?type ORDER BY DESC(?count)",
  },
  {
    name: "Recent chats",
    query:
      "PREFIX abid: <http://ontology.naas.ai/abi/desktop#>\nSELECT ?chat ?title WHERE {\n  ?chat a abid:Chat ; abid:title ?title .\n} LIMIT 20",
  },
  {
    name: "BFO7 routes (active context)",
    query:
      "PREFIX abid: <http://ontology.naas.ai/abi/desktop#>\nSELECT ?section ?agent ?harness ?bucketLabel WHERE {\n  GRAPH ?g {\n    ?route a abid:SectionRoute ;\n           abid:forSection ?section ;\n           abid:harnessAgent ?agent .\n    OPTIONAL { ?route abid:usesHarness ?harness . }\n    OPTIONAL { ?route abid:mapsToBfoProcess ?bucket . }\n  }\n  OPTIONAL {\n    GRAPH <http://ontology.naas.ai/abi/desktop#system> {\n      ?bucket <http://www.w3.org/2000/01/rdf-schema#label> ?bucketLabel .\n    }\n  }\n} ORDER BY ?section",
  },
  {
    name: "Language models (active context)",
    query:
      "PREFIX abi: <http://ontology.naas.ai/abi/>\nSELECT ?modelRef ?label ?site WHERE {\n  GRAPH ?g {\n    ?m a abi:LanguageModel ;\n       abi:modelRef ?modelRef ;\n       abi:hostedAt ?site .\n    OPTIONAL { ?m <http://www.w3.org/2000/01/rdf-schema#label> ?label . }\n  }\n} ORDER BY ?modelRef",
  },
];

const state = {
  section: "chat",
  panelOpen: true,
  chats: { chat: [], code: [] },
  activeChat: { chat: null, code: null },
  streaming: { chat: false, code: false },
  expandedDirs: new Set(),
  integrations: [],
  modelProviders: [],
  settingsTab: "general",
  settingsDraft: null,
  health: null,
  workspaceStatus: null,
  workspaces: null,
  workspaceMenuOpen: false,
  doctorReport: null,
  settings: null,
  showHiddenFiles: false,
  fileIndex: { files: [], truncated: false },
  composers: {
    chat: {
      fileChips: [],
      modelChip: null,
      mention: null,
      routerSuggestions: [],
      selectedAgent: null,
      agentMenuOpen: false,
      modelMenuOpen: false,
    },
    code: {
      fileChips: [],
      modelChip: null,
      mention: null,
      routerSuggestions: [],
      selectedAgent: null,
      agentMenuOpen: false,
      modelMenuOpen: false,
    },
  },
  agents: { chat: [], code: [] },
  graphTab: "overview",
  graphView: "brain",
  graphOverview: null,
  graphEvents: null,
  selectedEventId: null,
  pendingGraphFocus: null,
  graphNetwork: null,
  graphNodesDataset: null,
  graphEdgesDataset: null,
  graphSelectedNodeId: null,
  graphSearchQuery: "",
  graphSearchMatchIndex: 0,
  graphEnabledBuckets: null,
  graphBuckets: null,
};

const BFO_BUCKET_TINTS = {
  process: "#FADBD8",
  temporal: "#D5F5E3",
  material: "#D6EAF8",
  site: "#D5F5E3",
  quality: "#EAECEE",
  information: "#FDEBD0",
  role: "#E8DAEF",
};

const DEFAULT_BFO_BUCKETS = [
  { id: "process", label: "Process (WHAT)", subtitle: "Events, activities", color: "#C0392B" },
  { id: "temporal", label: "Temporal (WHEN)", subtitle: "Time periods", color: "#148F77" },
  { id: "material", label: "Material (WHO)", subtitle: "People, orgs", color: "#2980B9" },
  { id: "site", label: "Site (WHERE)", subtitle: "Locations", color: "#27AE60" },
  { id: "quality", label: "Quality (HOW IT IS)", subtitle: "Attributes", color: "#717D7E" },
  { id: "information", label: "Information (HOW WE KNOW)", subtitle: "Data, documents", color: "#D68910" },
  { id: "role", label: "Role (WHY)", subtitle: "Roles, capabilities", color: "#7D3C98" },
];

const BFO_BUCKET_SHORT_LABELS = {
  process: "Process",
  temporal: "Temporal",
  material: "Material",
  site: "Site",
  quality: "Quality",
  information: "Information",
  role: "Role",
};

const GRAPH_VIEWS = new Set(["brain", "abox", "tbox", "full"]);

const CHAT_BFO_GROUPS = new Set([
  "chat_process",
  "chat_temporal",
  "chat_participant",
  "chat_site",
  "chat_storage",
  "chat_role",
  "chat_quality",
]);

const GRAPH_UNBUCKETED_COLOR = {
  background: "#64748b",
  border: "#475569",
  highlight: { background: "#94a3b8", border: "#64748b" },
};

const GRAPH_DIMMED_NODE_COLOR = {
  background: "rgba(100,116,139,0.18)",
  border: "rgba(100,116,139,0.28)",
  highlight: { background: "rgba(100,116,139,0.28)", border: "rgba(100,116,139,0.38)" },
};

const GRAPH_DIMMED_EDGE_COLOR = {
  color: "rgba(100,116,139,0.12)",
  highlight: "rgba(100,116,139,0.2)",
};

const routerDebounce = { chat: null, code: null };

/* IDE state: Monaco tabs, preview mode, terminal. */
const ide = {
  editor: null,
  monacoReady: null,
  tabs: [], // { path, model, savedVersionId }
  activePath: null,
  selectedDir: "",
  dropHoverPath: null,
  fileTreeDragDepth: 0,
  viewMode: "code",
  treeInput: null, // { mode: "new-file"|"new-folder"|"rename", dirPath, entry }
  terminal: { term: null, fit: null, socket: null, open: false, height: 220 },
};

/* ---------- api ---------- */

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status}: ${body}`);
  }
  return response.json();
}

/* ---------- toast ---------- */

let toastTimer = null;

function showToast(message, kind = "info") {
  const host = $("toast-host");
  if (!host) return;
  host.textContent = message;
  host.className = `toast toast-${kind} visible`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => host.classList.remove("visible"), 4000);
}

/* ---------- shell: sections + panel ---------- */

function switchSection(section, { updateHash = true } = {}) {
  const meta = SECTION_META[section];
  if (!meta) return;

  state.section = section;
  document.querySelectorAll(".rail-btn[data-section]").forEach((b) => {
    b.classList.toggle("active", b.dataset.section === section);
  });
  SECTION_VIEWS.forEach((s) => {
    $(`view-${s}`).classList.toggle("hidden", s !== section);
  });
  Object.values(SECTION_META).forEach((m) => $(m.panel).classList.add("hidden"));
  $(meta.panel).classList.remove("hidden");
  $("panel-title").textContent = meta.title;
  $("topbar-title").textContent = meta.title;

  if (section === "chat") {
    renderChatList();
    renderMessagesFor("chat");
    loadComposerSelectors("chat");
  } else if (section === "code") {
    loadTree();
    renderMessagesFor("code");
    loadComposerSelectors("code");
  } else if (section === "graph") {
    refreshGraphStats();
    if (state.graphTab === "overview") {
      loadGraphOverview();
    } else if (state.graphTab === "sparql") {
      runActiveContextQuery();
    } else if (state.graphTab === "tables" && state.graphOverview) {
      renderGraphTables(state.graphOverview.tables);
    }
  } else if (section === "events") {
    loadEvents();
  } else if (section === "settings") {
    loadSettingsView();
  }
  refreshStatusBar();

  if (updateHash) {
    const tab = section === "settings" ? state.settingsTab || "general" : null;
    setSectionHash(section, tab, { replace: section === DEFAULT_SECTION && !location.hash });
  }
}

function togglePanel(force) {
  state.panelOpen = force !== undefined ? force : !state.panelOpen;
  $("panel").classList.toggle("closed", !state.panelOpen);
  $("btn-toggle-panel").classList.toggle("active", state.panelOpen);
}

/* ---------- chats ---------- */

async function loadChats(section) {
  state.chats[section] = await api(`/api/chats?section=${section}`);
  if (!state.activeChat[section] && state.chats[section].length) {
    state.activeChat[section] = state.chats[section][0].id;
  }
  if (section === "chat") renderChatList();
}

function renderChatList() {
  const list = $("chat-list");
  list.innerHTML = "";
  $("chat-list-label").classList.toggle("hidden", state.chats.chat.length === 0);
  for (const chat of state.chats.chat) {
    const item = document.createElement("div");
    item.className = "conv-item" + (chat.id === state.activeChat.chat ? " active" : "");
    const title = document.createElement("span");
    title.className = "conv-title";
    title.textContent = chat.title;
    const del = document.createElement("button");
    del.className = "conv-delete";
    del.innerHTML = icon("x", 11);
    del.title = "Delete";
    del.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(`Delete "${chat.title}"?`)) return;
      await api(`/api/chats/${chat.id}`, { method: "DELETE" });
      if (state.activeChat.chat === chat.id) state.activeChat.chat = null;
      await loadChats("chat");
      renderMessagesFor("chat");
    };
    item.append(title, del);
    item.onclick = () => {
      state.activeChat.chat = chat.id;
      renderChatList();
      renderMessagesFor("chat");
    };
    list.appendChild(item);
  }
}

async function newChat(section) {
  const model = resolveSendModel(section);
  const chat = await api("/api/chats", {
    method: "POST",
    body: JSON.stringify({ section, model: model || null }),
  });
  state.chats[section].unshift(chat);
  state.activeChat[section] = chat.id;
  if (section === "chat") renderChatList();
  renderMessagesFor(section);
  if (state.section === "graph") {
    state.graphEvents = null;
    if (state.graphTab === "overview") loadGraphOverview();
  } else if (state.section === "events") {
    state.graphEvents = null;
    loadEvents();
  }
  return chat;
}

async function ensureChat(section) {
  if (state.activeChat[section]) return state.activeChat[section];
  const chat = await newChat(section);
  return chat.id;
}

/* ---------- messages ---------- */

function messagesContainer(section) {
  return section === "code" ? $("code-messages") : $("messages");
}

function scrollerFor(section) {
  return section === "code" ? $("code-messages-scroll") : $("messages-scroll");
}

async function renderMessagesFor(section) {
  const container = messagesContainer(section);
  const chatId = state.activeChat[section];
  container.innerHTML = "";
  if (!chatId) {
    syncComposerForChat(section);
    container.appendChild(emptyState(section));
    return;
  }
  const messages = await api(`/api/chats/${chatId}/messages`);
  syncComposerForChat(section);
  if (!messages.length) {
    container.appendChild(emptyState(section));
    return;
  }
  for (const message of messages) {
    container.appendChild(
      messageRow(message.role, message.content, message.parts, {
        sources: message.sources || [],
      })
    );
  }
  scrollerFor(section).scrollTop = scrollerFor(section).scrollHeight;
}

function emptyState(section) {
  const div = document.createElement("div");
  div.className = "empty-state";
  div.innerHTML =
    '<img class="empty-logo" src="/static/assets/abi-logo.png" alt="ABI" width="48" height="48" />' +
    `<p>${
      section === "code"
        ? "Hello. Ask the coding agent to build something in your workspace."
        : "Hello. Type a message to get started."
    }</p>`;
  return div;
}

function stripTrailingSources(content) {
  if (!content || typeof content !== "string") return content || "";
  let result = content.replace(
    /\n{1,2}(?:#{1,3}\s*)?(?:\*{1,2})?Sources(?:\*{1,2})?:?\s*\n[\s\S]*$/i,
    ""
  );
  result = result.replace(/(\n+https?:\/\/\S+)+\s*$/, "");
  return result.trimEnd();
}

function extractUrlsFromContent(content) {
  if (!content) return [];
  const urls = new Set();
  const mdLinkRe = /\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g;
  let match;
  while ((match = mdLinkRe.exec(content)) !== null) urls.add(match[2]);
  const stripped = content.replace(/\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, "");
  const bareRe = /https?:\/\/[^\s<>\]\)]+?(?=[\s<>\]\)]|$)/g;
  while ((match = bareRe.exec(stripped)) !== null) urls.add(match[0]);
  return [...urls];
}

function pprintLikeString(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return text || "";
  try {
    return `${JSON.stringify(JSON.parse(trimmed), null, 4)}\n`;
  } catch {
    return text || "";
  }
}

function renderMarkdown(text) {
  if (!text) return "";
  try {
    return marked.parse(text);
  } catch {
    return text;
  }
}

function normalizeToolParts(parts) {
  if (!parts?.length) return [];
  return parts
    .filter((part) => part.type === "tool")
    .map((part, index) => {
      const status =
        part.status === "completed"
          ? "done"
          : part.status === "error"
            ? "error"
            : "running";
      const input =
        typeof part.input === "object"
          ? JSON.stringify(part.input, null, 2)
          : part.input || "";
      return {
        id: part.call_id || `tc-${index}`,
        toolName: part.title ? `${part.tool} · ${part.title}` : part.tool || "tool",
        prefix: "Tool",
        status,
        input,
        output: part.output || "",
      };
    });
}

function toolStatusIcon(status) {
  const span = document.createElement("span");
  span.className = `tool-status-icon ${status}`;
  if (status === "running") {
    span.innerHTML = icon("loader-circle", 11);
  } else if (status === "error") {
    span.innerHTML = icon("x", 11);
  } else {
    span.innerHTML = icon("check", 11);
  }
  return span;
}

function renderToolCallRow(tool) {
  const row = document.createElement("div");
  row.className = "tool-call-row";
  row.dataset.toolId = tool.id;

  const hasDetails = Boolean(tool.input?.trim() || tool.output?.trim());
  const header = document.createElement("button");
  header.type = "button";
  header.className = "tool-call-header" + (hasDetails ? " has-details" : "");
  header.disabled = !hasDetails;

  const statusIcon = toolStatusIcon(tool.status);
  const name = document.createElement("span");
  name.className = "tool-call-name";
  name.textContent = tool.toolName;
  header.append(statusIcon, name);
  if (hasDetails) {
    const chevron = document.createElement("span");
    chevron.className = "chevron";
    chevron.innerHTML = icon("chevron-down", 10);
    header.appendChild(chevron);
  }

  const details = document.createElement("div");
  details.className = "tool-call-details hidden";

  header.onclick = () => {
    if (!hasDetails) return;
    details.classList.toggle("hidden");
    header.querySelector(".chevron")?.classList.toggle("open");
  };

  if (tool.input?.trim()) {
    const inputPre = document.createElement("pre");
    inputPre.textContent = tool.input.trim();
    details.appendChild(inputPre);
  }
  if (tool.output?.trim()) {
    const outputPre = document.createElement("pre");
    outputPre.textContent = pprintLikeString(tool.output).trimEnd();
    details.appendChild(outputPre);
  }

  row.append(header, details);
  return row;
}

function renderToolCallsDropdown(toolCalls, { isProcessing = false, open = true } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "tool-calls-dropdown";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "tool-calls-toggle" + (open ? " open" : "");
  const wrench = document.createElement("span");
  wrench.innerHTML = icon("wrench", 11);
  const label = document.createElement("span");
  label.className = "tool-calls-label";
  const stepsLabel = `${toolCalls.length} step${toolCalls.length !== 1 ? "s" : ""}`;
  label.textContent = isProcessing ? `Processing · ${stepsLabel}` : stepsLabel;
  const chevron = document.createElement("span");
  chevron.className = "chevron";
  chevron.innerHTML = icon("chevron-down", 11);
  toggle.append(wrench, label, chevron);

  const panel = document.createElement("div");
  panel.className = "tool-calls-panel" + (open ? "" : " hidden");
  for (const tool of toolCalls) {
    panel.appendChild(renderToolCallRow(tool));
  }

  toggle.onclick = () => {
    const next = panel.classList.toggle("hidden");
    toggle.classList.toggle("open", !next);
  };

  wrap.append(toggle, panel);
  return wrap;
}

function renderRagSources(sources) {
  const row = document.createElement("div");
  row.className = "msg-sources-rag";
  for (const src of sources) {
    const pill = document.createElement("span");
    pill.className = "source-pill";
    pill.innerHTML = `${icon("file", 10)}<span>${src}</span>`;
    row.appendChild(pill);
  }
  return row;
}

function renderUrlSourcesPanel(urls) {
  const panel = document.createElement("div");
  panel.className = "msg-sources-urls";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "sources-toggle";
  const chevron = document.createElement("span");
  chevron.className = "sources-chevron";
  chevron.innerHTML =
    '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>';
  const title = document.createElement("span");
  title.textContent = `Sources (${urls.length})`;
  toggle.append(chevron, title);

  const list = document.createElement("div");
  list.className = "sources-list hidden";

  toggle.onclick = () => {
    const open = list.classList.toggle("hidden");
    toggle.classList.toggle("open", !open);
    title.textContent = open ? `Sources (${urls.length})` : "Sources";
  };

  urls.forEach((url, index) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "source-url-row";
    const idx = document.createElement("span");
    idx.className = "source-index";
    idx.textContent = String(index + 1);
    const label = document.createElement("span");
    label.className = "source-url";
    label.textContent = url.split("?")[0];
    label.title = url;
    btn.append(idx, label);
    btn.onclick = () => window.open(url, "_blank", "noopener,noreferrer");
    list.appendChild(btn);
  });

  panel.append(toggle, list);
  return panel;
}

function messageRow(role, content, parts, meta = {}) {
  const isUser = role === "user";
  const sources = meta.sources || [];
  const isStreaming = Boolean(meta.isStreaming);

  const row = document.createElement("div");
  row.className = `msg-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = `avatar ${role}`;
  avatar.innerHTML = isUser ? icon("user", 16) : icon("bot", 16);

  const body = document.createElement("div");
  body.className = "msg-body";

  const bubble = document.createElement("div");
  bubble.className = `msg-bubble ${role}`;

  const senderName = document.createElement("div");
  senderName.className = "msg-sender-name";
  senderName.textContent = isUser ? "You" : meta.agentName || "ABI";
  bubble.appendChild(senderName);

  if (!isUser) {
    const toolCalls = normalizeToolParts(parts);
    if (toolCalls.length) {
      bubble.appendChild(renderToolCallsDropdown(toolCalls, { isProcessing, open: isStreaming }));
    }
  }

  const contentDiv = document.createElement("div");
  contentDiv.className = isUser ? "msg-content" : "msg-content markdown-body";
  const displayContent = isUser ? content || "" : stripTrailingSources(content || "");
  if (isUser) {
    contentDiv.textContent = displayContent;
  } else if (displayContent) {
    contentDiv.innerHTML = renderMarkdown(displayContent);
  }
  bubble.appendChild(contentDiv);

  body.appendChild(bubble);

  if (!isUser && sources.length) {
    body.appendChild(renderRagSources(sources));
  }

  if (!isUser && displayContent) {
    const urlSources = extractUrlsFromContent(displayContent);
    if (urlSources.length) {
      body.appendChild(renderUrlSourcesPanel(urlSources));
    }
  }

  row.append(avatar, body);
  return row;
}

/* ---------- streaming ---------- */

function composerIds(section) {
  if (section === "code") {
    return {
      input: "code-input",
      popup: "code-mention-popup",
      chips: "code-chips",
      pill: "code-model-pill",
      picker: "code-model-picker",
      router: "code-router-suggestions",
      agentPicker: "agent-picker-code",
      modelPickerUi: "model-picker-code",
    };
  }
  return {
    input: "input",
    popup: "mention-popup",
    chips: "chips",
    pill: "model-pill",
    picker: "model-picker",
    router: "router-suggestions",
    agentPicker: "agent-picker-chat",
    modelPickerUi: "model-picker-chat",
  };
}

function agentDisplayName(section) {
  const comp = getComposer(section);
  const agents = state.agents[section] || [];
  const selected = agents.find((agent) => agent.id === comp.selectedAgent);
  return selected?.name || (section === "code" ? "Build" : "Plan");
}

function closeSelectorMenus(section, except) {
  const comp = getComposer(section);
  if (except !== "agent") comp.agentMenuOpen = false;
  if (except !== "model") comp.modelMenuOpen = false;
  renderAgentSelector(section);
  renderModelSelector(section);
}

function flattenModelOptions() {
  const rows = [];
  for (const provider of state.modelProviders || []) {
    for (const model of provider.models || []) {
      rows.push({
        value: `${provider.id}/${model.id}`,
        label: `${provider.name} / ${model.name}`,
        disabled: model.supports_tools === false,
      });
    }
  }
  return rows;
}

function renderAgentSelector(section) {
  const host = $(composerIds(section).agentPicker);
  if (!host) return;
  const comp = getComposer(section);
  const agents = state.agents[section] || [];
  const selected =
    agents.find((agent) => agent.id === comp.selectedAgent) ||
    agents.find((agent) => agent.id === (section === "code" ? "build" : "plan")) ||
    agents[0];

  host.innerHTML = "";
  if (!selected) return;

  const pill = document.createElement("button");
  pill.type = "button";
  pill.className = "selector-pill" + (comp.agentMenuOpen ? " open" : "");
  pill.title = `Agent: ${selected.name}`;
  const label = document.createElement("span");
  label.className = "selector-label";
  label.textContent = selected.name;
  const chevron = document.createElement("span");
  chevron.className = "chevron";
  chevron.innerHTML = icon("chevron-down", 13);
  pill.append(label, chevron);
  pill.onclick = (e) => {
    e.stopPropagation();
    comp.agentMenuOpen = !comp.agentMenuOpen;
    if (comp.agentMenuOpen) comp.modelMenuOpen = false;
    renderAgentSelector(section);
    renderModelSelector(section);
  };

  const menu = document.createElement("div");
  menu.className = "selector-menu" + (comp.agentMenuOpen ? "" : " hidden");
  const heading = document.createElement("div");
  heading.className = "selector-menu-heading";
  heading.textContent = "Agents";
  menu.appendChild(heading);

  for (const agent of agents) {
    const item = document.createElement("button");
    item.type = "button";
    item.className =
      "selector-menu-item" + (agent.id === comp.selectedAgent ? " active" : "");
    const avatar = document.createElement("span");
    avatar.className = "item-avatar";
    avatar.innerHTML = icon("bot", 14);
    const text = document.createElement("span");
    text.className = "item-text";
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = agent.name;
    const desc = document.createElement("div");
    desc.className = "item-desc";
    desc.textContent = agent.description || "";
    text.append(title, desc);
    item.append(avatar, text);
    item.onclick = (e) => {
      e.stopPropagation();
      comp.selectedAgent = agent.id;
      comp.agentMenuOpen = false;
      renderAgentSelector(section);
    };
    menu.appendChild(item);
  }

  host.append(pill, menu);
}

function renderModelSelector(section) {
  const host = $(composerIds(section).modelPickerUi);
  if (!host) return;
  const comp = getComposer(section);
  const picker = $(composerIds(section).picker);
  const modelValue = resolveSendModel(section);
  const options = flattenModelOptions();
  const selected =
    options.find((option) => option.value === modelValue) ||
    (modelValue
      ? { value: modelValue, label: modelShortLabel(modelValue), disabled: false }
      : null);

  host.innerHTML = "";
  if (!selected && !options.length) return;

  const pill = document.createElement("button");
  pill.type = "button";
  pill.className = "selector-pill" + (comp.modelMenuOpen ? " open" : "");
  const displayLabel = selected?.label || "Default model";
  pill.title = `Model: ${displayLabel}`;
  const label = document.createElement("span");
  label.className = "selector-label";
  label.textContent = displayLabel;
  const chevron = document.createElement("span");
  chevron.className = "chevron";
  chevron.innerHTML = icon("chevron-down", 13);
  pill.append(label, chevron);
  pill.onclick = (e) => {
    e.stopPropagation();
    comp.modelMenuOpen = !comp.modelMenuOpen;
    if (comp.modelMenuOpen) comp.agentMenuOpen = false;
    renderAgentSelector(section);
    renderModelSelector(section);
  };

  const menu = document.createElement("div");
  menu.className = "selector-menu" + (comp.modelMenuOpen ? "" : " hidden");
  const heading = document.createElement("div");
  heading.className = "selector-menu-heading";
  heading.textContent = "Models";
  menu.appendChild(heading);

  for (const option of options) {
    const item = document.createElement("button");
    item.type = "button";
    item.className =
      "selector-menu-item" +
      (option.value === modelValue ? " active" : "") +
      (option.disabled ? " disabled" : "");
    item.disabled = option.disabled;
    const text = document.createElement("span");
    text.className = "item-text";
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = option.label;
    text.appendChild(title);
    item.appendChild(text);
    item.onclick = (e) => {
      e.stopPropagation();
      if (option.disabled) return;
      picker.value = option.value;
      setChatModel(section, option.value);
      comp.modelMenuOpen = false;
      renderModelSelector(section);
      updateModelPill(section, option.value);
    };
    menu.appendChild(item);
  }

  host.append(pill, menu);
}

async function loadAgents(section) {
  try {
    const data = await api(`/api/agents?section=${section}`);
    state.agents[section] = data.agents || [];
    const comp = getComposer(section);
    if (!comp.selectedAgent) comp.selectedAgent = data.selected || null;
    renderAgentSelector(section);
  } catch {
    state.agents[section] = [];
  }
}

async function loadComposerSelectors(section) {
  await loadAgents(section);
  renderModelSelector(section);
}

function getComposer(section) {
  return state.composers[section];
}

function modelShortLabel(modelValue) {
  if (!modelValue) return "";
  const slash = modelValue.indexOf("/");
  return slash >= 0 ? modelValue.slice(slash + 1) : modelValue;
}

function updateModelPill(section, modelValue) {
  const ids = composerIds(section);
  const pill = $(ids.pill);
  const label = modelShortLabel(modelValue);
  if (!label) {
    pill.classList.add("hidden");
    pill.textContent = "";
    return;
  }
  pill.textContent = `Model: ${label}`;
  pill.classList.remove("hidden");
}

function syncComposerForChat(section) {
  const comp = getComposer(section);
  comp.fileChips = [];
  comp.modelChip = null;
  closeMention(section);
  renderChips(section);

  const chatId = state.activeChat[section];
  const chat = chatId ? state.chats[section].find((c) => c.id === chatId) : null;
  const model = chat?.model || "";
  const picker = $(composerIds(section).picker);
  if (model && [...picker.options].some((o) => o.value === model)) {
    picker.value = model;
  } else {
    picker.value = "";
  }
  updateModelPill(section, model);
  renderModelSelector(section);
}

async function setChatModel(section, modelValue) {
  const ids = composerIds(section);
  const picker = $(ids.picker);
  if (modelValue && [...picker.options].some((o) => o.value === modelValue)) {
    picker.value = modelValue;
  } else if (!modelValue) {
    picker.value = "";
  }
  updateModelPill(section, modelValue);

  const chatId = state.activeChat[section];
  if (!chatId) return;
  const updated = await api(`/api/chats/${chatId}`, {
    method: "PATCH",
    body: JSON.stringify({ model: modelValue || "" }),
  });
  const chat = state.chats[section].find((c) => c.id === chatId);
  if (chat) chat.model = updated.model;
}

function fuzzyMatch(needle, haystack) {
  if (!needle) return true;
  const n = needle.toLowerCase();
  const h = haystack.toLowerCase();
  if (h.includes(n)) return true;
  let i = 0;
  for (const ch of h) {
    if (ch === n[i]) i += 1;
    if (i === n.length) return true;
  }
  return false;
}

function getOllamaModels() {
  const seen = new Set();
  const models = [];

  for (const provider of state.modelProviders || []) {
    if (provider.id !== "ollama") continue;
    for (const model of provider.models || []) {
      const id = model.id;
      if (!id || seen.has(id)) continue;
      seen.add(id);
      models.push({ id, name: model.name || id });
    }
  }

  const ollama = (state.integrations || []).find((item) => item.id === "ollama");
  for (const model of ollama?.models || []) {
    const id = model.name || model.id;
    if (!id || seen.has(id)) continue;
    seen.add(id);
    models.push({ id, name: id });
  }

  return models.sort((a, b) => a.id.localeCompare(b.id));
}

function buildMentionItems(query) {
  const items = [];
  const q = query.toLowerCase();

  if (query.startsWith("ollama:")) {
    const modelQuery = query.slice(7);
    for (const model of getOllamaModels()) {
      if (fuzzyMatch(modelQuery, model.id) || fuzzyMatch(modelQuery, model.name)) {
        items.push({
          type: "model",
          label: model.name || model.id,
          value: `ollama/${model.id}`,
          mention: `@ollama:${model.id}`,
        });
      }
    }
    return items.slice(0, 20);
  }

  for (const path of state.fileIndex.files || []) {
    if (fuzzyMatch(q, path)) {
      items.push({
        type: "file",
        label: path.split("/").pop() || path,
        path,
        mention: `@${path}`,
      });
    }
  }

  for (const model of getOllamaModels()) {
    const mention = `@ollama:${model.id}`;
    if (
      fuzzyMatch(q, model.id) ||
      fuzzyMatch(q, model.name) ||
      fuzzyMatch(q, mention.slice(1)) ||
      fuzzyMatch(q, `ollama:${model.id}`)
    ) {
      items.push({
        type: "model",
        label: model.name || model.id,
        value: `ollama/${model.id}`,
        mention,
      });
    }
  }

  return items.slice(0, 20);
}

function getMentionContext(input) {
  const pos = input.selectionStart ?? input.value.length;
  const before = input.value.slice(0, pos);
  const at = before.lastIndexOf("@");
  if (at === -1) return null;
  const query = before.slice(at + 1);
  if (/\s/.test(query)) return null;
  return { at, query, end: pos };
}

function renderMentionPopup(section) {
  const ids = composerIds(section);
  const popup = $(ids.popup);
  const comp = getComposer(section);
  const mention = comp.mention;
  if (!mention || !mention.open) {
    popup.classList.add("hidden");
    popup.innerHTML = "";
    return;
  }

  popup.classList.remove("hidden");
  popup.innerHTML = "";
  if (!mention.items.length) {
    const empty = document.createElement("div");
    empty.className = "mention-item";
    empty.style.cursor = "default";
    empty.textContent = "No matches";
    popup.appendChild(empty);
    return;
  }

  mention.items.forEach((item, index) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mention-item" + (index === mention.index ? " active" : "");
    btn.dataset.index = String(index);
    const iconEl = document.createElement("span");
    iconEl.className = "mention-icon";
    iconEl.innerHTML = icon(item.type === "model" ? "bot" : "file", 14);
    const label = document.createElement("span");
    label.className = "mention-label";
    label.textContent = item.type === "model" ? item.mention : item.path;
    const hint = document.createElement("span");
    hint.className = "mention-hint";
    hint.textContent = item.type === "model" ? item.label : item.label;
    btn.append(iconEl, label, hint);
    btn.onclick = () => selectMentionItem(section, index);
    popup.appendChild(btn);
  });
}

function openMention(section, input) {
  const ctx = getMentionContext(input);
  const comp = getComposer(section);
  if (!ctx) {
    closeMention(section);
    return;
  }
  const items = buildMentionItems(ctx.query);
  comp.mention = {
    open: true,
    query: ctx.query,
    at: ctx.at,
    end: ctx.end,
    items,
    index: 0,
  };
  renderMentionPopup(section);
}

function closeMention(section) {
  const comp = getComposer(section);
  comp.mention = null;
  renderMentionPopup(section);
}

function selectMentionItem(section, index) {
  const comp = getComposer(section);
  const mention = comp.mention;
  if (!mention || !mention.items[index]) return;
  applyMention(section, mention.items[index]);
}

function applyMention(section, item) {
  const ids = composerIds(section);
  const input = $(ids.input);
  const comp = getComposer(section);
  const mention = comp.mention;
  if (!mention) return;

  const before = input.value.slice(0, mention.at);
  const after = input.value.slice(mention.end);
  input.value = before + after;

  if (item.type === "file") {
    if (!comp.fileChips.some((chip) => chip.path === item.path)) {
      comp.fileChips.push({ type: "file", path: item.path, label: item.label });
    }
  } else if (item.type === "model") {
    comp.modelChip = {
      type: "model",
      value: item.value,
      label: modelShortLabel(item.value),
      mention: item.mention,
    };
    setChatModel(section, item.value);
  }

  closeMention(section);
  renderChips(section);
  autoGrow(input);
  updateSendButton(section);
  input.focus();
}

function renderChips(section) {
  const ids = composerIds(section);
  const row = $(ids.chips);
  const comp = getComposer(section);
  row.innerHTML = "";
  const chips = [...(comp.modelChip ? [comp.modelChip] : []), ...comp.fileChips];
  if (!chips.length) {
    row.classList.add("hidden");
    return;
  }
  row.classList.remove("hidden");
  for (const chip of chips) {
    const el = document.createElement("span");
    el.className = `chip chip-${chip.type}`;
    const label = document.createElement("span");
    label.className = "chip-label";
    label.textContent = chip.type === "model" ? chip.label : chip.path;
    label.title = chip.type === "model" ? chip.value : chip.path;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "chip-remove";
    remove.innerHTML = icon("x", 10);
    remove.onclick = () => removeChip(section, chip);
    el.append(label, remove);
    row.appendChild(el);
  }
}

function removeChip(section, chip) {
  const comp = getComposer(section);
  if (chip.type === "model") {
    comp.modelChip = null;
    setChatModel(section, "");
  } else {
    comp.fileChips = comp.fileChips.filter((c) => c.path !== chip.path);
  }
  renderChips(section);
  updateSendButton(section);
}

function clearComposerChips(section) {
  const comp = getComposer(section);
  comp.fileChips = [];
  comp.modelChip = null;
  renderChips(section);
}

function routerMentionForSuggestion(suggestion) {
  if (!suggestion?.model_ref) return "";
  if (suggestion.hosted_at === "local" && suggestion.model_ref.startsWith("ollama/")) {
    return `@ollama:${suggestion.model_ref.split("/").slice(1).join("/")}`;
  }
  return suggestion.model_ref;
}

function renderRouterSuggestions(section, suggestions = [], intentTags = []) {
  const row = $(composerIds(section).router);
  const comp = getComposer(section);
  comp.routerSuggestions = suggestions;
  if (!row) return;
  row.innerHTML = "";
  if (!suggestions.length) {
    row.classList.add("hidden");
    return;
  }
  row.classList.remove("hidden");
  for (const suggestion of suggestions.slice(0, 3)) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "router-chip";
    btn.title = suggestion.reason || suggestion.model_ref;
    const label = document.createElement("span");
    label.className = "router-chip-label";
    label.textContent = suggestion.label || modelShortLabel(suggestion.model_ref);
    const reason = document.createElement("span");
    reason.className = "router-chip-reason";
    const site = suggestion.hosted_at === "local" ? "local" : "cloud";
    reason.textContent = intentTags.length
      ? `${intentTags.join(", ")} · ${site}`
      : site;
    btn.append(label, reason);
    btn.onclick = () => applyRouterSuggestion(section, suggestion);
    row.appendChild(btn);
  }
}

async function fetchRouterSuggestions(section) {
  const input = $(composerIds(section).input);
  const text = input.value.trim();
  if (!text || text.length < 3) {
    renderRouterSuggestions(section, []);
    return;
  }
  try {
    const data = await api("/api/router/suggest", {
      method: "POST",
      body: JSON.stringify({ text, prefer_local: true }),
    });
    renderRouterSuggestions(section, data.suggestions || [], data.intent_tags || []);
  } catch {
    renderRouterSuggestions(section, []);
  }
}

function scheduleRouterSuggestions(section) {
  clearTimeout(routerDebounce[section]);
  routerDebounce[section] = setTimeout(() => fetchRouterSuggestions(section), 350);
}

function applyRouterSuggestion(section, suggestion) {
  const comp = getComposer(section);
  comp.modelChip = {
    type: "model",
    value: suggestion.model_ref,
    label: suggestion.label || modelShortLabel(suggestion.model_ref),
    mention: routerMentionForSuggestion(suggestion),
  };
  setChatModel(section, suggestion.model_ref);
  renderChips(section);
  renderRouterSuggestions(section, []);
  updateSendButton(section);
}

async function buildPromptText(section, displayText) {
  const comp = getComposer(section);
  if (!comp.fileChips.length) return displayText;

  let apiText = displayText;
  for (const chip of comp.fileChips) {
    try {
      const data = await api(`/api/files/content?path=${encodeURIComponent(chip.path)}`);
      apiText += `\n\n\`\`\`${chip.path}\n${data.content}\n\`\`\``;
    } catch (err) {
      apiText += `\n\n[Could not read ${chip.path}: ${err.message}]`;
    }
  }
  return apiText;
}

function modelSupportsTools(modelRef) {
  if (!modelRef || !modelRef.includes("/")) return true;
  const [providerId, modelId] = modelRef.split("/", 2);
  for (const provider of state.modelProviders || []) {
    if (provider.id !== providerId) continue;
    for (const model of provider.models || []) {
      if (model.id === modelId) return model.supports_tools !== false;
    }
  }
  const ollama = (state.integrations || []).find((item) => item.id === "ollama");
  for (const model of ollama?.models || []) {
    const id = model.name || model.id;
    if (id === modelId) return model.supports_tools !== false;
  }
  return true;
}

function resolveSendModel(section) {
  const comp = getComposer(section);
  if (comp.modelChip?.value) return comp.modelChip.value;
  const picker = $(composerIds(section).picker);
  if (picker.value) return picker.value;
  const chatId = state.activeChat[section];
  const chat = chatId ? state.chats[section].find((c) => c.id === chatId) : null;
  return chat?.model || null;
}

async function sendMessage(section) {
  const input = section === "code" ? $("code-input") : $("input");

  if (state.streaming[section]) {
    await abortChat(section);
    return;
  }

  const text = input.value.trim();
  const comp = getComposer(section);
  if (!text && !comp.fileChips.length) return;

  const chatId = await ensureChat(section);
  const container = messagesContainer(section);
  const scroller = scrollerFor(section);
  const model = resolveSendModel(section);
  if (model && !modelSupportsTools(model)) {
    showToast(
      `${model} does not support agent tools. Pick qwen2.5, llama3.1+, or deepseek-r1.`,
      "error"
    );
    return;
  }
  const displayText = text;
  const apiText = await buildPromptText(section, displayText);

  input.value = "";
  clearComposerChips(section);
  closeMention(section);
  autoGrow(input);
  updateSendButton(section);
  if (container.querySelector(".empty-state")) container.innerHTML = "";
  container.appendChild(messageRow("user", displayText));

  const row = document.createElement("div");
  row.className = "msg-row assistant";

  const avatar = document.createElement("div");
  avatar.className = "avatar assistant";
  avatar.innerHTML = icon("bot", 16);

  const body = document.createElement("div");
  body.className = "msg-body";

  const typing = document.createElement("div");
  typing.className = "typing-indicator";
  typing.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble assistant hidden";

  const senderName = document.createElement("div");
  senderName.className = "msg-sender-name";
  senderName.textContent = agentDisplayName(section);

  const toolCallsHost = document.createElement("div");
  toolCallsHost.className = "tool-calls-host";

  const contentDiv = document.createElement("div");
  contentDiv.className = "msg-content markdown-body";

  const sourcesHost = document.createElement("div");
  sourcesHost.className = "msg-sources-host";

  bubble.append(senderName, toolCallsHost, contentDiv);
  body.append(typing, bubble, sourcesHost);
  row.append(avatar, body);
  container.appendChild(row);
  scroller.scrollTop = scroller.scrollHeight;

  const showPanel = () => {
    typing.remove();
    bubble.classList.remove("hidden");
  };

  setStreaming(section, true);
  const seenTools = new Map();
  const textParts = new Map();
  const seenErrors = new Set();
  let streamSources = [];

  try {
    const payload = {
      text: apiText,
      model: model || null,
      agent: getComposer(section).selectedAgent || null,
    };
    if (section === "code") {
      const tab = activeTab();
      if (tab) {
        payload.open_file = { path: tab.path, content: tab.model.getValue() };
      }
    }
    const response = await fetch(`/api/chats/${chatId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await response.text());

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let event;
        try {
          event = JSON.parse(line.slice(6));
        } catch {
          continue;
        }
        handleStreamEvent(event, {
          showPanel,
          contentDiv,
          toolCallsHost,
          sourcesHost,
          seenTools,
          textParts,
          seenErrors,
          streamSources,
          container,
          scroller,
          isStreaming: true,
        });
      }
    }
  } catch (err) {
    showPanel();
    const errorDiv = document.createElement("div");
    errorDiv.className = "msg-error";
    errorDiv.textContent = `Error: ${err.message}`;
    row.appendChild(errorDiv);
  } finally {
    typing.remove();
    if (!contentDiv.textContent && !toolCallsHost.children.length && bubble.classList.contains("hidden")) {
      row.remove();
    } else if (streamSources.length && !sourcesHost.children.length) {
      sourcesHost.appendChild(renderRagSources(streamSources));
    }
    setStreaming(section, false);
    loadChats(section);
    if (section === "code") {
      loadTree(); // agent may have created files
      refreshOpenTabs();
    }
  }
}

function handleStreamEvent(event, ctx) {
  if (event.type === "text") {
    ctx.showPanel();
    ctx.textParts.set(event.part_id || "_", event.text || "");
    const joined = [...ctx.textParts.values()].join("");
    ctx.contentDiv.innerHTML = renderMarkdown(stripTrailingSources(joined));
  } else if (event.type === "tool") {
    ctx.showPanel();
    const key = event.call_id || `${event.tool}:${event.title}`;
    const status =
      event.status === "completed"
        ? "done"
        : event.status === "error"
          ? "error"
          : "running";
    const input =
      typeof event.input === "object"
        ? JSON.stringify(event.input, null, 2)
        : event.input || "";
    ctx.seenTools.set(key, {
      id: key,
      toolName: event.title ? `${event.tool} · ${event.title}` : event.tool,
      prefix: "Tool",
      status,
      input,
      output: event.output || "",
    });
    const toolCalls = [...ctx.seenTools.values()];
    ctx.toolCallsHost.innerHTML = "";
    ctx.toolCallsHost.appendChild(
      renderToolCallsDropdown(toolCalls, { isProcessing: ctx.isStreaming, open: true })
    );
  } else if (event.type === "sources" && Array.isArray(event.sources)) {
    ctx.streamSources = event.sources;
    ctx.sourcesHost.innerHTML = "";
    if (event.sources.length) {
      ctx.sourcesHost.appendChild(renderRagSources(event.sources));
    }
  } else if (event.type === "reasoning") {
    ctx.showPanel();
    if (!ctx.contentDiv.textContent) {
      ctx.contentDiv.textContent = "Thinking…";
    }
  } else if (event.type === "error") {
    ctx.showPanel();
    if (ctx.seenErrors?.has(event.message)) return;
    ctx.seenErrors?.add(event.message);
    const errorDiv = document.createElement("div");
    errorDiv.className = "msg-error";
    errorDiv.textContent = `Error: ${event.message}`;
    ctx.contentDiv.before(errorDiv);
  } else if (event.type === "complete") {
    ctx.showPanel();
    if (Array.isArray(event.sources) && event.sources.length) {
      ctx.streamSources = event.sources;
      ctx.sourcesHost.innerHTML = "";
      ctx.sourcesHost.appendChild(renderRagSources(event.sources));
    }
    if (event.text) {
      ctx.textParts.clear();
      ctx.contentDiv.innerHTML = renderMarkdown(stripTrailingSources(event.text));
      const urlSources = extractUrlsFromContent(stripTrailingSources(event.text));
      if (urlSources.length) {
        ctx.sourcesHost.appendChild(renderUrlSourcesPanel(urlSources));
      }
    }
  }
  ctx.scroller.scrollTop = ctx.scroller.scrollHeight;
}

function setStreaming(section, on) {
  state.streaming[section] = on;
  updateSendButton(section);
}

function updateSendButton(section) {
  const btn = section === "code" ? $("btn-code-send") : $("btn-send");
  const input = section === "code" ? $("code-input") : $("input");
  const streaming = state.streaming[section];
  const comp = getComposer(section);
  const size = section === "code" ? 14 : 16;
  btn.innerHTML = streaming ? icon("square", size) : icon("arrow-up", size + 2);
  btn.title = streaming ? "Stop" : "Send";
  btn.classList.toggle("stop", streaming);
  btn.classList.toggle(
    "ready",
    !streaming && (input.value.trim().length > 0 || comp.fileChips.length > 0)
  );
}

async function abortChat(section) {
  const chatId = state.activeChat[section];
  if (chatId) await api(`/api/chats/${chatId}/abort`, { method: "POST" });
}

/* ---------- monaco editor + tabs ---------- */

function initMonaco() {
  if (ide.monacoReady) return ide.monacoReady;
  ide.monacoReady = new Promise((resolve) => {
    require.config({ paths: { vs: "/static/vendor/monaco/vs" } });
    require(["vs/editor/editor.main"], () => {
      monaco.editor.defineTheme("abi-dark", {
        base: "vs-dark",
        inherit: true,
        rules: [],
        colors: {
          "editor.background": "#18181b",
          "editor.foreground": "#fafafa",
          "editorCursor.foreground": "#22c55e",
          "editor.lineHighlightBackground": "#1f1f23",
          "editorLineNumber.foreground": "#52525b",
          "editorLineNumber.activeForeground": "#a1a1aa",
          "editor.selectionBackground": "#22c55e40",
          "editor.inactiveSelectionBackground": "#22c55e20",
          "editorWidget.background": "#1c1c1f",
          "editorWidget.border": "#2b2b30",
          "editorGutter.background": "#18181b",
          "scrollbarSlider.background": "#3f3f4644",
          "scrollbarSlider.hoverBackground": "#3f3f4677",
        },
      });
      ide.editor = monaco.editor.create($("monaco-host"), {
        theme: "abi-dark",
        model: null,
        fontSize: 13,
        fontFamily: '"SF Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
        minimap: { enabled: false },
        automaticLayout: true,
        scrollBeyondLastLine: false,
        padding: { top: 10 },
        renderLineHighlight: "line",
        tabSize: 4,
      });
      ide.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveActiveFile);
      resolve();
    });
  });
  return ide.monacoReady;
}

function activeTab() {
  return ide.tabs.find((t) => t.path === ide.activePath) || null;
}

function tabIsDirty(tab) {
  return tab.model.getAlternativeVersionId() !== tab.savedVersionId;
}

function middleTruncate(name, max = 24) {
  if (name.length <= max) return name;
  const head = Math.ceil((max - 1) * 0.6);
  return name.slice(0, head) + "…" + name.slice(-(max - 1 - head));
}

async function openFile(path) {
  if (ide.tabs.some((t) => t.path === path)) {
    activateTab(path);
    return;
  }
  try {
    const { content } = await api(`/api/files/content?path=${encodeURIComponent(path)}`);
    await initMonaco();
    const uri = monaco.Uri.file("/" + path);
    let model = monaco.editor.getModel(uri);
    if (model) model.setValue(content);
    else model = monaco.editor.createModel(content, undefined, uri);
    const tab = { path, model, savedVersionId: model.getAlternativeVersionId(), viewMode: "code" };
    model.onDidChangeContent(() => {
      renderTabs();
      updateBreadcrumb();
      schedulePreview();
    });
    ide.tabs.push(tab);
    activateTab(path);
  } catch (err) {
    alert(`Cannot open file: ${err.message}`);
  }
}

function activateTab(path) {
  const tab = ide.tabs.find((t) => t.path === path);
  if (!tab) return;
  ide.activePath = path;
  ide.viewMode = tab.viewMode;
  ide.editor.setModel(tab.model);
  $("editor-empty").classList.add("hidden");
  renderTabs();
  updateBreadcrumb();
  applyViewMode();
  renderTree();
}

function closeTab(path) {
  const index = ide.tabs.findIndex((t) => t.path === path);
  if (index < 0) return;
  const tab = ide.tabs[index];
  if (tabIsDirty(tab) && !confirm(`Discard unsaved changes in ${tab.path}?`)) return;
  tab.model.dispose();
  ide.tabs.splice(index, 1);
  if (ide.activePath === path) {
    const next = ide.tabs[index] || ide.tabs[index - 1];
    if (next) {
      activateTab(next.path);
    } else {
      ide.activePath = null;
      ide.editor.setModel(null);
      $("editor-empty").classList.remove("hidden");
      renderTabs();
      updateBreadcrumb();
      applyViewMode();
      renderTree();
    }
  } else {
    renderTabs();
  }
}

function renderTabs() {
  const bar = $("editor-tabs");
  bar.innerHTML = "";
  for (const tab of ide.tabs) {
    const el = document.createElement("div");
    el.className = "editor-tab" + (tab.path === ide.activePath ? " active" : "");
    el.title = tab.path;

    const dot = document.createElement("span");
    dot.className = "tab-dirty" + (tabIsDirty(tab) ? " on" : "");

    const name = document.createElement("span");
    name.className = "tab-name";
    name.textContent = middleTruncate(tab.path.split("/").pop());

    const close = document.createElement("button");
    close.className = "tab-close";
    close.innerHTML = icon("x", 11);
    close.title = "Close";
    close.onclick = (e) => {
      e.stopPropagation();
      closeTab(tab.path);
    };

    el.append(dot, name, close);
    el.onclick = () => activateTab(tab.path);
    el.onauxclick = (e) => {
      if (e.button === 1) closeTab(tab.path);
    };
    bar.appendChild(el);
  }
}

function updateBreadcrumb() {
  const tab = activeTab();
  const filename = $("editor-filename");
  const saveBtn = $("btn-save-file");
  if (!tab) {
    filename.textContent = "No file open";
    filename.classList.remove("dirty");
    saveBtn.classList.add("hidden");
    $("view-toggle").classList.add("hidden");
    return;
  }
  filename.textContent = tab.path;
  filename.classList.toggle("dirty", tabIsDirty(tab));
  saveBtn.classList.remove("hidden");
  saveBtn.classList.toggle("dirty", tabIsDirty(tab));

  const toggle = $("view-toggle");
  toggle.classList.toggle("hidden", !previewKind(tab.path));
  toggle.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === ide.viewMode);
  });
}

async function saveActiveFile() {
  const tab = activeTab();
  if (!tab) return;
  await api("/api/files/content", {
    method: "PUT",
    body: JSON.stringify({ path: tab.path, content: tab.model.getValue() }),
  });
  tab.savedVersionId = tab.model.getAlternativeVersionId();
  renderTabs();
  updateBreadcrumb();
  const saveBtn = $("btn-save-file");
  saveBtn.classList.add("saved");
  $("save-label").textContent = "Saved";
  setTimeout(() => {
    saveBtn.classList.remove("saved");
    $("save-label").textContent = "Save";
  }, 2000);
}

/* Re-fetch open tabs after the agent runs; replace clean buffers silently. */
async function refreshOpenTabs() {
  for (const tab of [...ide.tabs]) {
    let content;
    try {
      const data = await api(`/api/files/content?path=${encodeURIComponent(tab.path)}`);
      content = data.content;
    } catch {
      continue; // deleted or unreadable — leave the buffer alone
    }
    if (content !== tab.model.getValue() && !tabIsDirty(tab)) {
      tab.model.setValue(content);
      tab.savedVersionId = tab.model.getAlternativeVersionId();
      renderTabs();
      updateBreadcrumb();
      schedulePreview();
    }
  }
}

/* ---------- preview (html / markdown) ---------- */

function previewKind(path) {
  const ext = path.split(".").pop().toLowerCase();
  if (ext === "html" || ext === "htm") return "html";
  if (ext === "md" || ext === "mdx") return "md";
  return null;
}

function setViewMode(mode) {
  ide.viewMode = mode;
  const tab = activeTab();
  if (tab) tab.viewMode = mode;
  updateBreadcrumb();
  applyViewMode();
}

function applyViewMode() {
  const tab = activeTab();
  const kind = tab ? previewKind(tab.path) : null;
  const mode = kind ? ide.viewMode : "code";
  const host = $("monaco-host");
  const preview = $("preview-pane");
  host.classList.toggle("hidden", mode === "preview" || !tab);
  preview.classList.toggle("hidden", mode === "code" || !kind);
  host.classList.toggle("split", mode === "split");
  preview.classList.toggle("split", mode === "split");
  if (mode !== "code" && kind) renderPreview();
}

let previewTimer = null;
function schedulePreview() {
  if (ide.viewMode === "code") return;
  clearTimeout(previewTimer);
  const tab = activeTab();
  const delay =
    tab && previewKind(tab.path) === "html" && ide.viewMode === "split" ? 150 : 300;
  previewTimer = setTimeout(renderPreview, delay);
}

function renderPreview() {
  const tab = activeTab();
  if (!tab) return;
  const kind = previewKind(tab.path);
  if (!kind) return;
  const pane = $("preview-pane");
  const content = tab.model.getValue();
  if (kind === "html") {
    let frame = pane.querySelector("iframe");
    if (!frame) {
      pane.innerHTML = "";
      frame = document.createElement("iframe");
      frame.className = "preview-frame";
      frame.setAttribute("sandbox", "allow-scripts");
      pane.appendChild(frame);
    }
    frame.srcdoc = content;
  } else {
    let body = pane.querySelector(".markdown-body");
    if (!body) {
      pane.innerHTML = "";
      body = document.createElement("div");
      body.className = "markdown-body";
      pane.appendChild(body);
    }
    body.innerHTML = marked.parse(content);
  }
}

/* ---------- file explorer ---------- */

let treeSequence = 0;

async function loadTree() {
  const tree = $("file-tree");
  const sequence = ++treeSequence;
  const fragment = document.createDocumentFragment();
  const hiddenQuery = state.showHiddenFiles ? "&show_hidden=1" : "";
  expandActiveContextDirs();
  const rootCount = await renderDir("", fragment, 0, hiddenQuery);
  if (sequence !== treeSequence) return; // a newer render superseded this one
  tree.innerHTML = "";
  if (rootCount === 0 && !ide.treeInput) {
    const empty = document.createElement("div");
    empty.className = "file-tree-empty";
    empty.textContent = "Drop files from Finder here";
    fragment.prepend(empty);
  }
  tree.appendChild(fragment);
  if (ide.treeInput && ide.treeInput.mode !== "rename" && ide.treeInput.dirPath === "") {
    tree.prepend(treeInputRow(0));
  }
  focusTreeInput();
}

function expandActiveContextDirs() {
  state.expandedDirs.add("templates");
  state.expandedDirs.add("templates/slides");
  const org = state.settings?.active_org || state.settingsDraft?.active_org;
  const model = state.settings?.active_model || state.settingsDraft?.active_model;
  if (!org || !model) return;
  state.expandedDirs.add(org);
  state.expandedDirs.add(`${org}/${model}`);
}

/* Light refresh of the active highlight without refetching the tree. */
function renderTree() {
  document.querySelectorAll("#file-tree .tree-entry").forEach((el) => {
    el.classList.toggle("active", el.dataset.path === ide.activePath);
  });
}

async function renderDir(path, parent, depth, hiddenQuery = "") {
  const { entries } = await api(
    `/api/files?path=${encodeURIComponent(path)}${hiddenQuery}`
  );
  for (const entry of entries) {
    const row = treeEntryRow(entry, depth);
    parent.appendChild(row);

    if (entry.is_dir) {
      const childContainer = document.createElement("div");
      parent.appendChild(childContainer);
      if (state.expandedDirs.has(entry.path)) {
        if (
          ide.treeInput &&
          ide.treeInput.mode !== "rename" &&
          ide.treeInput.dirPath === entry.path
        ) {
          childContainer.appendChild(treeInputRow(depth + 1));
        }
        await renderDir(entry.path, childContainer, depth + 1, hiddenQuery);
      }
    }
  }
  return entries.length;
}

function treeEntryRow(entry, depth) {
  const div = document.createElement("div");
  div.className = "tree-entry" + (ide.activePath === entry.path ? " active" : "");
  div.dataset.path = entry.path;
  if (entry.is_dir) div.dataset.isDir = "true";
  div.style.paddingLeft = `${4 + depth * 14}px`;

  if (entry.is_dir) {
    const caret = document.createElement("span");
    caret.className = "icon-holder";
    caret.style.transition = "transform 0.15s";
    caret.style.display = "flex";
    if (state.expandedDirs.has(entry.path)) caret.style.transform = "rotate(90deg)";
    caret.innerHTML = icon("chevron-right", 12);
    div.appendChild(caret);
    const folderIcon = document.createElement("span");
    folderIcon.className = "icon";
    folderIcon.style.display = "flex";
    folderIcon.innerHTML = icon("folder", 13);
    div.appendChild(folderIcon);
  } else {
    const spacer = document.createElement("span");
    spacer.style.width = "12px";
    spacer.style.flexShrink = "0";
    div.appendChild(spacer);
    const fileIcon = document.createElement("span");
    fileIcon.className = "icon";
    fileIcon.style.display = "flex";
    fileIcon.innerHTML = icon("file", 13);
    div.appendChild(fileIcon);
  }

  if (ide.treeInput && ide.treeInput.mode === "rename" && ide.treeInput.path === entry.path) {
    div.appendChild(treeInputField(entry.name));
    return div;
  }

  const name = document.createElement("span");
  name.className = "tree-name";
  name.textContent = entry.name;
  div.appendChild(name);

  const actions = document.createElement("span");
  actions.className = "tree-row-actions";
  if (entry.is_dir) {
    actions.append(
      treeActionIcon("file-plus", "New file", () => startTreeInput("new-file", entry.path)),
      treeActionIcon("folder-plus", "New folder", () => startTreeInput("new-folder", entry.path))
    );
  }
  actions.append(
    treeActionIcon("pencil", "Rename", () => startRename(entry)),
    treeActionIcon("trash", "Delete", () => deleteEntry(entry))
  );
  div.appendChild(actions);

  if (entry.is_dir) {
    div.onclick = () => {
      ide.selectedDir = entry.path;
      if (state.expandedDirs.has(entry.path)) state.expandedDirs.delete(entry.path);
      else state.expandedDirs.add(entry.path);
      loadTree();
    };
  } else {
    div.onclick = () => {
      const parent = entry.path.split("/").slice(0, -1).join("/");
      ide.selectedDir = parent;
      openFile(entry.path);
    };
  }
  return div;
}

function treeActionIcon(name, title, onClick) {
  const btn = document.createElement("button");
  btn.className = "tree-action-btn";
  btn.title = title;
  btn.innerHTML = icon(name, 12);
  btn.onclick = (e) => {
    e.stopPropagation();
    onClick();
  };
  return btn;
}

function startTreeInput(mode, dirPath) {
  if (dirPath) state.expandedDirs.add(dirPath);
  ide.treeInput = { mode, dirPath };
  loadTree();
}

function startRename(entry) {
  ide.treeInput = { mode: "rename", path: entry.path, entry };
  loadTree();
}

function treeInputRow(depth) {
  const div = document.createElement("div");
  div.className = "tree-entry input-row";
  div.style.paddingLeft = `${4 + depth * 14}px`;
  const iconSpan = document.createElement("span");
  iconSpan.className = "icon";
  iconSpan.style.display = "flex";
  iconSpan.style.marginLeft = "12px";
  iconSpan.innerHTML = icon(ide.treeInput.mode === "new-folder" ? "folder" : "file", 13);
  div.append(iconSpan, treeInputField(""));
  return div;
}

function treeInputField(initial) {
  const input = document.createElement("input");
  input.className = "tree-inline-input";
  input.value = initial;
  input.spellcheck = false;
  input.onclick = (e) => e.stopPropagation();
  input.onkeydown = (e) => {
    if (e.key === "Enter") commitTreeInput(input.value.trim());
    else if (e.key === "Escape") cancelTreeInput();
  };
  input.onblur = () => cancelTreeInput();
  return input;
}

function focusTreeInput() {
  const input = $("file-tree").querySelector(".tree-inline-input");
  if (input) {
    input.focus();
    const dot = input.value.lastIndexOf(".");
    input.setSelectionRange(0, dot > 0 ? dot : input.value.length);
  }
}

function cancelTreeInput() {
  if (!ide.treeInput) return;
  ide.treeInput = null;
  loadTree();
}

async function commitTreeInput(name) {
  const request = ide.treeInput;
  ide.treeInput = null;
  if (!request || !name) {
    loadTree();
    return;
  }
  try {
    if (request.mode === "new-file") {
      const path = request.dirPath ? `${request.dirPath}/${name}` : name;
      await api("/api/files/content", {
        method: "PUT",
        body: JSON.stringify({ path, content: "" }),
      });
      await openFile(path);
    } else if (request.mode === "new-folder") {
      const path = request.dirPath ? `${request.dirPath}/${name}` : name;
      await api("/api/files/mkdir", { method: "POST", body: JSON.stringify({ path }) });
      state.expandedDirs.add(path);
    } else if (request.mode === "rename") {
      const parent = request.path.split("/").slice(0, -1).join("/");
      const newPath = parent ? `${parent}/${name}` : name;
      if (newPath !== request.path) {
        await api("/api/files/rename", {
          method: "POST",
          body: JSON.stringify({ path: request.path, new_path: newPath }),
        });
        applyPathRename(request.path, newPath, request.entry.is_dir);
      }
    }
  } catch (err) {
    alert(`Operation failed: ${err.message}`);
  }
  loadTree();
}

function applyPathRename(oldPath, newPath, isDir) {
  const remap = (p) => {
    if (p === oldPath) return newPath;
    if (isDir && p.startsWith(oldPath + "/")) return newPath + p.slice(oldPath.length);
    return p;
  };
  for (const tab of ide.tabs) tab.path = remap(tab.path);
  if (ide.activePath) ide.activePath = remap(ide.activePath);
  state.expandedDirs = new Set([...state.expandedDirs].map(remap));
  renderTabs();
  updateBreadcrumb();
}

async function deleteEntry(entry) {
  if (!confirm(`Delete "${entry.path}"?`)) return;
  await api(`/api/files?path=${encodeURIComponent(entry.path)}`, { method: "DELETE" });
  const affected = ide.tabs.filter(
    (t) => t.path === entry.path || (entry.is_dir && t.path.startsWith(entry.path + "/"))
  );
  for (const tab of affected) {
    tab.savedVersionId = tab.model.getAlternativeVersionId(); // drop dirty so close is silent
    closeTab(tab.path);
  }
  loadTree();
}

function dropTargetDir() {
  return ide.dropHoverPath ?? ide.selectedDir ?? "";
}

function clearDropHighlight() {
  const tree = $("file-tree");
  if (!tree) return;
  tree.classList.remove("drop-target");
  ide.dropHoverPath = null;
  tree.querySelectorAll(".tree-entry.drop-hover").forEach((el) => el.classList.remove("drop-hover"));
}

function setDropHoverFolder(folderRow) {
  const path = folderRow?.dataset.path ?? null;
  if (ide.dropHoverPath === path) return;
  clearDropHighlight();
  $("file-tree").classList.add("drop-target");
  ide.dropHoverPath = path;
  if (folderRow) folderRow.classList.add("drop-hover");
}

async function uploadDroppedFiles(fileList, targetDir) {
  const form = new FormData();
  form.append("dir", targetDir);
  let count = 0;
  for (const file of fileList) {
    if (file.name === ".DS_Store") continue;
    form.append("files", file, file.name);
    count++;
  }
  if (!count) {
    showToast("No uploadable files in drop", "error");
    return;
  }
  showToast(`Uploading ${count} file(s)...`, "info");
  const response = await fetch("/api/files/upload", { method: "POST", body: form });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function expandPathDirs(relPath) {
  if (!relPath) return;
  const parts = relPath.split("/");
  parts.pop();
  let acc = "";
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part;
    state.expandedDirs.add(acc);
  }
}

function handleUploadResult(data, targetDir = "", source = "upload") {
  const uploaded = data?.uploaded || [];
  clearDropHighlight();
  if (!uploaded.length) {
    showToast("No files were uploaded", "error");
    return;
  }
  if (targetDir) state.expandedDirs.add(targetDir);
  for (const rel of uploaded) expandPathDirs(rel);
  const verb = source === "import" ? "Imported" : "Uploaded";
  showToast(`${verb} ${uploaded.length} file(s)`, "success");
  loadTree().then(async () => {
    const htmlPath = uploaded.find((p) => /\.html?$/i.test(p));
    if (htmlPath) {
      await openFile(htmlPath);
      if (previewKind(htmlPath)) setViewMode("split");
    }
  });
}

function initFileTreeDrop() {
  const tree = $("file-tree");
  if (!tree) return;

  tree.addEventListener("dragenter", (e) => {
    e.preventDefault();
    e.stopPropagation();
    ide.fileTreeDragDepth += 1;
  });

  tree.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
    const folderRow = e.target.closest('.tree-entry[data-is-dir="true"]');
    if (folderRow) setDropHoverFolder(folderRow);
    else {
      clearDropHighlight();
      tree.classList.add("drop-target");
    }
  });

  tree.addEventListener("dragleave", (e) => {
    e.preventDefault();
    e.stopPropagation();
    ide.fileTreeDragDepth = Math.max(0, ide.fileTreeDragDepth - 1);
    if (ide.fileTreeDragDepth === 0) clearDropHighlight();
  });

  tree.addEventListener("drop", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    ide.fileTreeDragDepth = 0;
    const targetDir = dropTargetDir();
    const files = [...e.dataTransfer.files];
    clearDropHighlight();
    if (!files.length) {
      showToast("No files received — pywebview may handle this drop separately", "info");
      return;
    }
    try {
      const data = await uploadDroppedFiles(files, targetDir);
      handleUploadResult(data, targetDir);
    } catch (err) {
      showToast(`Upload failed: ${err.message}`, "error");
    }
  });
}

/* pywebview Finder drop bridge (see main.py) */
window.__getDropTargetDir = dropTargetDir;
window.__isFileTreeDropActive = () => ide.fileTreeDragDepth > 0;
window.__onUploadComplete = (data, targetDir) =>
  handleUploadResult(data, targetDir || dropTargetDir(), "import");
window.__onUploadFailed = (message) =>
  showToast(`Upload failed: ${String(message).slice(0, 200)}`, "error");

/* ---------- terminal (PTY over WebSocket) ---------- */

function toggleTerminal(force) {
  const panel = $("terminal-panel");
  const open = force !== undefined ? force : !ide.terminal.open;
  ide.terminal.open = open;
  panel.classList.toggle("collapsed", !open);
  panel.style.height = open ? `${ide.terminal.height}px` : "";
  if (open) {
    if (!ide.terminal.term) initTerminal();
    if (!ide.terminal.socket || ide.terminal.socket.readyState > WebSocket.OPEN) {
      connectTerminal();
    }
    requestAnimationFrame(() => fitTerminal());
  }
}

function initTerminal() {
  const term = new Terminal({
    fontSize: 12,
    fontFamily: '"SF Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
    cursorBlink: true,
    theme: {
      background: "#18181b",
      foreground: "#fafafa",
      cursor: "#22c55e",
      selectionBackground: "#22c55e40",
      black: "#18181b",
      brightBlack: "#52525b",
    },
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open($("terminal-host"));
  term.onData((data) => {
    const socket = ide.terminal.socket;
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(data);
  });
  term.onResize(({ cols, rows }) => {
    const socket = ide.terminal.socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "resize", cols, rows }));
    }
  });
  ide.terminal.term = term;
  ide.terminal.fit = fit;
}

function connectTerminal() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${proto}//${location.host}/api/terminal/ws`);
  ide.terminal.socket = socket;
  $("btn-terminal-reconnect").classList.add("hidden");
  socket.onopen = () => {
    fitTerminal();
    ide.terminal.term.focus();
  };
  socket.onmessage = (e) => ide.terminal.term.write(e.data);
  socket.onclose = () => {
    if (ide.terminal.term) {
      ide.terminal.term.write("\r\n\x1b[2m[terminal disconnected]\x1b[0m\r\n");
    }
    $("btn-terminal-reconnect").classList.remove("hidden");
  };
}

function reconnectTerminal() {
  const socket = ide.terminal.socket;
  if (socket && socket.readyState <= WebSocket.OPEN) {
    socket.close();
  }
  ide.terminal.socket = null;
  if (ide.terminal.open) {
    if (!ide.terminal.term) initTerminal();
    connectTerminal();
  }
}

function fitTerminal() {
  if (ide.terminal.fit && ide.terminal.open) {
    try {
      ide.terminal.fit.fit();
    } catch {}
  }
}

function wireTerminalDivider() {
  const divider = $("terminal-divider");
  divider.addEventListener("mousedown", (e) => {
    if (!ide.terminal.open) return;
    e.preventDefault();
    const pane = $("editor-pane");
    const onMove = (ev) => {
      const height = Math.min(
        Math.max(pane.getBoundingClientRect().bottom - ev.clientY, 80),
        pane.clientHeight - 120
      );
      ide.terminal.height = height;
      $("terminal-panel").style.height = `${height}px`;
      fitTerminal();
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

/* ---------- status bar ---------- */

function shortModelLabel(modelRef) {
  if (!modelRef) return "default model";
  const slash = modelRef.indexOf("/");
  return slash >= 0 ? modelRef.slice(slash + 1) : modelRef;
}

function renderStatusBar(status) {
  const gitEl = $("status-git");
  const workspaceEl = $("status-workspace");
  const harnessEl = $("status-harness");
  const harnessDot = $("status-harness-dot");
  const agentEl = $("status-agent");
  const modelEl = $("status-model");
  const cpuEl = $("status-cpu");
  const contextEl = $("status-context");
  if (!gitEl) return;

  if (!status) {
    gitEl.textContent = "—";
    gitEl.title = "Git branch unavailable";
    if (workspaceEl) {
      workspaceEl.textContent = "";
      workspaceEl.title = "Workspace folder";
    }
    harnessEl.textContent = "harness";
    harnessDot.classList.remove("ok");
    agentEl.textContent = "agent —";
    modelEl.textContent = "model —";
    cpuEl.classList.add("hidden");
    contextEl.classList.add("hidden");
    return;
  }

  const branch = status.git_branch;
  gitEl.textContent = branch ? `⎇ ${branch}` : "—";
  gitEl.title = branch
    ? `Git branch: ${branch}`
    : status.workspace_root
      ? "Not a git repository"
      : "No workspace";

  if (workspaceEl) {
    workspaceEl.textContent = status.workspace_name || "workspace";
    workspaceEl.title = status.workspace_root || "Workspace root";
  }

  const harness = status.harness || "opencode";
  harnessEl.textContent = harness;
  harnessEl.title = status.harness_connected
    ? `${harness} connected`
    : `${harness} disconnected`;
  harnessDot.classList.toggle("ok", Boolean(status.harness_connected));
  harnessDot.title = status.harness_connected ? "Connected" : "Disconnected";

  const agent =
    state.section === "code" ? status.code_agent || "build" : status.chat_agent || "plan";
  agentEl.textContent = `agent ${agent}`;
  agentEl.title = `Active agent (${state.section})`;

  const modelLabel = shortModelLabel(status.default_model);
  modelEl.textContent = `model ${modelLabel}`;
  modelEl.title = status.default_model || "Default model from settings";

  if (status.cpu_percent != null) {
    cpuEl.textContent = `CPU ${Math.round(status.cpu_percent)}%`;
    cpuEl.classList.remove("hidden");
  } else {
    cpuEl.classList.add("hidden");
  }

  if (status.context_tokens != null) {
    contextEl.textContent = `ctx ${status.context_tokens}`;
    contextEl.classList.remove("hidden");
  } else {
    contextEl.classList.add("hidden");
  }
}

async function refreshStatusBar() {
  try {
    state.workspaceStatus = await api("/api/workspace/status");
  } catch {
    state.workspaceStatus = null;
  }
  renderStatusBar(state.workspaceStatus);
  return state.workspaceStatus;
}

function wireStatusBar() {
  $("status-git")?.addEventListener("click", async () => {
    const root = state.workspaceStatus?.workspace_root;
    if (!root) return;
    try {
      await navigator.clipboard.writeText(root);
      showToast("Workspace path copied", "info");
    } catch {
      showToast(root, "info");
    }
  });
  $("status-harness")?.addEventListener("click", () => openSettings("servers"));
  $("status-model")?.addEventListener("click", () => openSettings("models"));
}

/* ---------- workspace switcher (IDE folder semantics) ---------- */

function hasNativeFolderPicker() {
  return Boolean(window.pywebview?.api?.pick_workspace_folder);
}

function renderWorkspaceSwitcher() {
  const trigger = $("workspace-switcher");
  const listEl = $("workspace-menu-recent");
  if (!trigger || !listEl) return;

  const active =
    state.workspaces?.active ||
    (state.workspaceStatus
      ? {
          path: state.workspaceStatus.workspace_root,
          name: state.workspaceStatus.workspace_name,
          exists: true,
        }
      : null);

  const fullPath = active?.path || "Workspace root";
  trigger.title = fullPath;

  listEl.innerHTML = "";
  const items = [];
  if (active) items.push(active);
  for (const item of state.workspaces?.recent || []) {
    if (!active || item.path !== active.path) items.push(item);
  }
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "workspace-menu-empty";
    empty.textContent = "No workspaces yet";
    listEl.appendChild(empty);
  }
  for (const item of items) {
    const isActive = Boolean(active && item.path === active.path);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "workspace-menu-item";
    if (!item.exists) btn.classList.add("missing");
    if (isActive) btn.classList.add("active");
    btn.title = item.path;
    btn.dataset.path = item.path;
    const label = document.createElement("span");
    label.className = "workspace-menu-item-name";
    label.textContent = item.name;
    btn.appendChild(label);
    if (isActive) {
      const check = document.createElement("span");
      check.className = "workspace-menu-item-check";
      check.innerHTML = icon("check", 14);
      btn.appendChild(check);
    }
    btn.onclick = () => {
      closeWorkspaceMenu();
      if (item.exists) switchWorkspace(item.path);
      else showOpenFolderModal(item.path);
    };
    listEl.appendChild(btn);
  }

  const browseBtn = $("btn-open-folder-browse");
  if (browseBtn) {
    browseBtn.classList.toggle("hidden", !hasNativeFolderPicker());
  }
}

function positionWorkspaceMenu() {
  const trigger = $("workspace-switcher");
  const menu = $("workspace-menu");
  if (!trigger || !menu) return;
  const rect = trigger.getBoundingClientRect();
  menu.style.top = `${rect.top}px`;
  menu.style.bottom = "auto";
  menu.style.left = `${rect.right + 8}px`;
}

function openWorkspaceMenu() {
  const trigger = $("workspace-switcher");
  const menu = $("workspace-menu");
  const backdrop = $("workspace-menu-backdrop");
  if (!trigger || !menu || !backdrop) return;
  positionWorkspaceMenu();
  menu.classList.remove("hidden");
  backdrop.classList.remove("hidden");
  trigger.setAttribute("aria-expanded", "true");
  state.workspaceMenuOpen = true;
}

function closeWorkspaceMenu() {
  $("workspace-menu")?.classList.add("hidden");
  $("workspace-menu-backdrop")?.classList.add("hidden");
  $("workspace-switcher")?.setAttribute("aria-expanded", "false");
  state.workspaceMenuOpen = false;
}

async function loadWorkspaces() {
  try {
    state.workspaces = await api("/api/workspaces");
  } catch {
    state.workspaces = null;
  }
  renderWorkspaceSwitcher();
  return state.workspaces;
}

async function applyWorkspaceSwitchResult(body) {
  if (body?.settings) {
    state.settings = body.settings;
    if (state.settingsDraft) {
      state.settingsDraft.workspace_root = body.settings.workspace_root;
    }
    const workspaceInput = $("set-workspace");
    if (workspaceInput) workspaceInput.value = body.settings.workspace_root || "";
  }
  if (body?.workspaces) {
    state.workspaces = body.workspaces;
  } else {
    await loadWorkspaces();
  }
  renderWorkspaceSwitcher();

  ide.tabs = [];
  ide.activeTab = null;
  if (ide.monaco) ide.monaco.setValue("");
  $("editor-tabs").innerHTML = "";
  ide.selectedDir = "";

  await Promise.all([
    loadHealth(),
    loadFileIndex(),
    loadModels(),
    refreshDoctorInSettings(),
    refreshStatusBar(),
    refreshGraphStats(),
  ]);
  renderServersTab();
  if (state.section === "code") loadTree();
  if (state.section === "graph" && state.graphTab === "overview") {
    state.graphEvents = null;
    loadGraphOverview();
  } else if (state.section === "events") {
    state.graphEvents = null;
    loadEvents();
  }
  reconnectTerminal();
  refreshWorkspaceEnvPanel();
  showToast(`Workspace: ${state.workspaces?.active?.name || "opened"}`, "info");
}

async function switchWorkspace(path) {
  if (!path) return;
  try {
    const body = await api("/api/workspaces/open", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    await applyWorkspaceSwitchResult(body);
  } catch (err) {
    showToast(err.message || "Failed to open workspace", "error");
  }
}

function showOpenFolderModal(prefill = "") {
  closeWorkspaceMenu();
  const modal = $("open-folder-modal");
  const input = $("open-folder-path");
  const error = $("open-folder-error");
  if (!modal || !input) return;
  input.value = prefill || "";
  error?.classList.add("hidden");
  if (error) error.textContent = "";
  modal.classList.remove("hidden");
  input.focus();
  input.select();
}

function hideOpenFolderModal() {
  $("open-folder-modal")?.classList.add("hidden");
}

async function browseWorkspaceFolderNative() {
  if (!hasNativeFolderPicker()) {
    showToast("Native folder picker is only available in the pywebview app", "info");
    return;
  }
  try {
    const picked = await window.pywebview.api.pick_workspace_folder();
    if (picked) $("open-folder-path").value = picked;
  } catch (err) {
    showToast(err.message || "Folder picker failed", "error");
  }
}

async function submitOpenFolder() {
  const input = $("open-folder-path");
  const error = $("open-folder-error");
  const path = input?.value?.trim();
  if (!path) {
    if (error) {
      error.textContent = "Enter a folder path.";
      error.classList.remove("hidden");
    }
    return;
  }
  try {
    const body = await api("/api/workspaces/open", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    hideOpenFolderModal();
    await applyWorkspaceSwitchResult(body);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Invalid workspace path";
      error.classList.remove("hidden");
    }
  }
}

function wireWorkspaceSwitcher() {
  $("workspace-switcher")?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (state.workspaceMenuOpen) closeWorkspaceMenu();
    else {
      loadWorkspaces().then(() => openWorkspaceMenu());
    }
  });
  $("workspace-menu-backdrop")?.addEventListener("click", closeWorkspaceMenu);
  $("workspace-menu-open-folder")?.addEventListener("click", () => showOpenFolderModal());
  $("btn-open-folder-cancel")?.addEventListener("click", hideOpenFolderModal);
  $("btn-open-folder-submit")?.addEventListener("click", submitOpenFolder);
  $("btn-open-folder-browse")?.addEventListener("click", browseWorkspaceFolderNative);
  $("open-folder-path")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submitOpenFolder();
    }
    if (e.key === "Escape") hideOpenFolderModal();
  });
  window.addEventListener("resize", () => {
    if (state.workspaceMenuOpen) positionWorkspaceMenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.workspaceMenuOpen) closeWorkspaceMenu();
  });
}

/* ---------- graph ---------- */

function switchGraphTab(tab) {
  state.graphTab = tab;
  document.querySelectorAll(".graph-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.graphTab === tab);
  });
  $("graph-tab-overview").classList.toggle("hidden", tab !== "overview");
  $("graph-tab-sparql").classList.toggle("hidden", tab !== "sparql");
  $("graph-tab-tables").classList.toggle("hidden", tab !== "tables");
  if (tab === "overview") {
    loadGraphOverview();
  } else if (tab === "sparql") {
    if (!$("sparql-input").value.trim()) {
      $("sparql-input").value = ACTIVE_CONTEXT_SPARQL;
    }
    runSparql();
  } else if (tab === "tables") {
    if (state.graphOverview) {
      renderGraphTables(state.graphOverview.tables);
    } else {
      loadGraphOverview().then(() => renderGraphTables(state.graphOverview?.tables || []));
    }
  }
  if (state.graphNetwork) {
    setTimeout(() => state.graphNetwork.redraw(), 50);
  }
}

function getGraphBuckets() {
  return state.graphBuckets?.length ? state.graphBuckets : DEFAULT_BFO_BUCKETS;
}

function getGraphBucketById(bucketId) {
  return getGraphBuckets().find((bucket) => bucket.id === bucketId) || null;
}

function getGraphNodeBucketId(node) {
  if (!node) return null;
  return node.bucket_id || node.detail?.bucket_id || null;
}

function getGraphNodeColor(node) {
  if (node.detail?.unknown) {
    return {
      background: "#E5E7EB",
      border: "#9CA3AF",
      highlight: { background: "#F3F4F6", border: "#6B7280" },
      fontColor: "#4B5563",
      shape: "dot",
      borderWidth: 2,
      shapeProperties: { borderDashes: [6, 4] },
    };
  }
  if (node.group === "ai_system") {
    return {
      background: "#1C2833",
      border: "#7D3C98",
      highlight: { background: "#2E4053", border: "#9B59B6" },
      fontColor: "#ffffff",
      shape: "box",
      borderWidth: 3,
      size: 36,
    };
  }
  const bucketId = getGraphNodeBucketId(node);
  const bucket = bucketId ? getGraphBucketById(bucketId) : null;
  if (bucket) {
    const color = bucket.color;
    const isAnchor = node.group === "bfo_anchor";
    const isChatAspect = CHAT_BFO_GROUPS.has(node.group);
    const isProcessNode =
      (state.graphView === "abox" || state.graphView === "brain") &&
      node.group === "chat_process";
    if (isAnchor) {
      return {
        background: color,
        border: color,
        highlight: { background: color, border: color },
        fontColor: "#ffffff",
        shape: "box",
        borderWidth: 2,
      };
    }
    if (isProcessNode) {
      return {
        background: BFO_BUCKET_TINTS[bucketId] || color,
        border: color,
        highlight: { background: color, border: color },
        fontColor: "#1C2833",
        shape: "dot",
        borderWidth: 3,
        size: 22,
      };
    }
    if (isChatAspect) {
      return {
        background: color,
        border: color,
        highlight: { background: color, border: color },
        fontColor: "#ffffff",
        shape: "dot",
        borderWidth: 2,
        size: 14,
      };
    }
    const background = BFO_BUCKET_TINTS[bucketId] || color;
    return {
      background,
      border: color,
      highlight: { background, border: color },
      fontColor: "#1C2833",
      shape: "box",
      borderWidth: 1,
    };
  }
  const palette = GRAPH_UNBUCKETED_COLOR;
  return {
    background: palette.background,
    border: palette.border,
    highlight: palette.highlight || { background: palette.background, border: palette.border },
    fontColor: "#fafafa",
    shape: "dot",
    borderWidth: 2,
  };
}

function getGraphBaseColor(nodeOrGroup) {
  const node = typeof nodeOrGroup === "string" ? { group: nodeOrGroup } : nodeOrGroup;
  const styled = getGraphNodeColor(node);
  return {
    background: styled.background,
    border: styled.border,
    highlight: styled.highlight,
  };
}

function nodePassesGraphBucketFilter(node) {
  if (!state.graphEnabledBuckets || state.graphEnabledBuckets.size === 0) return true;
  const bucketId = getGraphNodeBucketId(node);
  if (!bucketId) return true;
  return state.graphEnabledBuckets.has(bucketId);
}

function nodePassesGraphGroupFilter(node) {
  return nodePassesGraphBucketFilter(node);
}

function getGraphNodeById(nodeId) {
  return state.graphOverview?.nodes?.find((item) => item.id === nodeId) || null;
}

function nodeMatchesGraphSearch(node, query) {
  if (!query) return true;
  const bucket = getGraphBucketById(getGraphNodeBucketId(node));
  const bucketLabel = bucket?.label || "";
  const haystack = `${node.label || ""} ${node.id || ""} ${node.group || ""} ${bucketLabel}`.toLowerCase();
  return haystack.includes(query);
}

function getGraphSearchMatches() {
  const query = state.graphSearchQuery.trim().toLowerCase();
  if (!query || !state.graphOverview?.nodes) return [];
  return state.graphOverview.nodes.filter(
    (node) => nodeMatchesGraphSearch(node, query) && nodePassesGraphGroupFilter(node)
  );
}

function renderGraphBucketFilters() {
  const host = $("graph-bucket-filters");
  if (!host) return;
  host.innerHTML = "";
  host.classList.toggle("hidden", state.graphView === "brain" || state.graphView === "tbox");

  if (state.graphView === "brain" || state.graphView === "tbox") return;

  const bucketIds = getGraphBuckets().map((bucket) => bucket.id);
  if (!state.graphEnabledBuckets) {
    state.graphEnabledBuckets = new Set(bucketIds);
  } else {
    for (const enabled of [...state.graphEnabledBuckets]) {
      if (!bucketIds.includes(enabled)) state.graphEnabledBuckets.delete(enabled);
    }
    for (const bucketId of bucketIds) {
      if (!state.graphEnabledBuckets.has(bucketId)) state.graphEnabledBuckets.add(bucketId);
    }
    if (state.graphEnabledBuckets.size === 0) {
      state.graphEnabledBuckets = new Set(bucketIds);
    }
  }

  const heading = document.createElement("span");
  heading.className = "graph-bucket-filter-heading";
  heading.textContent = "Buckets";
  host.appendChild(heading);

  for (const bucket of getGraphBuckets()) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "graph-bucket-filter";
    btn.dataset.bucketId = bucket.id;
    btn.title = bucket.label;
    btn.classList.toggle("active", state.graphEnabledBuckets.has(bucket.id));
    const swatch = document.createElement("span");
    swatch.className = "graph-bucket-filter-swatch";
    swatch.style.background = bucket.color;
    const label = document.createElement("span");
    label.className = "graph-bucket-filter-label";
    label.textContent = BFO_BUCKET_SHORT_LABELS[bucket.id] || bucket.id;
    btn.append(swatch, label);
    btn.onclick = () => toggleGraphBucketFilter(bucket.id);
    host.appendChild(btn);
  }
}

function switchGraphView(view) {
  if (!GRAPH_VIEWS.has(view) || view === state.graphView) return;
  state.graphView = view;
  document.querySelectorAll(".graph-view-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.graphView === view);
  });
  loadGraphOverview();
}

function getGraphHubNodeId() {
  const hub = state.graphOverview?.nodes?.find(
    (node) => node.group === "ai_system" || node.group === "context"
  );
  return hub?.id || null;
}

function applyGraphLayoutPositions(nodes) {
  return nodes;
}

function applyGraphPhysicsForView() {
  if (!state.graphNetwork) return;
  const brainMode = state.graphView === "brain";
  state.graphNetwork.setOptions({
    physics: {
      enabled: true,
      solver: brainMode ? "repulsion" : "forceAtlas2Based",
      repulsion: brainMode
        ? {
            centralGravity: 0.35,
            springLength: 160,
            springConstant: 0.04,
            nodeDistance: 140,
            damping: 0.45,
          }
        : undefined,
      forceAtlas2Based: brainMode
        ? undefined
        : {
            gravitationalConstant: -60,
            centralGravity: 0.01,
            springLength: 120,
            springConstant: 0.08,
            damping: 0.4,
            avoidOverlap: 0.8,
          },
      stabilization: { iterations: brainMode ? 120 : 150 },
    },
    edges: {
      smooth: brainMode
        ? { enabled: true, type: "curvedCW", roundness: 0.16 }
        : { enabled: true, type: "dynamic" },
    },
  });
  if (brainMode) {
    state.graphNetwork.stabilize(120);
  }
}

function toggleGraphBucketFilter(bucketId) {
  if (!state.graphEnabledBuckets) {
    state.graphEnabledBuckets = new Set(getGraphBuckets().map((bucket) => bucket.id));
  }
  if (state.graphEnabledBuckets.has(bucketId)) {
    if (state.graphEnabledBuckets.size === 1) return;
    state.graphEnabledBuckets.delete(bucketId);
  } else {
    state.graphEnabledBuckets.add(bucketId);
  }
  renderGraphBucketFilters();
  applyGraphVisualState();
  renderGraphNodeList();
  if (state.graphSelectedNodeId) {
    const selected = getGraphNodeById(state.graphSelectedNodeId);
    if (!selected || !nodePassesGraphGroupFilter(selected)) {
      clearGraphNodeSelection();
    }
  }
}

function renderGraphNodeList() {
  const list = $("graph-node-list");
  if (!list) return;
  const query = state.graphSearchQuery.trim();
  const matches = getGraphSearchMatches();
  list.classList.toggle("visible", query.length > 0 && matches.length > 0);
  list.innerHTML = "";
  if (!query || !matches.length) return;

  const header = document.createElement("div");
  header.className = "graph-node-list-header";
  header.textContent = `${matches.length} match${matches.length === 1 ? "" : "es"}`;
  list.appendChild(header);

  const items = document.createElement("div");
  items.className = "graph-node-list-items";
  for (const node of matches) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "graph-node-list-item";
    if (node.id === state.graphSelectedNodeId) btn.classList.add("active");
    btn.textContent = node.label || node.id;
    const group = document.createElement("span");
    group.className = "graph-node-list-group";
    const bucket = getGraphBucketById(getGraphNodeBucketId(node));
    group.textContent = bucket?.label || node.group;
    btn.appendChild(group);
    btn.onclick = () => focusGraphNode(node.id, { openPanel: true });
    items.appendChild(btn);
  }
  list.appendChild(items);
}

function applyGraphSearch() {
  const input = $("graph-search");
  state.graphSearchQuery = input?.value || "";
  const clear = $("graph-search-clear");
  clear?.classList.toggle("hidden", !state.graphSearchQuery);
  state.graphSearchMatchIndex = 0;
  applyGraphVisualState();
  renderGraphNodeList();
}

function jumpGraphSearchMatch(direction = 1) {
  const matches = getGraphSearchMatches();
  if (!matches.length) return;
  state.graphSearchMatchIndex =
    (state.graphSearchMatchIndex + direction + matches.length) % matches.length;
  focusGraphNode(matches[state.graphSearchMatchIndex].id, { openPanel: true });
  renderGraphNodeList();
}

function applyGraphVisualState() {
  if (!state.graphNodesDataset || !state.graphEdgesDataset || !state.graphOverview) return;

  const query = state.graphSearchQuery.trim().toLowerCase();
  const searchActive = query.length > 0;
  const matchIds = new Set(getGraphSearchMatches().map((node) => node.id));
  const nodeUpdates = [];
  const edgeUpdates = [];

  for (const node of state.graphOverview.nodes) {
    const visible = nodePassesGraphGroupFilter(node);
    const matched = !searchActive || matchIds.has(node.id);
    const styled = getGraphNodeColor(node);
    const base = getGraphBaseColor(node);
    const dimmed = !visible || (searchActive && !matched);
    const update = {
      id: node.id,
      hidden: !visible,
      color: dimmed ? GRAPH_DIMMED_NODE_COLOR : base,
      shape: styled.shape,
      ...(styled.size ? { size: styled.size } : {}),
      font: {
        color: dimmed ? "rgba(148,163,184,0.45)" : styled.fontColor,
        bold: node.group === "bfo_anchor" || node.group === "ai_system",
        size: node.group === "ai_system" ? 14 : node.group === "bfo_anchor" ? 12 : 11,
        face: "Inter, Segoe UI, system-ui, sans-serif",
      },
      borderWidth: searchActive && matched && visible ? 3 : styled.borderWidth,
    };
    if (styled.shape === "box") {
      update.shapeProperties = { borderRadius: 0 };
      update.margin = { top: 6, bottom: 6, left: 8, right: 8 };
    }
    nodeUpdates.push(update);
  }

  const visibleNodeIds = new Set(
    state.graphOverview.nodes
      .filter((node) => nodePassesGraphGroupFilter(node))
      .map((node) => node.id)
  );
  for (const edge of state.graphOverview.edges) {
    const edgeVisible =
      visibleNodeIds.has(edge.from) &&
      visibleNodeIds.has(edge.to) &&
      (!searchActive || (matchIds.has(edge.from) && matchIds.has(edge.to)));
    edgeUpdates.push({
      id: edge.id,
      hidden: !edgeVisible,
      color: edgeVisible && searchActive ? { color: "#22c55e", highlight: "#4ade80" } : edgeVisible
        ? { color: "#D5D8DC", highlight: "#D5D8DC" }
        : GRAPH_DIMMED_EDGE_COLOR,
    });
  }

  state.graphNodesDataset.update(nodeUpdates);
  state.graphEdgesDataset.update(edgeUpdates);
}

function getGraphChatAspects(chatId) {
  if (!chatId || !state.graphOverview?.nodes) return [];
  return state.graphOverview.nodes.filter(
    (node) => node.detail?.chat_id === chatId && CHAT_BFO_GROUPS.has(node.group)
  );
}

function getGraphConnectedRelations(nodeId) {
  const relations = [];
  for (const edge of state.graphOverview?.edges || []) {
    if (edge.from === nodeId) {
      const other = getGraphNodeById(edge.to);
      relations.push({
        direction: "out",
        label: edge.label || "related",
        nodeId: edge.to,
        nodeLabel: other?.label || edge.to,
      });
    } else if (edge.to === nodeId) {
      const other = getGraphNodeById(edge.from);
      relations.push({
        direction: "in",
        label: edge.label || "related",
        nodeId: edge.from,
        nodeLabel: other?.label || edge.from,
      });
    }
  }
  return relations;
}

function formatGraphDetailValue(key, value) {
  if (value == null || value === "") return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function focusGraphNode(nodeId, { openPanel = true, animate = true } = {}) {
  if (!state.graphNetwork || !state.graphNodesDataset) return;
  const node = getGraphNodeById(nodeId);
  if (!node || !nodePassesGraphGroupFilter(node)) return;

  state.graphNetwork.selectNodes([nodeId]);
  state.graphNetwork.focus(nodeId, {
    scale: 1.2,
    animation: animate ? { duration: 350, easingFunction: "easeInOutQuad" } : false,
  });
  if (openPanel) selectGraphNode(nodeId);
}

function ensureGraphNetwork() {
  if (state.graphNetwork || typeof vis === "undefined") return;
  const host = $("graph-network-host");
  if (!host) return;
  state.graphNodesDataset = new vis.DataSet([]);
  state.graphEdgesDataset = new vis.DataSet([]);
  state.graphNetwork = new vis.Network(
    host,
    { nodes: state.graphNodesDataset, edges: state.graphEdgesDataset },
    {
      autoResize: true,
      height: "100%",
      width: "100%",
      nodes: {
        shape: "dot",
        size: 16,
        font: { color: "#fafafa", size: 12, face: "Inter, Segoe UI, system-ui, sans-serif" },
        borderWidth: 2,
      },
      edges: {
        width: 1,
        color: { color: "#D5D8DC", highlight: "#D5D8DC" },
        font: { color: "#AAB7B8", size: 9, strokeWidth: 0, align: "middle" },
        smooth: { enabled: true, type: "dynamic" },
      },
      physics: {
        enabled: true,
        solver: "forceAtlas2Based",
        forceAtlas2Based: {
          gravitationalConstant: -60,
          centralGravity: 0.01,
          springLength: 120,
          springConstant: 0.08,
          damping: 0.4,
          avoidOverlap: 0.8,
        },
        stabilization: { iterations: 150 },
      },
      interaction: {
        hover: true,
        tooltipDelay: 150,
        navigationButtons: true,
        keyboard: { enabled: false },
      },
    }
  );
  state.graphNetwork.on("click", (params) => {
    if (params.nodes.length > 0) {
      selectGraphNode(params.nodes[0]);
    } else {
      clearGraphNodeSelection();
    }
  });
}

function selectGraphNode(nodeId) {
  state.graphSelectedNodeId = nodeId;
  const node = getGraphNodeById(nodeId);
  renderGraphNodeDetail(node || null);
  $("graph-detail-panel")?.classList.add("open");
  renderGraphNodeList();
}

function clearGraphNodeSelection() {
  state.graphSelectedNodeId = null;
  state.graphNetwork?.unselectAll();
  renderGraphNodeDetail(null);
  $("graph-detail-panel")?.classList.remove("open");
  renderGraphNodeList();
}

function findGraphNodeIdForIri(iri) {
  if (!iri || !state.graphOverview?.nodes) return null;
  const short = iri.split("/").pop();
  const direct = state.graphOverview.nodes.find((node) => node.detail?.iri === iri);
  if (direct) return direct.id;
  const ontoMatch = state.graphOverview.nodes.find((node) => node.id === `onto:${short}`);
  if (ontoMatch) return ontoMatch.id;
  const anchorMatch = state.graphOverview.nodes.find(
    (node) => node.group === "bfo_anchor" && node.detail?.iri === iri
  );
  return anchorMatch?.id || null;
}

async function loadGraphSubclassDrilldown(host, classIri, currentNode) {
  const section = document.createElement("div");
  section.className = "graph-detail-section";
  const sectionTitle = document.createElement("div");
  sectionTitle.className = "graph-detail-section-title";
  sectionTitle.textContent = "Subclasses";
  section.appendChild(sectionTitle);

  const selectWrap = document.createElement("div");
  selectWrap.className = "graph-subclass-wrap";
  const select = document.createElement("select");
  select.className = "graph-subclass-select";
  select.disabled = true;
  const loading = document.createElement("option");
  loading.value = "";
  loading.textContent = "Loading subclasses…";
  select.appendChild(loading);
  selectWrap.appendChild(select);
  section.appendChild(selectWrap);
  host.appendChild(section);

  try {
    const payload = await api(`/api/graph/subclasses?iri=${encodeURIComponent(classIri)}`);
    select.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = payload.subclasses?.length
      ? "Explore subclasses…"
      : "No direct subclasses";
    select.appendChild(placeholder);
    for (const sub of payload.subclasses || []) {
      const option = document.createElement("option");
      option.value = sub.iri;
      option.textContent = sub.label || sub.iri;
      select.appendChild(option);
    }
    select.disabled = !payload.subclasses?.length;
    select.onchange = () => {
      const iri = select.value;
      if (!iri) return;
      const sub = (payload.subclasses || []).find((item) => item.iri === iri);
      const nodeId = findGraphNodeIdForIri(iri);
      if (nodeId) {
        focusGraphNode(nodeId, { openPanel: true });
      } else {
        renderGraphNodeDetail({
          id: `iri:${iri}`,
          label: select.selectedOptions[0]?.textContent || iri,
          group: "ontology_class",
          detail: { iri, bucket_id: sub?.bucket_id, source: "sparql" },
        });
        $("graph-detail-panel")?.classList.add("open");
      }
      select.value = "";
    };
  } catch (err) {
    select.innerHTML = "";
    const errOpt = document.createElement("option");
    errOpt.value = "";
    errOpt.textContent = err.message || "Failed to load subclasses";
    select.appendChild(errOpt);
  }
}

function renderGraphBfoAspectsTable(host, aspects) {
  if (!Array.isArray(aspects) || !aspects.length) return;
  const section = document.createElement("div");
  section.className = "graph-detail-section";
  const sectionTitle = document.createElement("div");
  sectionTitle.className = "graph-detail-section-title";
  sectionTitle.textContent = "BFO7 aspects";
  section.appendChild(sectionTitle);

  const table = document.createElement("table");
  table.className = "graph-aspects-table";
  const head = table.insertRow();
  for (const column of ["Aspect", "Bucket", "Value", "Property"]) {
    const th = document.createElement("th");
    th.textContent = column;
    head.appendChild(th);
  }
  for (const aspect of aspects) {
    const tr = table.insertRow();
    const aspectCell = tr.insertCell();
    aspectCell.textContent = aspect.aspect || "";
    const bucketCell = tr.insertCell();
    const bucket = getGraphBucketById(aspect.bucket);
    if (bucket) {
      const badge = document.createElement("span");
      badge.className = "graph-detail-bucket-badge";
      badge.textContent = BFO_BUCKET_SHORT_LABELS[bucket.id] || bucket.label;
      badge.style.background = bucket.color;
      bucketCell.appendChild(badge);
    } else {
      bucketCell.textContent = aspect.bucket || "";
    }
    const valueCell = tr.insertCell();
    valueCell.textContent = aspect.label || "";
    const propertyCell = tr.insertCell();
    propertyCell.textContent = aspect.property || "";
  }
  section.appendChild(table);
  host.appendChild(section);
}

function renderGraphNodeDetail(node) {
  const host = $("graph-detail-table");
  if (!host) return;
  if (!node) {
    host.className = "graph-detail-empty";
    host.textContent = "Click a node to inspect properties.";
    return;
  }

  host.className = "";
  host.innerHTML = "";

  const detail = node.detail || {};
  const bucket = getGraphBucketById(detail.bucket_id || getGraphNodeBucketId(node));

  const title = document.createElement("div");
  title.className = "graph-detail-title";
  const heading = document.createElement("h3");
  heading.textContent = node.label || node.id;
  title.appendChild(heading);
  if (bucket) {
    const badge = document.createElement("span");
    badge.className = "graph-detail-bucket-badge";
    badge.textContent = bucket.label;
    badge.style.background = bucket.color;
    title.appendChild(badge);
  } else if (node.group) {
    const badge = document.createElement("span");
    badge.className = "graph-detail-badge";
    badge.textContent = node.group;
    title.appendChild(badge);
  }
  host.appendChild(title);

  const definition = detail.skos_definition || detail.rdfs_comment || "";
  if (definition) {
    const section = document.createElement("div");
    section.className = "graph-detail-section";
    const sectionTitle = document.createElement("div");
    sectionTitle.className = "graph-detail-section-title";
    sectionTitle.textContent = "Definition";
    section.appendChild(sectionTitle);
    const def = document.createElement("div");
    def.className = "graph-detail-definition";
    def.textContent = definition;
    section.appendChild(def);
    host.appendChild(section);
  }

  if (detail.iri && state.graphView !== "brain") {
    loadGraphSubclassDrilldown(host, detail.iri, node);
  }

  if (Array.isArray(detail.bfo_aspects) && detail.bfo_aspects.length) {
    renderGraphBfoAspectsTable(host, detail.bfo_aspects);
  }

  const chatId = detail.chat_id;
  if (chatId && state.graphView !== "brain") {
    const aspects = getGraphChatAspects(chatId).filter((aspect) => aspect.id !== node.id);
    if (aspects.length) {
      const section = document.createElement("div");
      section.className = "graph-detail-section";
      const sectionTitle = document.createElement("div");
      sectionTitle.className = "graph-detail-section-title";
      sectionTitle.textContent = "BFO7 aspects";
      section.appendChild(sectionTitle);
      const list = document.createElement("ul");
      list.className = "graph-detail-relations";
      for (const aspect of aspects) {
        const li = document.createElement("li");
        const bucket = getGraphBucketById(getGraphNodeBucketId(aspect));
        if (bucket) {
          const swatch = document.createElement("span");
          swatch.className = "graph-detail-bucket-badge";
          swatch.textContent = BFO_BUCKET_SHORT_LABELS[bucket.id] || bucket.id;
          swatch.style.background = bucket.color;
          li.appendChild(swatch);
        }
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "graph-detail-rel-node";
        btn.textContent = aspect.label || aspect.id;
        btn.onclick = () => focusGraphNode(aspect.id, { openPanel: true });
        li.appendChild(btn);
        list.appendChild(li);
      }
      section.appendChild(list);
      host.appendChild(section);
    }
  }

  const skipKeys = new Set([
    "can_realize",
    "bucket_id",
    "bucket_label",
    "bucket_color",
    "skos_definition",
    "rdfs_comment",
    "iri",
    "label",
    "bfo_aspects",
    "display_name",
  ]);
  const rows = [
    ["id", node.id],
    ...Object.entries(detail)
      .filter(([key]) => !skipKeys.has(key))
      .map(([key, value]) => [key, formatGraphDetailValue(key, value)]),
  ].filter(([, value]) => value !== "");

  if (detail.iri) {
    rows.unshift(["iri", detail.iri]);
  }

  if (rows.length) {
    const section = document.createElement("div");
    section.className = "graph-detail-section";
    const sectionTitle = document.createElement("div");
    sectionTitle.className = "graph-detail-section-title";
    sectionTitle.textContent = "Properties";
    section.appendChild(sectionTitle);
    const table = document.createElement("table");
    table.className = "graph-detail-table";
    for (const [key, value] of rows) {
      const tr = table.insertRow();
      const th = tr.insertCell();
      th.textContent = key;
      const td = tr.insertCell();
      td.textContent = value;
      td.title = value;
    }
    section.appendChild(table);
    host.appendChild(section);
  }

  if (Array.isArray(detail.can_realize) && detail.can_realize.length) {
    const section = document.createElement("div");
    section.className = "graph-detail-section";
    const sectionTitle = document.createElement("div");
    sectionTitle.className = "graph-detail-section-title";
    sectionTitle.textContent = "Can realize";
    section.appendChild(sectionTitle);
    const tags = document.createElement("div");
    tags.className = "graph-detail-tags";
    for (const processLabel of detail.can_realize) {
      const tag = document.createElement("span");
      tag.className = "graph-detail-tag";
      tag.textContent = processLabel;
      tags.appendChild(tag);
    }
    section.appendChild(tags);
    host.appendChild(section);
  }

  const relations = getGraphConnectedRelations(node.id);
  if (relations.length) {
    const section = document.createElement("div");
    section.className = "graph-detail-section";
    const sectionTitle = document.createElement("div");
    sectionTitle.className = "graph-detail-section-title";
    sectionTitle.textContent = `Relations (${relations.length})`;
    section.appendChild(sectionTitle);
    const list = document.createElement("ul");
    list.className = "graph-detail-relations";
    for (const rel of relations) {
      const li = document.createElement("li");
      const arrow = document.createElement("span");
      arrow.className = "graph-detail-rel-arrow";
      arrow.textContent = rel.direction === "out" ? "→" : "←";
      const label = document.createElement("span");
      label.className = "graph-detail-rel-label";
      label.textContent = rel.label;
      const other = document.createElement("button");
      other.type = "button";
      other.className = "graph-detail-rel-node";
      other.textContent = rel.nodeLabel;
      other.onclick = () => focusGraphNode(rel.nodeId, { openPanel: true });
      li.append(arrow, label, other);
      list.appendChild(li);
    }
    section.appendChild(list);
    host.appendChild(section);
  }
}

function renderGraphEventBucketCell(bucket) {
  const td = document.createElement("td");
  if (!bucket) {
    td.className = "graph-event-cell graph-event-unknown";
    td.textContent = "—";
    return td;
  }
  const status = bucket.status || "unknown";
  td.className = `graph-event-cell graph-event-${status}`;
  const label = bucket.label || "—";
  td.textContent = label;
  td.title = `${status}: ${label}`;
  return td;
}

function focusGraphProcessNode(eventRow) {
  if (!eventRow?.graph_node_id || !state.graphNetwork || !state.graphOverview) return;
  const processNodeId = eventRow.graph_node_id;
  const nodeIds = new Set([processNodeId]);
  for (const edge of state.graphOverview.edges || []) {
    if (edge.from === processNodeId) nodeIds.add(edge.to);
    if (edge.to === processNodeId) nodeIds.add(edge.from);
  }
  const visibleIds = [...nodeIds].filter((nodeId) => {
    const node = getGraphNodeById(nodeId);
    return node && nodePassesGraphGroupFilter(node);
  });
  if (!visibleIds.length) {
    showToast("Process not visible in current graph view", "info");
    return;
  }
  state.graphNetwork.selectNodes(visibleIds);
  focusGraphNode(processNodeId, { openPanel: true, animate: true });
}

function selectProcessEvent(eventRow) {
  state.selectedEventId = eventRow?.id ?? null;
  renderEventsTable(state.graphEvents?.items || []);
  renderEventDetail(eventRow);
}

function openProcessEventInGraph(eventRow) {
  if (!eventRow?.graph_node_id) {
    showToast("No graph node linked to this event", "info");
    return;
  }
  state.pendingGraphFocus = eventRow;
  if (state.section !== "graph") {
    state.graphTab = "overview";
    switchSection("graph");
    return;
  }
  if (!state.graphOverview) {
    loadGraphOverview();
    return;
  }
  state.pendingGraphFocus = null;
  focusGraphProcessNode(eventRow);
}

function renderEventDetail(eventRow) {
  const host = $("events-detail-body");
  const panel = $("events-detail-panel");
  if (!host || !panel) return;
  if (!eventRow) {
    panel.classList.remove("open");
    host.innerHTML = '<div class="graph-detail-empty">Select a row to inspect bucket values.</div>';
    return;
  }
  panel.classList.add("open");
  host.innerHTML = "";
  const title = document.createElement("div");
  title.className = "graph-detail-title";
  const heading = document.createElement("h3");
  heading.textContent = eventRow.process_label || eventRow.process_type || "Process event";
  title.appendChild(heading);
  const badge = document.createElement("span");
  badge.className = "graph-detail-badge";
  badge.textContent = eventRow.process_type || "event";
  title.appendChild(badge);
  host.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "graph-detail-section";
  meta.innerHTML = `<div class="graph-detail-section-title">When</div><div>${eventRow.timestamp || "—"}</div>`;
  host.appendChild(meta);

  const buckets = eventRow.buckets || {};
  const bucketSection = document.createElement("div");
  bucketSection.className = "graph-detail-section";
  const bucketTitle = document.createElement("div");
  bucketTitle.className = "graph-detail-section-title";
  bucketTitle.textContent = "BFO buckets";
  bucketSection.appendChild(bucketTitle);
  const table = document.createElement("table");
  table.className = "graph-aspects-table";
  const head = table.insertRow();
  ["Bucket", "Value", "Status"].forEach((label) => {
    const th = document.createElement("th");
    th.textContent = label;
    head.appendChild(th);
  });
  for (const [bucket, data] of Object.entries(buckets)) {
    const tr = table.insertRow();
    const status = data?.status || "unknown";
    tr.innerHTML = `<td>${bucket}</td><td>${data?.label || "—"}</td><td>${status}</td>`;
  }
  bucketSection.appendChild(table);
  host.appendChild(bucketSection);

  if (eventRow.graph_node_id) {
    const actions = document.createElement("div");
    actions.className = "events-detail-actions";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "settings-btn primary";
    btn.textContent = "View in Graph";
    btn.onclick = () => openProcessEventInGraph(eventRow);
    actions.appendChild(btn);
    host.appendChild(actions);
  }
}

function renderEventsTable(items) {
  const host = $("events-table-host");
  const count = $("events-count");
  if (!host) return;
  host.innerHTML = "";
  const total = state.graphEvents?.total ?? items.length;
  if (count) {
    count.textContent = total ? `${items.length} of ${total}` : "";
  }
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "graph-detail-empty";
    empty.textContent = "No process events yet. Create a chat to record one.";
    host.appendChild(empty);
    return;
  }
  const table = document.createElement("table");
  table.className = "events-table";
  const head = table.insertRow();
  const columns = [
    "timestamp",
    "process_label",
    "process_type",
    "process",
    "temporal",
    "material",
    "site",
    "quality",
    "information",
    "role",
  ];
  const columnLabels = {
    timestamp: "When",
    process_label: "Label",
    process_type: "Type",
    process: "Process",
    temporal: "Temporal",
    material: "Material",
    site: "Site",
    quality: "Quality",
    information: "Information",
    role: "Role",
  };
  for (const column of columns) {
    const th = document.createElement("th");
    th.textContent = columnLabels[column] || column;
    head.appendChild(th);
  }
  for (const row of items) {
    const tr = document.createElement("tr");
    tr.className = "events-row";
    if (row.id === state.selectedEventId) {
      tr.classList.add("selected");
    }
    tr.onclick = () => selectProcessEvent(row);
    tr.ondblclick = () => openProcessEventInGraph(row);
    const buckets = row.buckets || {};
    for (const column of columns) {
      if (column === "timestamp" || column === "process_label" || column === "process_type") {
        const td = document.createElement("td");
        td.className = "events-meta";
        td.textContent = row[column] ?? "";
        td.title = td.textContent;
        tr.appendChild(td);
      } else {
        tr.appendChild(renderGraphEventBucketCell(buckets[column]));
      }
    }
    table.appendChild(tr);
  }
  host.appendChild(table);
}

async function loadEvents() {
  const host = $("events-table-host");
  if (host && !state.graphEvents) {
    host.innerHTML = '<div class="graph-detail-empty">Loading events…</div>';
  }
  try {
    const payload = await api("/api/processes?limit=100");
    state.graphEvents = payload;
    renderEventsTable(payload.items || []);
    if (state.selectedEventId) {
      const selected = (payload.items || []).find((row) => row.id === state.selectedEventId);
      renderEventDetail(selected || null);
    }
  } catch (err) {
    if (host) {
      host.innerHTML = "";
      const empty = document.createElement("div");
      empty.className = "graph-detail-empty";
      empty.textContent = err.message || "Failed to load process events.";
      host.appendChild(empty);
    }
  }
}

function renderGraphTables(tables) {
  const host = $("graph-tables-host");
  host.innerHTML = "";
  for (const tableData of tables || []) {
    const section = document.createElement("div");
    section.className = "graph-table-section";
    const heading = document.createElement("h3");
    heading.textContent = `${tableData.name} (${tableData.rows?.length || 0})`;
    section.appendChild(heading);
    if (!tableData.rows?.length) {
      const empty = document.createElement("p");
      empty.className = "graph-detail-empty";
      empty.textContent = "No rows.";
      section.appendChild(empty);
      host.appendChild(section);
      continue;
    }
    const columns = Object.keys(tableData.rows[0]);
    const table = document.createElement("table");
    const head = table.insertRow();
    for (const column of columns) {
      const th = document.createElement("th");
      th.textContent = column;
      head.appendChild(th);
    }
    for (const row of tableData.rows) {
      const tr = table.insertRow();
      for (const column of columns) {
        const td = tr.insertCell();
        const value = row[column];
        td.textContent = value == null ? "" : String(value);
        td.title = td.textContent;
      }
    }
    section.appendChild(table);
    host.appendChild(section);
  }
}

function updateGraphNetwork(overview) {
  ensureGraphNetwork();
  if (!state.graphNetwork || !overview) return;
  let nodes = overview.nodes.map((node) => {
    const styled = getGraphNodeColor(node);
    const item = {
      id: node.id,
      label: node.label,
      group: node.group,
      title: node.title,
      color: getGraphBaseColor(node),
      shape: styled.shape,
      ...(styled.size ? { size: styled.size } : {}),
      font: {
        color: styled.fontColor,
        bold: node.group === "bfo_anchor" || node.group === "ai_system",
        size: node.group === "ai_system" ? 14 : node.group === "bfo_anchor" ? 12 : 11,
        face: "Inter, Segoe UI, system-ui, sans-serif",
      },
      borderWidth: styled.borderWidth,
    };
    if (styled.shape === "box") {
      item.shapeProperties = { borderRadius: 0 };
      item.margin = { top: 6, bottom: 6, left: 8, right: 8 };
    }
    return item;
  });
  nodes = applyGraphLayoutPositions(nodes);
  const edges = overview.edges.map((edge) => {
    const source = overview.nodes.find((node) => node.id === edge.from);
    const bucketId = source ? getGraphNodeBucketId(source) : null;
    const bucket = bucketId ? getGraphBucketById(bucketId) : null;
    const edgeColor = state.graphView === "brain" && bucket ? bucket.color : "#D5D8DC";
    return {
      id: edge.id,
      from: edge.from,
      to: edge.to,
      label: state.graphView === "brain" ? undefined : edge.label || undefined,
      color: { color: edgeColor, highlight: edgeColor, opacity: 0.85 },
      width: state.graphView === "brain" ? 2 : 1,
    };
  });
  state.graphNodesDataset.clear();
  state.graphEdgesDataset.clear();
  state.graphNodesDataset.add(nodes);
  state.graphEdgesDataset.add(edges);
  state.graphBuckets = overview.buckets || DEFAULT_BFO_BUCKETS;
  state.graphEnabledBuckets = null;
  renderGraphBucketFilters();
  applyGraphPhysicsForView();
  applyGraphVisualState();
  renderGraphNodeList();
  if (state.graphSelectedNodeId) {
    const stillExists = nodes.some((node) => node.id === state.graphSelectedNodeId);
    if (stillExists) {
      state.graphNetwork.selectNodes([state.graphSelectedNodeId]);
      selectGraphNode(state.graphSelectedNodeId);
    } else {
      clearGraphNodeSelection();
    }
  }
}

function renderGraphViewToggle() {
  document.querySelectorAll(".graph-view-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.graphView === state.graphView);
  });
}

async function loadGraphOverview() {
  try {
    const overview = await api(`/api/graph/overview?view=${encodeURIComponent(state.graphView)}`);
    state.graphOverview = overview;
    if (overview.meta?.view && GRAPH_VIEWS.has(overview.meta.view)) {
      state.graphView = overview.meta.view;
      document.querySelectorAll(".graph-view-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.graphView === state.graphView);
      });
    }
    state.graphBuckets = overview.buckets || DEFAULT_BFO_BUCKETS;
    const meta = overview.meta || {};
    const stats = $("graph-stats");
    if (stats) {
      stats.textContent = `${meta.triple_count ?? 0} triples · ${meta.node_count ?? 0} nodes`;
    }
    updateGraphNetwork(overview);
    if (state.graphTab === "tables") {
      renderGraphTables(overview.tables);
    }
    if (state.pendingGraphFocus) {
      const row = state.pendingGraphFocus;
      state.pendingGraphFocus = null;
      focusGraphProcessNode(row);
    }
  } catch (err) {
    const host = $("graph-detail-table");
    if (host) {
      host.className = "graph-detail-empty";
      host.textContent = err.message || "Failed to load graph overview.";
    }
  }
}

async function refreshGraphStats() {
  try {
    const health = await api("/api/health");
    const triples = health.graph?.triples ?? 0;
    if (state.graphTab !== "overview" || !state.graphOverview) {
      $("graph-stats").textContent = `${triples} triples`;
    }
  } catch {
    if (!state.graphOverview) $("graph-stats").textContent = "";
  }
}

async function runActiveContextQuery() {
  $("sparql-input").value = ACTIVE_CONTEXT_SPARQL;
  await runSparql();
}

function renderQueryList() {
  const list = $("query-list");
  list.innerHTML = "";
  for (const sample of SAMPLE_QUERIES) {
    const btn = document.createElement("button");
    btn.className = "query-item";
    btn.textContent = sample.name;
    btn.onclick = () => {
      $("sparql-input").value = sample.query;
      runSparql();
    };
    list.appendChild(btn);
  }
}

async function runSparql() {
  const results = $("sparql-results");
  results.innerHTML = "";
  try {
    const data = await api("/api/sparql", {
      method: "POST",
      body: JSON.stringify({ query: $("sparql-input").value }),
    });
    if (data.type === "solutions") {
      const table = document.createElement("table");
      const head = table.insertRow();
      for (const variable of data.variables) {
        const th = document.createElement("th");
        th.textContent = variable;
        head.appendChild(th);
      }
      for (const row of data.rows) {
        const tr = table.insertRow();
        for (const variable of data.variables) {
          const td = tr.insertCell();
          td.textContent = row[variable] ?? "";
          td.title = row[variable] ?? "";
        }
      }
      results.appendChild(table);
    } else {
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(data, null, 2);
      results.appendChild(pre);
    }
  } catch (err) {
    const div = document.createElement("div");
    div.className = "sparql-error";
    div.textContent = err.message;
    results.appendChild(div);
  }
}

/* ---------- models ---------- */

function firstToolCapableModel(providers) {
  for (const provider of providers || []) {
    for (const model of provider.models || []) {
      if (model.supports_tools === false) continue;
      return `${provider.id}/${model.id}`;
    }
  }
  return null;
}

function applyComposerModelDefaults() {
  const preferred =
    (state.settings?.default_model && modelSupportsTools(state.settings.default_model)
      ? state.settings.default_model
      : null) || firstToolCapableModel(state.modelProviders);
  if (!preferred) return;
  for (const section of ["chat", "code"]) {
    const picker = $(composerIds(section).picker);
    if (
      picker &&
      !picker.value &&
      [...picker.options].some((option) => option.value === preferred)
    ) {
      picker.value = preferred;
      setChatModel(section, preferred);
    }
  }
}

function populateModelSelect(select, providers, selectedValue) {
  const current = selectedValue ?? select.value;
  while (select.options.length > 1) select.remove(1);
  for (const provider of providers || []) {
    for (const model of provider.models || []) {
      const option = document.createElement("option");
      option.value = `${provider.id}/${model.id}`;
      const label = `${provider.name} / ${model.name}`;
      option.textContent =
        model.supports_tools === false ? `${label} (no agent tools)` : label;
      if (model.supports_tools === false) option.disabled = true;
      select.appendChild(option);
    }
  }
  if (current) {
    const match = [...select.options].find((o) => o.value === current);
    select.value = match ? current : "";
  }
}

async function loadModels() {
  try {
    const { providers } = await api("/api/models");
    state.modelProviders = providers || [];
    for (const picker of [$("model-picker"), $("code-model-picker")]) {
      populateModelSelect(picker, providers);
    }
    populateModelSelect($("set-model"), providers, $("set-model")?.value);
    applyComposerModelDefaults();
    renderModelSelector("chat");
    renderModelSelector("code");
    if (state.section === "settings" && state.settingsTab === "models") renderModelsTab();
    refreshGraphStats();
  } catch {}
}

async function loadAppSettings() {
  try {
    state.settings = await api("/api/settings");
  } catch {
    state.settings = {};
  }
}

async function loadFileIndex() {
  try {
    const data = await api("/api/files/index");
    state.fileIndex = { files: data.files || [], truncated: data.truncated };
  } catch {
    state.fileIndex = { files: [], truncated: false };
  }
}

/* ---------- settings ---------- */

function switchSettingsTab(tab, { updateHash = true } = {}) {
  if (!SETTINGS_TABS.includes(tab)) tab = "general";
  state.settingsTab = tab;
  document.querySelectorAll(".settings-nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.settingsTab === tab);
  });
  for (const name of SETTINGS_TABS) {
    $(`settings-tab-${name}`).classList.toggle("hidden", name !== tab);
  }
  if (tab === "servers") renderServersTab();
  if (tab === "models") renderModelsTab();

  if (updateHash && state.section === "settings") {
    setSectionHash("settings", tab);
  }
}

function updateHarnessFields(harness) {
  const isPi = harness === "pi";
  $("set-opencode-wrap").classList.toggle("hidden", isPi);
  $("set-pi-wrap").classList.toggle("hidden", !isPi);
}

function integrationStatusClass(connected, error) {
  if (connected) return "ok";
  if (error) return "error";
  return "warn";
}

function integrationStatusLabel(connected, error) {
  if (connected) return "Connected";
  if (error) return "Disconnected";
  return "Offline";
}

function serverStatusPill(online, label) {
  const pill = document.createElement("span");
  pill.className = `settings-status-pill ${online ? "ok" : "warn"}`;
  pill.innerHTML = `${icon(online ? "wifi" : "wifi-off", 12)}<span>${label}</span>`;
  return pill;
}

function formatBytes(bytes) {
  if (!bytes || bytes < 1024) return `${bytes || 0} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unit]}`;
}

async function loadHealth() {
  try {
    state.health = await api("/api/health");
  } catch {
    state.health = null;
  }
  return state.health;
}

async function loadIntegrations() {
  try {
    const payload = await api("/api/integrations");
    state.integrations = payload.integrations || [];
  } catch {
    state.integrations = [];
  }
  return state.integrations;
}

function renderDoctorReadyPill(report) {
  const pill = $("doctor-ready-pill");
  if (!pill) return;
  if (!report) {
    pill.classList.add("hidden");
    return;
  }
  pill.classList.remove("hidden");
  pill.className = `settings-ready-pill ${report.ready ? "ok" : "warn"}`;
  pill.textContent = report.ready ? "Ready" : "Setup incomplete";
}

function renderDoctorChecks(containerId, report) {
  const container = $(containerId);
  if (!container) return;
  container.innerHTML = "";
  if (!report || !report.checks || !report.checks.length) {
    container.textContent = "No checks returned.";
    return;
  }
  for (const check of report.checks) {
    const row = document.createElement("div");
    row.className = "doctor-check-row";
    const status = document.createElement("span");
    status.className = `doctor-status ${check.status || "warn"}`;
    status.textContent = check.status || "warn";
    const message = document.createElement("div");
    message.className = "doctor-check-message";
    message.textContent = check.message || "";
    const top = document.createElement("div");
    top.className = "doctor-check-top";
    top.appendChild(status);
    top.appendChild(message);
    row.appendChild(top);
    if (check.fix) {
      const fix = document.createElement("div");
      fix.className = "doctor-check-fix";
      fix.textContent = `Fix: ${check.fix}`;
      row.appendChild(fix);
    }
    container.appendChild(row);
  }
  if (containerId === "doctor-settings-results") renderDoctorReadyPill(report);
}

async function runDoctor() {
  return api("/api/doctor");
}

async function refreshDoctorInSettings() {
  try {
    const report = await runDoctor();
    state.doctorReport = report;
    renderDoctorChecks("doctor-settings-results", report);
    return report;
  } catch (e) {
    const fallback = {
      checks: [
        {
          id: "doctor_api",
          status: "error",
          message: `Doctor API failed: ${e.message || e}`,
          fix: "Ensure the ABI Desktop backend is running.",
        },
      ],
      ready: false,
    };
    state.doctorReport = fallback;
    renderDoctorChecks("doctor-settings-results", fallback);
    return null;
  }
}

function populateSettingsForm(settings) {
  state.settingsDraft = { ...settings };
  $("set-workspace").value = settings.workspace_root || "";
  $("set-harness").value = settings.harness || "opencode";
  $("set-opencode").value = settings.opencode_bin || "";
  $("set-pi").value = settings.pi_bin || "";
  $("set-model").value = settings.default_model || "";
  $("set-chat-agent").value = settings.chat_agent || "";
  $("set-code-agent").value = settings.code_agent || "";
  $("set-router-auto-apply").checked =
    settings.router_auto_apply === "true" || settings.router_auto_apply === "1";
  updateHarnessFields($("set-harness").value);
  refreshWorkspaceEnvPanel();
  loadWorkspaceContextSelectors(settings.active_org, settings.active_model);
}

function renderWorkspaceEnvPanel(report) {
  const list = $("workspace-env-list");
  if (!list) return;
  list.innerHTML = "";
  if (!report || !report.files || !report.files.length) {
    list.textContent = "No workspace configured.";
    return;
  }
  for (const file of report.files) {
    const row = document.createElement("div");
    row.className = "workspace-env-row";
    const path = document.createElement("div");
    path.className = "workspace-env-path";
    path.textContent = file.path;
    const status = document.createElement("span");
    status.className = `workspace-env-status ${file.exists ? "ok" : "missing"}`;
    status.textContent = file.exists ? "Found" : "Missing";
    const keys = document.createElement("div");
    keys.className = "workspace-env-keys";
    if (file.exists && file.keys && file.keys.length) {
      keys.textContent = `Keys: ${file.keys.join(", ")}`;
    } else if (file.exists) {
      keys.textContent = "No non-empty keys detected.";
    } else {
      keys.textContent = `Expected at ${file.path}`;
    }
    row.append(path, status, keys);
    list.appendChild(row);
  }
  if (report.provider_keys && report.provider_keys.length) {
    const summary = document.createElement("div");
    summary.className = "workspace-env-keys";
    summary.textContent = `Provider keys ready for chat: ${report.provider_keys.join(", ")}`;
    list.appendChild(summary);
  } else {
    const summary = document.createElement("div");
    summary.className = "workspace-env-keys";
    summary.textContent =
      "No provider API keys detected in this workspace. Chat will fail until you add keys or configure Ollama.";
    list.appendChild(summary);
  }
}

async function refreshWorkspaceEnvPanel(workspaceRoot) {
  const root = workspaceRoot ?? $("set-workspace")?.value ?? state.settingsDraft?.workspace_root;
  if (!root) {
    renderWorkspaceEnvPanel(null);
    return;
  }
  try {
    const report = await api(`/api/workspace/env?workspace_root=${encodeURIComponent(root)}`);
    state.workspaceEnv = report;
    renderWorkspaceEnvPanel(report);
  } catch {
    renderWorkspaceEnvPanel(null);
  }
}

async function loadWorkspaceContextSelectors(activeOrg, activeModel) {
  const orgSelect = $("set-active-org");
  const modelSelect = $("set-active-model");
  if (!orgSelect || !modelSelect) return;
  try {
    const payload = await api("/api/workspace/orgs");
    const orgs = payload.orgs || [];
    const selectedOrg = activeOrg || payload.active_org || "default";
    orgSelect.innerHTML = "";
    for (const org of orgs) {
      const option = document.createElement("option");
      option.value = org;
      option.textContent = org;
      orgSelect.appendChild(option);
    }
    const newOrgOption = document.createElement("option");
    newOrgOption.value = "__new__";
    newOrgOption.textContent = "New organization…";
    orgSelect.appendChild(newOrgOption);
    if (orgs.includes(selectedOrg)) orgSelect.value = selectedOrg;
    else if (orgs.length) orgSelect.value = orgs[0];
    else orgSelect.value = "__new__";

    await populateModelSelector(selectedOrg, activeModel || payload.active_model);
  } catch {
    orgSelect.innerHTML = `<option value="${activeOrg || "default"}">${activeOrg || "default"}</option>`;
    modelSelect.innerHTML = `<option value="${activeModel || "default"}">${activeModel || "default"}</option>`;
  }
}

async function populateModelSelector(org, activeModel) {
  const modelSelect = $("set-active-model");
  if (!modelSelect) return;
  if (!org || org === "__new__") {
    modelSelect.innerHTML = `<option value="${activeModel || "default"}">${activeModel || "default"}</option>`;
    return;
  }
  try {
    const payload = await api(`/api/workspace/orgs/${encodeURIComponent(org)}/models`);
    const models = payload.models || [];
    const selected = activeModel || payload.active_model || "default";
    modelSelect.innerHTML = "";
    for (const model of models) {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      modelSelect.appendChild(option);
    }
    const newModelOption = document.createElement("option");
    newModelOption.value = "__new__";
    newModelOption.textContent = "New model context…";
    modelSelect.appendChild(newModelOption);
    if (models.includes(selected)) modelSelect.value = selected;
    else if (models.length) modelSelect.value = models[0];
    else modelSelect.value = "__new__";
  } catch {
    modelSelect.innerHTML = `<option value="${activeModel || "default"}">${activeModel || "default"}</option>`;
  }
}

function readActiveContextFromForm() {
  let org = $("set-active-org")?.value || "default";
  let model = $("set-active-model")?.value || "default";
  if (org === "__new__") {
    const entered = prompt("Organization name");
    if (!entered) return null;
    org = entered.trim();
  }
  if (model === "__new__") {
    const entered = prompt("Model context name");
    if (!entered) return null;
    model = entered.trim();
  }
  return { org, model };
}

async function scaffoldActiveContext() {
  const context = readActiveContextFromForm();
  if (!context) return;
  const { org, model } = context;
  await api(
    `/api/workspace/orgs/${encodeURIComponent(org)}/models/${encodeURIComponent(model)}/scaffold`,
    { method: "POST" }
  );
  await loadWorkspaceContextSelectors(org, model);
  $("set-active-org").value = org;
  $("set-active-model").value = model;
  showToast(`Scaffolded ${org}/${model}`, "info");
  if (state.section === "code") loadTree();
}

function renderOllamaServerCard(item) {
  const card = document.createElement("div");
  card.className = "server-card";

  const header = document.createElement("div");
  header.className = "server-card-header";
  const iconWrap = document.createElement("div");
  iconWrap.className = "server-card-icon";
  iconWrap.innerHTML = icon("hard-drive", 18);
  const titleWrap = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = item.name || "Ollama";
  const subtitle = document.createElement("p");
  subtitle.textContent = "Run open-source models locally";
  titleWrap.append(title, subtitle);
  const status = serverStatusPill(
    item.connected,
    integrationStatusLabel(item.connected, item.error)
  );
  header.append(iconWrap, titleWrap, status);

  const form = document.createElement("div");
  form.className = "server-card-body";
  const urlLabel = document.createElement("label");
  urlLabel.className = "settings-field";
  urlLabel.textContent = "Base URL";
  const urlInput = document.createElement("input");
  urlInput.type = "text";
  urlInput.className = "server-url-input";
  urlInput.value = item.base_url || "";
  urlInput.spellcheck = false;
  urlLabel.appendChild(urlInput);

  const actions = document.createElement("div");
  actions.className = "server-card-actions";
  const connectBtn = document.createElement("button");
  connectBtn.type = "button";
  connectBtn.className = "settings-btn primary";
  connectBtn.textContent = "Connect";
  const refreshBtn = document.createElement("button");
  refreshBtn.type = "button";
  refreshBtn.className = "settings-btn";
  refreshBtn.innerHTML = icon("refresh-cw", 13) + "<span>Refresh</span>";
  actions.append(connectBtn, refreshBtn);

  const hint = document.createElement("p");
  hint.className = "server-card-hint";
  hint.textContent = item.error || item.hint || (item.connected
    ? "Models sync into opencode.json and appear in chat/code pickers."
    : "Install and start Ollama to use local models.");

  const modelsWrap = document.createElement("div");
  modelsWrap.className = "server-models";
  const modelsTitle = document.createElement("p");
  modelsTitle.className = "server-models-title";
  modelsTitle.textContent = item.models?.length
    ? `Installed models (${item.models.length})`
    : "Installed models";
  modelsWrap.appendChild(modelsTitle);

  if (item.models?.length) {
    const table = document.createElement("table");
    table.className = "settings-table compact";
    const head = table.insertRow();
    for (const col of ["Model", "Size", "Params", "Quant"]) {
      const th = document.createElement("th");
      th.textContent = col;
      head.appendChild(th);
    }
    for (const model of item.models) {
      const tr = table.insertRow();
      const name = tr.insertCell();
      name.textContent = model.name;
      name.title = model.name;
      tr.insertCell().textContent = model.size ? formatBytes(model.size) : "";
      tr.insertCell().textContent = model.parameter_size || "";
      tr.insertCell().textContent = model.quantization_level || "";
    }
    modelsWrap.appendChild(table);
  } else {
    const none = document.createElement("p");
    none.className = "server-card-hint";
    none.textContent = item.connected
      ? "No models installed. Run `ollama pull <model>`."
      : "Connect to Ollama to list local models.";
    modelsWrap.appendChild(none);
  }

  connectBtn.onclick = async () => {
    connectBtn.disabled = true;
    try {
      const updated = await api("/api/integrations/ollama", {
        method: "PUT",
        body: JSON.stringify({ base_url: urlInput.value.trim() }),
      });
      const index = state.integrations.findIndex((x) => x.id === item.id);
      if (index >= 0) state.integrations[index] = updated;
      renderServersTab();
      loadModels();
    } catch (err) {
      alert(`Connect failed: ${err.message}`);
    } finally {
      connectBtn.disabled = false;
    }
  };
  refreshBtn.onclick = async () => {
    await loadIntegrations();
    renderServersTab();
  };

  form.append(urlLabel, actions, hint, modelsWrap);
  card.append(header, form);
  return card;
}

function renderOpencodeServerCard(settings, health, report) {
  const card = document.createElement("div");
  card.className = "server-card";

  const harness = settings.harness || "opencode";
  const reachable = health?.opencode_running;
  const binaryCheck = report?.checks?.find((c) => c.id === "opencode_binary");
  const reachCheck = report?.checks?.find((c) => c.id === "opencode_reachable");

  const header = document.createElement("div");
  header.className = "server-card-header";
  const iconWrap = document.createElement("div");
  iconWrap.className = "server-card-icon";
  iconWrap.innerHTML = icon("server", 18);
  const titleWrap = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = "opencode";
  const subtitle = document.createElement("p");
  subtitle.textContent = "AI harness for chat and code sections";
  titleWrap.append(title, subtitle);
  const status = serverStatusPill(
    harness === "opencode" && reachable,
    harness !== "opencode" ? "pi harness active" : reachable ? "Online" : "Offline"
  );
  header.append(iconWrap, titleWrap, status);

  const body = document.createElement("div");
  body.className = "server-card-body";
  const rows = [
    ["Binary", settings.opencode_bin || "opencode"],
    ["Server URL", health?.opencode_url || "—"],
    ["Harness health", reachCheck?.message || binaryCheck?.message || "—"],
  ];
  const table = document.createElement("table");
  table.className = "server-info-table";
  for (const [label, value] of rows) {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = label;
    const td = document.createElement("td");
    td.innerHTML = `<code>${value}</code>`;
    tr.append(th, td);
    table.appendChild(tr);
  }
  body.appendChild(table);
  card.append(header, body);
  return card;
}

function renderAbiServerCard(health, settings) {
  const card = document.createElement("div");
  card.className = "server-card";

  const header = document.createElement("div");
  header.className = "server-card-header";
  const iconWrap = document.createElement("div");
  iconWrap.className = "server-card-icon";
  iconWrap.innerHTML = icon("cloud", 18);
  const titleWrap = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = "ABI Desktop";
  const subtitle = document.createElement("p");
  subtitle.textContent = "Local app runtime and knowledge graph";
  titleWrap.append(title, subtitle);
  const status = serverStatusPill(true, "Running");
  header.append(iconWrap, titleWrap, status);

  const body = document.createElement("div");
  body.className = "server-card-body";
  const rows = [
    ["Data directory", health?.data_dir || "~/.abi-desktop"],
    ["Workspace root", health?.workspace_root || settings.workspace_root || "—"],
    ["Graph triples", String(health?.graph?.triples ?? 0)],
    ["App", health?.app || "ABI Desktop"],
  ];
  const table = document.createElement("table");
  table.className = "server-info-table";
  for (const [label, value] of rows) {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = label;
    const td = document.createElement("td");
    td.innerHTML = `<code>${value}</code>`;
    tr.append(th, td);
    table.appendChild(tr);
  }
  body.appendChild(table);
  card.append(header, body);
  return card;
}

function renderServersTab() {
  const list = $("servers-list");
  if (!list) return;
  list.innerHTML = "";

  const settings = state.settingsDraft || {};
  const ollama = state.integrations.find((item) => item.id === "ollama");

  if (ollama) list.appendChild(renderOllamaServerCard(ollama));
  list.appendChild(renderOpencodeServerCard(settings, state.health, state.doctorReport));
  list.appendChild(renderAbiServerCard(state.health, settings));
}

function flattenModels(providers) {
  const rows = [];
  for (const provider of providers || []) {
    for (const model of provider.models || []) {
      rows.push({
        providerId: provider.id,
        providerName: provider.name,
        modelId: model.id,
        name: model.name || model.id,
        canonical: `${provider.id}/${model.id}`,
      });
    }
  }
  return rows;
}

function renderModelsTab() {
  const rows = flattenModels(state.modelProviders);
  const search = ($("models-search")?.value || "").trim().toLowerCase();
  const providerFilter = $("models-provider-filter")?.value || "all";

  const filterSelect = $("models-provider-filter");
  if (filterSelect) {
    const current = filterSelect.value;
    while (filterSelect.options.length > 1) filterSelect.remove(1);
    const seen = new Set();
    for (const row of rows) {
      if (seen.has(row.providerId)) continue;
      seen.add(row.providerId);
      const option = document.createElement("option");
      option.value = row.providerId;
      option.textContent = row.providerName;
      filterSelect.appendChild(option);
    }
    if ([...filterSelect.options].some((o) => o.value === current)) {
      filterSelect.value = current;
    }
  }

  const filtered = rows.filter((row) => {
    if (providerFilter !== "all" && row.providerId !== providerFilter) return false;
    if (!search) return true;
    const haystack = [row.name, row.modelId, row.providerName, row.canonical]
      .join(" ")
      .toLowerCase();
    return haystack.includes(search);
  });

  $("models-count-badge").textContent = String(filtered.length);
  const providerBadge = $("models-provider-badge");
  if (providerBadge) {
    const providerCount = new Set(rows.map((r) => r.providerId)).size;
    providerBadge.textContent = `${providerCount} providers`;
    providerBadge.classList.toggle("hidden", providerCount === 0);
  }

  const tbody = $("models-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";
  $("models-table-wrap").classList.toggle("hidden", filtered.length === 0);
  $("models-empty").classList.toggle("hidden", filtered.length !== 0);

  for (const row of filtered) {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = row.name;
    const modelId = document.createElement("td");
    modelId.innerHTML = `<code>${row.modelId}</code>`;
    const provider = document.createElement("td");
    provider.textContent = row.providerName;
    tr.append(name, modelId, provider);
    tbody.appendChild(tr);
  }
}

async function loadSettingsView() {
  try {
    const [settings, , report] = await Promise.all([
      api("/api/settings"),
      loadHealth(),
      refreshDoctorInSettings(),
    ]);
    populateSettingsForm(settings);
    await Promise.all([loadIntegrations(), loadModels()]);
    renderServersTab();
    renderModelsTab();
    state.doctorReport = report;
  } catch {}
}

async function openSettings(tab = "general") {
  switchSection("settings", { updateHash: false });
  switchSettingsTab(tab);
}

async function saveSettings() {
  const priorWorkspace = state.settingsDraft?.workspace_root || "";
  const context = readActiveContextFromForm();
  if (!context) return;
  const payload = {
    workspace_root: $("set-workspace").value,
    active_org: context.org,
    active_model: context.model,
    harness: $("set-harness").value,
    opencode_bin: $("set-opencode").value,
    pi_bin: $("set-pi").value,
    default_model: $("set-model").value,
    chat_agent: $("set-chat-agent").value,
    code_agent: $("set-code-agent").value,
    router_auto_apply: $("set-router-auto-apply").checked ? "true" : "false",
  };
  const updated = await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
  const workspaceChanged = priorWorkspace !== updated.workspace_root;
  state.settings = updated;
  populateSettingsForm(updated);
  loadModels();
  loadHealth().then(() => {
    renderServersTab();
    refreshGraphStats();
    refreshStatusBar();
  });
  refreshDoctorInSettings();
  loadFileIndex();
  if (workspaceChanged) {
    ide.tabs = [];
    ide.activeTab = null;
    if (ide.monaco) ide.monaco.setValue("");
    $("editor-tabs").innerHTML = "";
    reconnectTerminal();
  }
  if (state.section === "code") loadTree();
}

function discardSettings() {
  api("/api/settings").then(populateSettingsForm).catch(() => {});
}

async function maybeShowFirstRunDoctor() {
  try {
    const [settings, report] = await Promise.all([api("/api/settings"), runDoctor()]);
    state.settings = settings;
    const dismissed =
      settings.doctor_dismissed === "true" || settings.doctor_dismissed === "1";
    if (dismissed || report.ready) return;
    renderDoctorChecks("doctor-first-run-results", report);
    $("doctor-modal").classList.remove("hidden");
  } catch {}
}

async function dismissDoctor() {
  await api("/api/settings", {
    method: "PUT",
    body: JSON.stringify({ doctor_dismissed: "true" }),
  });
  $("doctor-modal").classList.add("hidden");
}

/* ---------- misc ---------- */

function autoGrow(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, 144) + "px";
}

function wireComposer(inputId, section) {
  const input = $(inputId);
  input.addEventListener("input", () => {
    autoGrow(input);
    updateSendButton(section);
    scheduleRouterSuggestions(section);
    if (getMentionContext(input)) openMention(section, input);
    else closeMention(section);
  });
  input.addEventListener("keydown", (e) => {
    const comp = getComposer(section);
    if (comp.mention?.open) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        comp.mention.index = Math.min(
          comp.mention.index + 1,
          Math.max(comp.mention.items.length - 1, 0)
        );
        renderMentionPopup(section);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        comp.mention.index = Math.max(comp.mention.index - 1, 0);
        renderMentionPopup(section);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (comp.mention.items.length) selectMentionItem(section, comp.mention.index);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        closeMention(section);
        return;
      }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(section);
    }
  });
  input.addEventListener("click", () => {
    if (getMentionContext(input)) openMention(section, input);
    else closeMention(section);
  });
  input.addEventListener("blur", () => {
    setTimeout(() => closeMention(section), 120);
  });
}

/* ---------- init ---------- */

function init() {
  mountIcons();

  document.querySelectorAll(".rail-btn[data-section]").forEach((btn) => {
    btn.onclick = () => switchSection(btn.dataset.section);
  });

  $("btn-toggle-panel").onclick = () => togglePanel();
  $("btn-new-chat").onclick = () => newChat("chat");
  $("btn-new-code-chat").onclick = () => newChat("code");
  $("btn-send").onclick = () => sendMessage("chat");
  $("btn-code-send").onclick = () => sendMessage("code");
  $("btn-save-file").onclick = saveActiveFile;
  $("btn-new-file").onclick = () => startTreeInput("new-file", "");
  $("btn-new-folder").onclick = () => startTreeInput("new-folder", "");
  $("btn-toggle-hidden").onclick = () => {
    state.showHiddenFiles = !state.showHiddenFiles;
    $("btn-toggle-hidden").classList.toggle("active", state.showHiddenFiles);
    $("btn-toggle-hidden").title = state.showHiddenFiles
      ? "Hide hidden files"
      : "Show hidden files";
    loadTree();
  };
  $("terminal-titlebar").onclick = () => toggleTerminal();
  $("btn-terminal-reconnect").onclick = connectTerminal;
  $("view-toggle")
    .querySelectorAll("button")
    .forEach((b) => (b.onclick = () => setViewMode(b.dataset.mode)));
  wireTerminalDivider();
  wireStatusBar();
  wireWorkspaceSwitcher();
  $("btn-sparql").onclick = runSparql;
  document.querySelectorAll(".graph-tab").forEach((btn) => {
    btn.onclick = () => switchGraphTab(btn.dataset.graphTab);
  });
  $("graph-search")?.addEventListener("input", applyGraphSearch);
  $("graph-search")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      jumpGraphSearchMatch(e.shiftKey ? -1 : 1);
    }
    if (e.key === "Escape") {
      $("graph-search").value = "";
      applyGraphSearch();
    }
  });
  $("graph-search-clear")?.addEventListener("click", () => {
    $("graph-search").value = "";
    applyGraphSearch();
    $("graph-search")?.focus();
  });
  $("graph-detail-close")?.addEventListener("click", clearGraphNodeSelection);
  $("events-detail-close")?.addEventListener("click", () => {
    state.selectedEventId = null;
    renderEventsTable(state.graphEvents?.items || []);
    renderEventDetail(null);
  });
  document.querySelectorAll(".graph-view-btn").forEach((btn) => {
    btn.onclick = () => switchGraphView(btn.dataset.graphView);
  });

  document.querySelectorAll(".settings-nav-item").forEach((btn) => {
    btn.onclick = () => switchSettingsTab(btn.dataset.settingsTab);
  });
  $("btn-settings-save").onclick = saveSettings;
  $("btn-settings-discard").onclick = discardSettings;
  $("btn-scaffold-context").onclick = () => scaffoldActiveContext();
  $("set-active-org").onchange = () => {
    const org = $("set-active-org").value;
    if (org === "__new__") return;
    populateModelSelector(org, state.settingsDraft?.active_model);
  };
  $("set-harness").onchange = (e) => updateHarnessFields(e.target.value);
  let workspaceEnvTimer = null;
  $("set-workspace").oninput = () => {
    clearTimeout(workspaceEnvTimer);
    workspaceEnvTimer = setTimeout(() => refreshWorkspaceEnvPanel(), 300);
  };
  $("btn-doctor-rerun").onclick = () => refreshDoctorInSettings();
  $("btn-servers-refresh").onclick = async () => {
    await Promise.all([loadHealth(), loadIntegrations(), refreshDoctorInSettings()]);
    renderServersTab();
  };
  $("models-search").oninput = () => {
    const clear = $("models-search-clear");
    clear.classList.toggle("hidden", !$("models-search").value);
    renderModelsTab();
  };
  $("models-search-clear").onclick = () => {
    $("models-search").value = "";
    $("models-search-clear").classList.add("hidden");
    renderModelsTab();
  };
  $("models-provider-filter").onchange = () => renderModelsTab();
  $("set-model").onchange = () => {
    if (state.settingsDraft) state.settingsDraft.default_model = $("set-model").value;
  };

  $("btn-doctor-rerun-first").onclick = async () => {
    const report = await runDoctor();
    renderDoctorChecks("doctor-first-run-results", report);
    if (report.ready) await dismissDoctor();
  };
  $("btn-doctor-dismiss").onclick = dismissDoctor;
  $("btn-doctor-open-settings").onclick = () => {
    $("doctor-modal").classList.add("hidden");
    openSettings("general");
  };

  wireComposer("input", "chat");
  wireComposer("code-input", "code");
  document.addEventListener("click", () => {
    closeSelectorMenus("chat");
    closeSelectorMenus("code");
  });
  $("model-picker").onchange = () => {
    const value = $("model-picker").value;
    updateModelPill("chat", value);
    renderModelSelector("chat");
    if (state.activeChat.chat) setChatModel("chat", value);
  };
  $("code-model-picker").onchange = () => {
    const value = $("code-model-picker").value;
    updateModelPill("code", value);
    renderModelSelector("code");
    if (state.activeChat.code) setChatModel("code", value);
  };
  togglePanel(true);
  updateSendButton("chat");
  updateSendButton("code");
  renderQueryList();

  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "s" && state.section === "code") {
      e.preventDefault();
      saveActiveFile();
    }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "i" && !e.altKey && !e.shiftKey) {
      e.preventDefault();
      newChat(state.section === "code" ? "code" : "chat");
    }
  });

  loadChats("chat").then(() => {
    renderMessagesFor("chat");
    loadComposerSelectors("chat");
  });
  loadChats("code").then(() => loadComposerSelectors("code"));
  loadAppSettings().then(() => loadModels());
  loadWorkspaces();
  loadFileIndex();
  loadIntegrations();
  initMonaco();
  initFileTreeDrop();
  refreshGraphStats();
  refreshStatusBar();
  setInterval(refreshGraphStats, 15000);
  setInterval(refreshStatusBar, 5000);
  maybeShowFirstRunDoctor();

  window.addEventListener("hashchange", onSectionHashChange);
  window.addEventListener("popstate", onSectionHashChange);
  applySectionHash({ replaceMissing: true });
}

init();
