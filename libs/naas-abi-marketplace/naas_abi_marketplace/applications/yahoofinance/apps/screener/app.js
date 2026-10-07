const API_BASE = `${window.location.origin}/api/yahoofinance/screener`;

const state = {
  schema: null,
  rows: [],
  sourceRows: [],
  view: "listings",
  sortKey: "marketCap",
  sortDir: "desc",
  page: 0,
  visible: new Set(),
};

function $(id) {
  return document.getElementById(id);
}

function rawValue(value) {
  if (value && typeof value === "object" && "raw" in value) {
    return value.raw;
  }
  return value;
}

function displayValue(value) {
  if (value == null || value === "") {
    return "";
  }
  if (value && typeof value === "object") {
    if (value.fmt) {
      return value.fmt;
    }
    if ("raw" in value) {
      return String(value.raw);
    }
  }
  return String(value);
}

function numeric(row, key) {
  if (key === "ebitdaMargin") {
    const ebitda = Number(rawValue(row.ebitdaLtm));
    const revenue = Number(rawValue(row.totalRevenueLtm));
    if (!Number.isFinite(ebitda) || !Number.isFinite(revenue) || revenue === 0) {
      return null;
    }
    return ebitda / revenue;
  }
  const value = rawValue(row[key]);
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

function setStatus(message, isError = false) {
  const node = $("status");
  node.textContent = message;
  node.classList.toggle("error", isError);
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || response.statusText || "Request failed");
  }
  return data;
}

function formBody() {
  const includeFields = [...document.querySelectorAll("#include-fields input:checked")].map(
    (input) => input.value
  );
  const regions = [...document.querySelectorAll("#regions input:checked")].map(
    (input) => input.value
  );
  const minRevenue = $("min-revenue").value;
  return {
    size: Number($("size").value) || 100,
    offset: Number($("offset").value) || 0,
    fetch_all: $("fetch-all").checked,
    save: $("save").checked,
    sector: $("sector").value || null,
    industry: $("industry").value || null,
    sort_type: $("sort-type").value,
    sort_field: $("sort-field").value,
    min_revenue: minRevenue === "" ? null : Number(minRevenue),
    include_fields: includeFields,
    regions,
    require_positive: $("require-positive").checked,
    cookie: $("cookie").value || null,
    crumb: $("crumb").value || null,
    formatted: $("formatted").checked,
    use_records_response: $("use-records").checked,
    lang: $("lang").value || "en-US",
    query_region: $("query-region").value || "US",
    view: $("view").value,
  };
}

function fillSelect(node, items, getValue, getLabel) {
  node.replaceChildren();
  for (const item of items) {
    const option = document.createElement("option");
    option.value = getValue(item);
    option.textContent = getLabel(item);
    node.append(option);
  }
}

function fillDatalist(node, items) {
  node.replaceChildren();
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item;
    node.append(option);
  }
}

function setChecks(container, values, checkedValues) {
  container.replaceChildren();
  const selected = new Set(checkedValues);
  for (const value of values) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = value;
    input.checked = selected.has(value);
    label.append(input, document.createTextNode(value));
    container.append(label);
  }
}

function renderIncludeFields(schema) {
  const root = $("include-fields");
  root.replaceChildren();
  const selected = new Set(schema.defaults.include_fields);
  for (const group of schema.includeFieldGroups) {
    const details = document.createElement("details");
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = group.label;
    details.append(summary);
    const box = document.createElement("div");
    box.className = "checks compact";
    for (const field of group.fields) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = field;
      input.checked = selected.has(field);
      label.append(input, document.createTextNode(field));
      box.append(label);
    }
    details.append(box);
    root.append(details);
  }
}

function applyDefaults(schema) {
  const defaults = schema.defaults;
  $("sector").value = defaults.sector;
  $("industry").value = defaults.industry;
  $("min-revenue").value = defaults.min_revenue;
  $("require-positive").checked = defaults.require_positive !== false;
  $("size").value = defaults.size;
  $("offset").value = defaults.offset;
  $("sort-field").value = defaults.sort_field;
  $("sort-type").value = defaults.sort_type;
  $("formatted").checked = defaults.formatted;
  $("use-records").checked = defaults.use_records_response;
  $("lang").value = defaults.lang;
  $("query-region").value = defaults.query_region;
  state.visible = new Set(schema.defaultVisibleColumns);
}

function renderColumnPanel(schema) {
  const panel = $("column-panel");
  panel.replaceChildren();
  for (const column of schema.columns) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = column.key;
    input.checked = state.visible.has(column.key);
    input.addEventListener("change", () => {
      if (input.checked) {
        state.visible.add(column.key);
      } else {
        state.visible.delete(column.key);
      }
      renderTable();
    });
    label.append(input, document.createTextNode(column.label));
    panel.append(label);
  }
}

function visibleColumns() {
  return state.schema.columns.filter((column) => state.visible.has(column.key));
}

function parseCompanyList(text) {
  const tokens = [];
  const seen = new Set();
  for (const part of text.replaceAll(";", ",").replaceAll("\n", ",").split(",")) {
    const token = part.trim();
    const key = token.toLowerCase();
    if (!token || seen.has(key)) {
      continue;
    }
    seen.add(key);
    tokens.push(token);
  }
  return tokens;
}

function tickerValues(row) {
  const values = [row.ticker, row.primaryTicker, ...(displayValue(row.stockIds).split(/[,\s]+/))];
  return values.map((value) => displayValue(value).trim().toLowerCase()).filter(Boolean);
}

function rowMatchesCompanyList(row, tokens) {
  if (!tokens.length) {
    return true;
  }
  const tickers = tickerValues(row);
  const name = displayValue(row.companyName).trim().toLowerCase();
  return tokens.some((token) => {
    const needle = token.toLowerCase();
    if (tickers.some((ticker) => ticker === needle || ticker.startsWith(`${needle}.`))) {
      return true;
    }
    if (!name) {
      return false;
    }
    return (
      name === needle ||
      name.startsWith(`${needle} `) ||
      name.startsWith(`${needle},`) ||
      (needle.length >= 4 && name.startsWith(needle))
    );
  });
}

function filteredRows() {
  const query = $("filter").value.trim().toLowerCase();
  const fx = $("fx-filter").value;
  const minMcap = $("min-mcap").value === "" ? null : Number($("min-mcap").value);
  const minEbitda = $("min-ebitda").value === "" ? null : Number($("min-ebitda").value);
  const companyTokens = parseCompanyList($("company-list").value);
  return state.rows.filter((row) => {
    if (!rowMatchesCompanyList(row, companyTokens)) {
      return false;
    }
    if (query) {
      const haystack = [
        row.ticker,
        row.companyName,
        row.industry,
        row.sector,
        row.region,
        row.primaryTicker,
        row.stockIds,
      ]
        .map((value) => displayValue(value).toLowerCase())
        .join(" ");
      if (!haystack.includes(query)) {
        return false;
      }
    }
    if (fx && displayValue(row.quotesCurrency) !== fx && displayValue(row.financialCurrency) !== fx) {
      return false;
    }
    if (minMcap != null) {
      const marketCap = numeric(row, "marketCap");
      if (marketCap == null || marketCap < minMcap) {
        return false;
      }
    }
    if (minEbitda != null) {
      const ebitda = numeric(row, "ebitdaLtm");
      if (ebitda == null || ebitda < minEbitda) {
        return false;
      }
    }
    return true;
  });
}

function sortedRows(rows) {
  const key = state.sortKey;
  const direction = state.sortDir === "asc" ? 1 : -1;
  const column = state.schema.columns.find((item) => item.key === key);
  const numericSort = column && column.type !== "text";
  return [...rows].sort((left, right) => {
    if (numericSort) {
      const a = numeric(left, key);
      const b = numeric(right, key);
      if (a == null && b == null) {
        return 0;
      }
      if (a == null) {
        return 1;
      }
      if (b == null) {
        return -1;
      }
      return (a - b) * direction;
    }
    const a = displayValue(left[key]).toLowerCase();
    const b = displayValue(right[key]).toLowerCase();
    return a.localeCompare(b) * direction;
  });
}

function formatCell(row, column) {
  if (column.key === "ebitdaMargin") {
    const value = numeric(row, "ebitdaMargin");
    if (value == null) {
      return "";
    }
    return `${(value * 100).toFixed(1)}%`;
  }
  return displayValue(row[column.key]);
}

function renderFxOptions(rows) {
  const current = $("fx-filter").value;
  const currencies = new Set();
  for (const row of rows) {
    const quote = displayValue(row.quotesCurrency);
    const financial = displayValue(row.financialCurrency);
    if (quote) {
      currencies.add(quote);
    }
    if (financial) {
      currencies.add(financial);
    }
  }
  fillSelect(
    $("fx-filter"),
    ["", ...[...currencies].sort()],
    (item) => item,
    (item) => item || "All"
  );
  $("fx-filter").value = currencies.has(current) ? current : "";
}

function renderTable() {
  if (!state.schema) {
    return;
  }
  const columns = visibleColumns();
  const rows = sortedRows(filteredRows());
  const pageSize = Number($("page-size").value);
  const pages = pageSize === 0 ? 1 : Math.max(1, Math.ceil(rows.length / pageSize));
  if (state.page >= pages) {
    state.page = 0;
  }
  const start = pageSize === 0 ? 0 : state.page * pageSize;
  const pageRows = pageSize === 0 ? rows : rows.slice(start, start + pageSize);

  const thead = document.querySelector("#results thead");
  const headerRow = document.createElement("tr");
  columns.forEach((column, index) => {
    const th = document.createElement("th");
    th.textContent = column.label;
    th.dataset.key = column.key;
    if (column.type !== "text") {
      th.classList.add("num");
    }
    if (index === 0) {
      th.classList.add("sticky");
    }
    if (index === 1) {
      th.classList.add("sticky-2");
    }
    if (state.sortKey === column.key) {
      th.classList.add(state.sortDir === "asc" ? "sort-asc" : "sort-desc");
    }
    th.addEventListener("click", () => {
      if (state.sortKey === column.key) {
        state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
      } else {
        state.sortKey = column.key;
        state.sortDir = column.type === "text" ? "asc" : "desc";
      }
      renderTable();
    });
    headerRow.append(th);
  });
  thead.replaceChildren(headerRow);

  const tbody = document.querySelector("#results tbody");
  tbody.replaceChildren();
  for (const row of pageRows) {
    const tr = document.createElement("tr");
    columns.forEach((column, index) => {
      const td = document.createElement("td");
      const text = formatCell(row, column);
      td.textContent = text;
      if (column.type !== "text") {
        td.classList.add("num");
        const value = numeric(row, column.key);
        if (value != null && value < 0) {
          td.classList.add("neg");
        } else if (column.key.includes("Change") && value > 0) {
          td.classList.add("pos");
        }
      }
      if (index === 0) {
        td.classList.add("sticky");
      }
      if (index === 1) {
        td.classList.add("sticky-2");
      }
      tr.append(td);
    });
    tbody.append(tr);
  }

  $("page-label").textContent = `${rows.length} rows · page ${state.page + 1}/${pages}`;
  $("prev").disabled = state.page <= 0;
  $("next").disabled = state.page >= pages - 1;
}

function setRows(rows, message, sourceRows = null) {
  if (sourceRows) {
    state.sourceRows = sourceRows;
  } else if ($("view").value === "listings") {
    state.sourceRows = rows;
  }
  state.rows = rows;
  state.page = 0;
  renderFxOptions(rows);
  renderTable();
  setStatus(message);
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

function exportCsv() {
  const columns = visibleColumns();
  const rows = sortedRows(filteredRows());
  const lines = [
    columns.map((column) => csvEscape(column.label)).join(","),
    ...rows.map((row) => columns.map((column) => csvEscape(formatCell(row, column))).join(",")),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "yahoo-screener.csv";
  link.click();
  URL.revokeObjectURL(url);
}

async function loadSnapshots() {
  const data = await api("/snapshots");
  const current = $("snapshot").value;
  fillSelect(
    $("snapshot"),
    [{ id: "", name: "Select a saved JSON file" }, ...data.snapshots],
    (item) => item.id,
    (item) => (item.id ? `${item.id} (${item.modified})` : item.name)
  );
  if (current) {
    $("snapshot").value = current;
  }
}

async function loadSnapshot() {
  const id = $("snapshot").value;
  if (!id) {
    setStatus("Choose a snapshot first.", true);
    return;
  }
  setStatus("Loading snapshot…");
  const data = await api(`/snapshot?id=${encodeURIComponent(id)}&view=${encodeURIComponent($("view").value)}`);
  setRows(data.rows, `Loaded ${data.count} ${data.view} from ${id}`);
}

function extractUploadedRows(payload) {
  if (Array.isArray(payload.rows)) {
    return payload.rows;
  }
  if (Array.isArray(payload.organizations)) {
    return payload.organizations.map((org) => {
      const listing = (org.parameters && org.parameters.listings && org.parameters.listings[0]) || {};
      return {
        ...listing,
        companyName: org.companyName,
        sector: org.sector,
        industry: org.industry,
        primaryTicker: org.primaryTicker,
        ticker: org.primaryTicker || listing.ticker,
        listingCount: org.listingCount,
        stockIds: ((org.parameters && org.parameters.stockIds) || []).join(", "),
      };
    });
  }
  const page = (((payload.finance || {}).result) || [])[0] || {};
  return page.records || [];
}

async function init() {
  try {
    state.schema = await api("/schema");
  } catch (error) {
    setStatus(`API unavailable (${error.message}). Start the app with: uv run python -m naas_abi_marketplace.applications.yahoofinance.apps.screener`, true);
    return;
  }
  fillDatalist($("sector-list"), state.schema.sectors);
  fillDatalist($("industry-list"), state.schema.industries);
  fillSelect(
    $("sort-field"),
    state.schema.sortFields,
    (item) => item.value,
    (item) => item.label
  );
  setChecks($("regions"), state.schema.regions, state.schema.defaults.regions);
  renderIncludeFields(state.schema);
  applyDefaults(state.schema);
  renderColumnPanel(state.schema);
  fillSelect(
    $("watchlist"),
    [{ id: "", label: "All companies" }, ...(state.schema.watchlists || [])],
    (item) => item.id,
    (item) => item.label
  );
  await loadSnapshots();
  setStatus("Ready. Run the screener or load a snapshot.");
}

$("query-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Running screener…");
  $("payload-panel").classList.add("hidden");
  try {
    const data = await api("/run", {
      method: "POST",
      body: JSON.stringify(formBody()),
    });
    setRows(
      data.rows,
      `Yahoo returned ${data.count} ${data.view}${data.total ? ` (total ${data.total})` : ""}${data.savedTo ? `. Saved to ${data.savedTo}` : ""}`
    );
    await loadSnapshots();
  } catch (error) {
    setStatus(error.message, true);
  }
});

$("preview").addEventListener("click", async () => {
  try {
    const data = await api("/payload", {
      method: "POST",
      body: JSON.stringify(formBody()),
    });
    $("payload-panel").textContent = JSON.stringify(data, null, 2);
    $("payload-panel").classList.remove("hidden");
    setStatus("Payload preview updated.");
  } catch (error) {
    setStatus(error.message, true);
  }
});

$("load-snapshot").addEventListener("click", async () => {
  try {
    await loadSnapshot();
  } catch (error) {
    setStatus(error.message, true);
  }
});

$("upload").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) {
    return;
  }
  try {
    const payload = JSON.parse(await file.text());
    const view = $("view").value;
    if (view === "organizations" && Array.isArray((((payload.finance || {}).result) || [])[0]?.records)) {
      const data = await api("/dedup", {
        method: "POST",
        body: JSON.stringify({ records: payload.finance.result[0].records, view }),
      });
      setRows(data.rows, `Deduped upload into ${data.count} organizations`);
      return;
    }
    const rows = extractUploadedRows(payload);
    setRows(rows, `Loaded ${rows.length} rows from ${file.name}`);
  } catch (error) {
    setStatus(error.message, true);
  }
});

$("view").addEventListener("change", async () => {
  const id = $("snapshot").value;
  if (id) {
    try {
      await loadSnapshot();
      return;
    } catch (error) {
      setStatus(error.message, true);
    }
  }
  if ($("view").value === "listings") {
    if (state.sourceRows.length) {
      setRows(state.sourceRows, `Showing ${state.sourceRows.length} listings`);
    }
    return;
  }
  if (!state.sourceRows.length) {
    return;
  }
  try {
    const data = await api("/dedup", {
      method: "POST",
      body: JSON.stringify({ records: state.sourceRows, view: "organizations" }),
    });
    setRows(data.rows, `Grouped into ${data.count} organizations`, state.sourceRows);
  } catch (error) {
    setStatus(error.message, true);
  }
});

["filter", "fx-filter", "min-mcap", "min-ebitda", "page-size", "company-list"].forEach((id) => {
  $(id).addEventListener("input", () => {
    state.page = 0;
    renderTable();
  });
  $(id).addEventListener("change", () => {
    state.page = 0;
    renderTable();
  });
});

$("watchlist").addEventListener("change", () => {
  const id = $("watchlist").value;
  if (!id) {
    $("company-list").value = "";
  } else {
    const list = (state.schema.watchlists || []).find((item) => item.id === id);
    $("company-list").value = list ? list.tokens.join(", ") : "";
  }
  state.page = 0;
  renderTable();
});

$("prev").addEventListener("click", () => {
  state.page -= 1;
  renderTable();
});
$("next").addEventListener("click", () => {
  state.page += 1;
  renderTable();
});
$("columns-toggle").addEventListener("click", () => {
  $("column-panel").classList.toggle("hidden");
});
$("export-csv").addEventListener("click", exportCsv);
$("regions-all").addEventListener("click", () => {
  document.querySelectorAll("#regions input").forEach((input) => {
    input.checked = true;
  });
});
$("regions-none").addEventListener("click", () => {
  document.querySelectorAll("#regions input").forEach((input) => {
    input.checked = false;
  });
});
$("fields-all").addEventListener("click", () => {
  document.querySelectorAll("#include-fields input").forEach((input) => {
    input.checked = true;
  });
});
$("fields-none").addEventListener("click", () => {
  document.querySelectorAll("#include-fields input").forEach((input) => {
    input.checked = false;
  });
});

init();
