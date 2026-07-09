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
  settings: { title: "Settings", panel: "settings-panel" },
};

const SECTION_VIEWS = ["chat", "code", "graph", "settings"];

const SETTINGS_TABS = ["general", "servers", "models"];

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
    name: "Messages per chat",
    query:
      "PREFIX abid: <http://ontology.naas.ai/abi/desktop#>\nSELECT ?chat (COUNT(?m) AS ?messages) WHERE {\n  ?m abid:inChat ?chat .\n} GROUP BY ?chat ORDER BY DESC(?messages)",
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
  doctorReport: null,
  fileIndex: { files: [], truncated: false },
  composers: {
    chat: { fileChips: [], modelChip: null, mention: null },
    code: { fileChips: [], modelChip: null, mention: null },
  },
};

/* IDE state: Monaco tabs, preview mode, terminal. */
const ide = {
  editor: null,
  monacoReady: null,
  tabs: [], // { path, model, savedVersionId }
  activePath: null,
  selectedDir: "",
  dropHoverPath: null,
  fileTreeDragActive: false,
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

function switchSection(section) {
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
  } else if (section === "code") {
    loadTree();
    renderMessagesFor("code");
  } else if (section === "graph") {
    refreshGraphStats();
  } else if (section === "settings") {
    loadSettingsView();
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
  const chat = await api("/api/chats", {
    method: "POST",
    body: JSON.stringify({ section }),
  });
  state.chats[section].unshift(chat);
  state.activeChat[section] = chat.id;
  if (section === "chat") renderChatList();
  renderMessagesFor(section);
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
    container.appendChild(messageRow(message.role, message.content, message.parts));
  }
  scrollerFor(section).scrollTop = scrollerFor(section).scrollHeight;
}

function emptyState(section) {
  const div = document.createElement("div");
  div.className = "empty-state";
  div.innerHTML =
    `<div class="empty-logo">${icon("bot", 24)}</div>` +
    `<p>${
      section === "code"
        ? "Hello. Ask the coding agent to build something in your workspace."
        : "Hello. Type a message to get started."
    }</p>`;
  return div;
}

function messageRow(role, content, parts) {
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;

  const meta = document.createElement("div");
  meta.className = "msg-meta";

  const avatar = document.createElement("div");
  avatar.className = `avatar ${role}`;
  avatar.innerHTML = role === "user" ? icon("user", 16) : icon("bot", 16);

  const sender = document.createElement("div");
  sender.className = "msg-sender";
  sender.textContent = role === "user" ? "You" : "ABI";
  meta.append(avatar, sender);

  const panel = document.createElement("div");
  panel.className = `msg-panel ${role}`;

  const toolCalls = document.createElement("div");
  toolCalls.className = "tool-calls";
  if (parts && parts.length) {
    for (const part of parts) {
      if (part.type === "tool") toolCalls.appendChild(toolCallRow(part));
    }
  }
  if (toolCalls.children.length) panel.appendChild(toolCalls);

  const contentDiv = document.createElement("div");
  contentDiv.className = "content";
  contentDiv.textContent = content || "";
  panel.appendChild(contentDiv);

  row.append(meta, panel);
  return row;
}

function toolCallRow(part) {
  const div = document.createElement("div");
  div.className =
    "tool-call " +
    (part.status === "completed" ? "done" : part.status === "error" ? "error" : "running");
  const status = document.createElement("span");
  status.className = "tool-status";
  const title = document.createElement("span");
  title.className = "tool-title";
  title.textContent = part.title ? `${part.tool} · ${part.title}` : part.tool;
  div.append(status, title);
  return div;
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
    };
  }
  return {
    input: "input",
    popup: "mention-popup",
    chips: "chips",
    pill: "model-pill",
    picker: "model-picker",
  };
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
  const displayText = text;
  const apiText = await buildPromptText(section, displayText);

  input.value = "";
  clearComposerChips(section);
  closeMention(section);
  autoGrow(input);
  updateSendButton(section);
  if (container.querySelector(".empty-state")) container.innerHTML = "";
  container.appendChild(messageRow("user", displayText));

  // Assistant row with live-updating panel.
  const row = document.createElement("div");
  row.className = "msg-row assistant";

  const meta = document.createElement("div");
  meta.className = "msg-meta";
  const avatar = document.createElement("div");
  avatar.className = "avatar assistant";
  avatar.innerHTML = icon("bot", 16);
  const sender = document.createElement("div");
  sender.className = "msg-sender";
  sender.textContent = "ABI";
  meta.append(avatar, sender);

  const typing = document.createElement("div");
  typing.className = "typing-indicator";
  typing.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';

  const panel = document.createElement("div");
  panel.className = "msg-panel assistant hidden";
  const toolCalls = document.createElement("div");
  toolCalls.className = "tool-calls";
  const contentDiv = document.createElement("div");
  contentDiv.className = "content";
  panel.append(toolCalls, contentDiv);

  row.append(meta, typing, panel);
  container.appendChild(row);
  scroller.scrollTop = scroller.scrollHeight;

  const showPanel = () => {
    typing.remove();
    panel.classList.remove("hidden");
  };

  setStreaming(section, true);
  const seenTools = new Map();
  const textParts = new Map();

  try {
    const response = await fetch(`/api/chats/${chatId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: apiText, model: model || null }),
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
          toolCalls,
          seenTools,
          textParts,
          container,
          scroller,
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
    if (!contentDiv.textContent && !toolCalls.children.length && panel.classList.contains("hidden")) {
      row.remove();
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
    ctx.contentDiv.textContent = [...ctx.textParts.values()].join("");
  } else if (event.type === "tool") {
    ctx.showPanel();
    const key = event.call_id || `${event.tool}:${event.title}`;
    let node = ctx.seenTools.get(key);
    if (!node) {
      node = toolCallRow(event);
      ctx.seenTools.set(key, node);
      ctx.toolCalls.appendChild(node);
    }
    if (event.title) {
      node.querySelector(".tool-title").textContent = `${event.tool} · ${event.title}`;
    }
    node.className =
      "tool-call " +
      (event.status === "completed" ? "done" : event.status === "error" ? "error" : "running");
  } else if (event.type === "error") {
    ctx.showPanel();
    const errorDiv = document.createElement("div");
    errorDiv.className = "msg-error";
    errorDiv.textContent = `Error: ${event.message}`;
    ctx.contentDiv.before(errorDiv);
  } else if (event.type === "complete" && event.text) {
    ctx.showPanel();
    ctx.textParts.clear();
    ctx.contentDiv.textContent = event.text;
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
  previewTimer = setTimeout(renderPreview, 300);
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
  const rootCount = await renderDir("", fragment, 0);
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

/* Light refresh of the active highlight without refetching the tree. */
function renderTree() {
  document.querySelectorAll("#file-tree .tree-entry").forEach((el) => {
    el.classList.toggle("active", el.dataset.path === ide.activePath);
  });
}

async function renderDir(path, parent, depth) {
  const { entries } = await api(`/api/files?path=${encodeURIComponent(path)}`);
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
        await renderDir(entry.path, childContainer, depth + 1);
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

function handleUploadResult(data, targetDir = "") {
  const uploaded = data?.uploaded || [];
  clearDropHighlight();
  if (!uploaded.length) {
    showToast("No files were uploaded", "error");
    return;
  }
  if (targetDir) state.expandedDirs.add(targetDir);
  showToast(`Uploaded ${uploaded.length} file(s)`, "success");
  loadTree();
}

function initFileTreeDrop() {
  const tree = $("file-tree");
  if (!tree) return;

  tree.addEventListener("dragenter", (e) => {
    e.preventDefault();
    e.stopPropagation();
    ide.fileTreeDragActive = true;
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
    if (!tree.contains(e.relatedTarget)) {
      ide.fileTreeDragActive = false;
      clearDropHighlight();
    }
  });

  tree.addEventListener("drop", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    ide.fileTreeDragActive = false;
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
window.__isFileTreeDropActive = () => ide.fileTreeDragActive;
window.__onUploadComplete = (data, targetDir) =>
  handleUploadResult(data, targetDir || dropTargetDir());
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

/* ---------- graph ---------- */

async function refreshGraphStats() {
  try {
    const health = await api("/api/health");
    $("graph-stats").textContent = `${health.graph.triples} triples`;
    $("status-dot").classList.toggle("ok", health.opencode_running);
    $("status-label").textContent = health.opencode_running
      ? "opencode connected"
      : "opencode idle";
  } catch {
    $("status-dot").classList.remove("ok");
    $("status-label").textContent = "backend offline";
  }
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

function populateModelSelect(select, providers, selectedValue) {
  const current = selectedValue ?? select.value;
  while (select.options.length > 1) select.remove(1);
  for (const provider of providers || []) {
    for (const model of provider.models || []) {
      const option = document.createElement("option");
      option.value = `${provider.id}/${model.id}`;
      option.textContent = `${provider.name} / ${model.name}`;
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
    if (state.section === "settings" && state.settingsTab === "models") renderModelsTab();
    refreshGraphStats();
  } catch {}
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

function switchSettingsTab(tab) {
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
  updateHarnessFields($("set-harness").value);
  refreshWorkspaceEnvPanel();
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
  switchSection("settings");
  switchSettingsTab(tab);
}

async function saveSettings() {
  const priorWorkspace = state.settingsDraft?.workspace_root || "";
  const payload = {
    workspace_root: $("set-workspace").value,
    harness: $("set-harness").value,
    opencode_bin: $("set-opencode").value,
    pi_bin: $("set-pi").value,
    default_model: $("set-model").value,
    chat_agent: $("set-chat-agent").value,
    code_agent: $("set-code-agent").value,
  };
  const updated = await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
  const workspaceChanged = priorWorkspace !== updated.workspace_root;
  populateSettingsForm(updated);
  loadModels();
  loadHealth().then(() => {
    renderServersTab();
    refreshGraphStats();
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
  $("terminal-titlebar").onclick = () => toggleTerminal();
  $("btn-terminal-reconnect").onclick = connectTerminal;
  $("view-toggle")
    .querySelectorAll("button")
    .forEach((b) => (b.onclick = () => setViewMode(b.dataset.mode)));
  wireTerminalDivider();
  $("btn-sparql").onclick = runSparql;

  document.querySelectorAll(".settings-nav-item").forEach((btn) => {
    btn.onclick = () => switchSettingsTab(btn.dataset.settingsTab);
  });
  $("btn-settings-save").onclick = saveSettings;
  $("btn-settings-discard").onclick = discardSettings;
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
  $("model-picker").onchange = () => {
    const value = $("model-picker").value;
    updateModelPill("chat", value);
    if (state.activeChat.chat) setChatModel("chat", value);
  };
  $("code-model-picker").onchange = () => {
    const value = $("code-model-picker").value;
    updateModelPill("code", value);
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

  loadChats("chat").then(() => renderMessagesFor("chat"));
  loadChats("code");
  loadModels();
  loadFileIndex();
  loadIntegrations();
  initMonaco();
  initFileTreeDrop();
  refreshGraphStats();
  setInterval(refreshGraphStats, 15000);
  maybeShowFirstRunDoctor();
}

init();
