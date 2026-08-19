function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function changedTriples(row) {
  const triples = row.type === "delete" ? row.triples_deleted : row.triples_added;
  return Array.isArray(triples) ? triples : [];
}

function triplesCell(row, index) {
  const count = changedTriples(row).length;
  if (!count) {
    return `<td class="muted">-</td>`;
  }
  return `<td>
    <button class="log-triples-open" type="button" data-log-row="${index}" aria-haspopup="dialog">
      ${count} ${count === 1 ? "triple" : "triples"}
    </button>
  </td>`;
}

function turtleResource(value) {
  const text = String(value ?? "");
  if (text.startsWith("_:")) return text;
  return `<${text.replace(/\\/g, "\\\\").replace(/>/g, "\\>")}>`;
}

function turtleObject(value) {
  const text = String(value ?? "");
  if (/^(?:[a-z][a-z0-9+.-]*:|_:)/i.test(text)) {
    return turtleResource(text);
  }
  return JSON.stringify(text);
}

function formatTurtle(triples) {
  return triples
    .map(
      (triple) =>
        `${turtleResource(triple.subject)} ${turtleResource(triple.predicate)} ${turtleObject(triple.object)} .`
    )
    .join("\n");
}

function dateCell(value) {
  if (!value) return `<td class="muted">-</td>`;
  const [date, time] = String(value).split("T");
  return `<td class="log-date">
    <time datetime="${esc(value)}">${esc(date)}${time ? `<small>${esc(time)}</small>` : ""}</time>
  </td>`;
}

function resourceCell(label, uri, meta = "") {
  if (!label && !uri) return `<td class="muted">-</td>`;
  return `<td>
    <details class="log-resource">
      <summary>${esc(label || "Resource")}</summary>
      ${meta ? `<span class="log-resource-meta">${esc(meta)}</span>` : ""}
      ${uri ? `<code>${esc(uri)}</code>` : ""}
    </details>
  </td>`;
}

function processCell(row) {
  return `<td class="log-process-id">
    <details class="log-resource">
      <summary>${esc(row.process_label || "Graph mutation")}</summary>
      <span class="log-resource-meta">Mutation URI</span>
      <code>${esc(row.process_id)}</code>
    </details>
  </td>`;
}

/** @param {HTMLElement} el @param {{ loadJson: (rel: string) => Promise<object> }} ctx */
export async function mountPage(el, ctx) {
  const ledger = await ctx.loadJson("logs/ledger.json");
  const rows = ledger.records || [];
  const body = rows
    .map(
      (row, index) => `<tr>
        ${processCell(row)}
        ${dateCell(row.started_at)}
        ${dateCell(row.completed_at)}
        ${resourceCell(row.actor, row.actor_id)}
        ${resourceCell(row.server_label, row.server_site_id, row.server_ip)}
        <td><span class="log-operation ${row.type === "delete" ? "delete" : "insert"}">${esc(row.type)}</span></td>
        <td><span class="log-status ${row.status === "succeeded" ? "success" : "error"}">${esc(row.status)}</span></td>
        ${triplesCell(row, index)}
        ${resourceCell(row.target_graph_label, row.target_graph)}
      </tr>`
    )
    .join("");

  el.innerHTML = `
    <div class="panel logs-panel">
      <h2>Graph mutation log</h2>
      <div class="ledger-scroll">
        <table class="ledger-table logs-table">
          <thead>
            <tr>
              <th>Process<small>Process</small></th>
              <th>Start<small>Temporal region</small></th>
              <th>End<small>Temporal region</small></th>
              <th>Owner<small>Material entity</small></th>
              <th>Server<small>Site · IP address</small></th>
              <th>Type<small>Quality</small></th>
              <th>Status<small>Quality</small></th>
              <th>Triples<small>GDC</small></th>
              <th>Graph<small>GDC</small></th>
            </tr>
          </thead>
          <tbody>
            ${body || `<tr><td colspan="9" class="muted">No process changes recorded</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
    <dialog class="log-triples-dialog" aria-labelledby="log-triples-dialog-title">
      <header>
        <h2 id="log-triples-dialog-title">Changed triples</h2>
        <button type="button" class="log-dialog-close" aria-label="Close dialog">×</button>
      </header>
      <pre class="log-turtle"></pre>
    </dialog>
  `;

  const dialog = el.querySelector(".log-triples-dialog");
  const dialogTitle = el.querySelector("#log-triples-dialog-title");
  const turtle = el.querySelector(".log-turtle");
  el.querySelectorAll("[data-log-row]").forEach((button) => {
    button.addEventListener("click", () => {
      const row = rows[Number(button.dataset.logRow)];
      dialogTitle.textContent = `${row.type} · ${row.process_id}`;
      turtle.textContent = formatTurtle(changedTriples(row));
      dialog.showModal();
    });
  });
  el.querySelector(".log-dialog-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
}
