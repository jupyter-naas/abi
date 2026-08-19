function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function chip(status) {
  const cls =
    status === "active"
      ? ""
      : status === "on-leave" || status === "notice-period"
        ? "warn"
        : "muted";
  return `<span class="chip ${cls}">${esc(status)}</span>`;
}

function formatYears(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toFixed(1)} yrs`;
}

const ROSTER_COLUMNS = [
  {
    key: "personLabel",
    label: "Name",
    sortValue: (row) => row.personLabel || "",
    filterValue: (row) => row.personLabel || "",
    render: (row) => `<strong>${esc(row.personLabel)}</strong>`,
  },
  {
    key: "job_title",
    label: "Role",
    sortValue: (row) => row.job_title || "",
    filterValue: (row) => row.job_title || "",
    render: (row) => esc(row.job_title || "-"),
  },
  {
    key: "org_tenure_years",
    label: "Time at org",
    sortValue: (row) => Number(row.org_tenure_years) || 0,
    filterValue: (row) => formatYears(row.org_tenure_years),
    render: (row) => formatYears(row.org_tenure_years),
  },
  {
    key: "experience_count",
    label: "Experiences",
    sortValue: (row) => Number(row.experience_count) || 0,
    filterValue: (row) => String(row.experience_count ?? ""),
    render: (row) => esc(row.experience_count ?? 0),
  },
  {
    key: "seniority_years",
    label: "Seniority",
    sortValue: (row) => Number(row.seniority_years) || 0,
    filterValue: (row) => formatYears(row.seniority_years),
    render: (row) => formatYears(row.seniority_years),
  },
  {
    key: "education_count",
    label: "Education",
    sortValue: (row) => Number(row.education_count) || 0,
    filterValue: (row) => String(row.education_count ?? 0),
    render: (row) => esc(row.education_count ?? 0),
  },
  {
    key: "scolarity_years",
    label: "Scolarity",
    sortValue: (row) => Number(row.scolarity_years) || 0,
    filterValue: (row) => formatYears(row.scolarity_years),
    render: (row) =>
      Number(row.scolarity_years) > 0 ? formatYears(row.scolarity_years) : "-",
  },
  {
    key: "status_value",
    label: "Status",
    sortValue: (row) => row.status_value || "",
    filterValue: (row) => row.status_value || "",
    render: (row) => chip(row.status_value || "unknown"),
  },
];

function compareValues(a, b) {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

function mountDataTable(tableRoot, rows, columns, countEl, filterNoteEl, { initialFilters = {} } = {}) {
  if (!tableRoot) return () => {};

  let sortKey = "personLabel";
  let sortDir = 1;
  const filters = Object.fromEntries(
    columns.map((column) => [column.key, initialFilters[column.key] || ""])
  );

  const updateFilterNote = () => {
    if (!filterNoteEl) return;
    const status = filters.status_value?.trim();
    filterNoteEl.textContent = status ? `Status: ${status}` : "All statuses";
  };

  const filteredRows = () => {
    const queryByKey = Object.fromEntries(
      Object.entries(filters).map(([key, value]) => [key, value.trim().toLowerCase()])
    );
    return rows.filter((row) =>
      columns.every((column) => {
        const query = queryByKey[column.key];
        if (!query) return true;
        return String(column.filterValue(row)).toLowerCase().includes(query);
      })
    );
  };

  const sortedRows = () => {
    const column = columns.find((entry) => entry.key === sortKey) || columns[0];
    const sorted = [...filteredRows()].sort((left, right) => {
      const result = compareValues(column.sortValue(left), column.sortValue(right));
      return result * sortDir;
    });
    return sorted;
  };

  const render = () => {
    const body = sortedRows()
      .map(
        (row) =>
          `<tr>${columns.map((column) => `<td>${column.render(row)}</td>`).join("")}</tr>`
      )
      .join("");
    tableRoot.querySelector("[data-table-body]").innerHTML =
      body || `<tr><td colspan="${columns.length}" class="muted">No matching members</td></tr>`;
    if (countEl) {
      const total = sortedRows().length;
      const status = filters.status_value?.trim().toLowerCase();
      countEl.textContent =
        status === "active" ? `${total} active` : `${total} shown`;
    }
    updateFilterNote();
    for (const th of tableRoot.querySelectorAll("[data-sort-key]")) {
      const active = th.dataset.sortKey === sortKey;
      th.dataset.sortActive = active ? "true" : "false";
      th.dataset.sortDir = active ? (sortDir === 1 ? "asc" : "desc") : "";
    }
  };

  tableRoot.addEventListener("click", (event) => {
    const header = event.target.closest("[data-sort-key]");
    if (!header) return;
    const key = header.dataset.sortKey;
    if (sortKey === key) sortDir *= -1;
    else {
      sortKey = key;
      sortDir = 1;
    }
    render();
  });

  tableRoot.addEventListener("input", (event) => {
    const input = event.target.closest("[data-filter-key]");
    if (!input) return;
    filters[input.dataset.filterKey] = input.value;
    render();
  });

  render();
  for (const input of tableRoot.querySelectorAll("[data-filter-key]")) {
    const key = input.dataset.filterKey;
    if (filters[key]) input.value = filters[key];
  }
  return () => {};
}

/** @param {HTMLElement} el @param {{ loadJson: (rel: string) => Promise<object> }} ctx */
export async function mountPage(el, ctx) {
  const { loadJson } = ctx;
  const [kpis, roster] = await Promise.all([
    loadJson("dashboard/kpis.json"),
    loadJson("dashboard/roster.json"),
  ]);
  const k = kpis.kpis || {};
  const rosterRows = roster.records || [];
  const activeCount = rosterRows.filter((row) => row.status_value === "active").length;
  const year = new Date().getFullYear();

  el.innerHTML = `
    <div class="dashboard-page">
      <div class="kpis">
        <div class="kpi">
          <span>Active Headcount</span>
          <strong>${esc(k.active_headcount?.value ?? 0)}</strong>
        </div>
        <div class="kpi">
          <span>Time working for org in ${year}</span>
          <strong>${esc(formatYears(k.org_time_in_year?.value ?? 0))}</strong>
        </div>
        <div class="kpi">
          <span>Seniority</span>
          <strong>${esc(formatYears(k.avg_seniority?.value ?? 0))}</strong>
          <small class="kpi-note">Average across all members</small>
        </div>
        <div class="kpi">
          <span>Scolarity</span>
          <strong>${esc(formatYears(k.avg_scolarity?.value ?? 0))}</strong>
          <small class="kpi-note">Average across members with education</small>
        </div>
      </div>

      <div class="roster-heading">
        <div class="roster-heading-text">
          <h2>Roster</h2>
          <span class="roster-filter-note" data-roster-filter-note>Status: active</span>
        </div>
        <span class="roster-count" data-table-count>${activeCount} active</span>
      </div>

      <div class="panel dashboard-table-panel">
        <div class="data-table-wrap" data-roster-table>
          <table class="data-table">
            <thead>
              <tr class="data-table-head">
                ${ROSTER_COLUMNS.map(
                  (column) =>
                    `<th scope="col"><button type="button" class="data-table-sort" data-sort-key="${esc(column.key)}">${esc(column.label)}<span class="data-table-sort-indicator" aria-hidden="true"></span></button></th>`
                ).join("")}
              </tr>
              <tr class="data-table-filters">
                ${ROSTER_COLUMNS.map(
                  (column) =>
                    `<th><input type="search" class="data-table-filter" data-filter-key="${esc(column.key)}" placeholder="Filter" aria-label="Filter ${esc(column.label)}" spellcheck="false" autocomplete="off"></th>`
                ).join("")}
              </tr>
            </thead>
            <tbody data-table-body></tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  return mountDataTable(
    el.querySelector("[data-roster-table]"),
    rosterRows,
    ROSTER_COLUMNS,
    el.querySelector("[data-table-count]"),
    el.querySelector("[data-roster-filter-note]"),
    { initialFilters: { status_value: "active" } }
  );
}
