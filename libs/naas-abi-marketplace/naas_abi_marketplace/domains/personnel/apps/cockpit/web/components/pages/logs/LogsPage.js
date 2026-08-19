function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function cell(value) {
  if (value == null || value === "") {
    return `<td class="muted">-</td>`;
  }
  return `<td>${esc(value)}</td>`;
}

function sourceCell(url) {
  if (!url) return `<td class="muted">-</td>`;
  const href = String(url);
  if (/^https?:\/\//i.test(href)) {
    return `<td class="ledger-uri"><a href="${esc(href)}" target="_blank" rel="noreferrer">${esc(href)}</a></td>`;
  }
  return `<td class="ledger-uri" title="${esc(href)}">${esc(href)}</td>`;
}

function dateCell(value) {
  if (!value) return `<td class="muted">-</td>`;
  const text = String(value).slice(0, 10);
  return `<td class="ledger-when">${esc(text)}</td>`;
}

/** @param {HTMLElement} el @param {{ loadJson: (rel: string) => Promise<object> }} ctx */
export async function mountPage(el, ctx) {
  const ledger = await ctx.loadJson("logs/ledger.json");
  const rows = ledger.records || [];

  const body = rows
    .map(
      (row) => `<tr>
        ${cell(row.person_label)}
        ${cell(row.process_type)}
        ${cell(row.title)}
        ${cell(row.organization)}
        ${cell(row.site)}
        ${dateCell(row.start)}
        ${dateCell(row.end)}
        ${sourceCell(row.source)}
      </tr>`
    )
    .join("");

  el.innerHTML = `
    <div class="panel logs-panel">
      <h2>Process log</h2>
      <div class="ledger-scroll">
        <table class="ledger-table logs-table">
          <thead>
            <tr>
              <th>Person</th>
              <th>Process</th>
              <th>Title</th>
              <th>Organization</th>
              <th>Site</th>
              <th>Start</th>
              <th>End</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            ${body || `<tr><td colspan="8" class="muted">No process records</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
    <div class="agent-q"><strong>Ask PersonnelAgent:</strong> "List acts of working." · "What did Hugo Girard work on?"</div>
  `;
}
