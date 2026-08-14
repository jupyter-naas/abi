/** @param {HTMLElement} el @param {{ loadJson: (rel: string) => Promise<object> }} ctx */
export async function mountPage(el, ctx) {
  const { loadJson } = ctx;
  const ledger = await loadJson("logs/ledger.json");
  const entries = ledger.records || [];

  const uriCell = (value) => {
    const text = value || "—";
    return `<td class="ledger-uri" title="${text}">${text}</td>`;
  };

  const cards = entries
    .map((entry) => {
      const triples = (entry.triples || entry.assertions || [])
        .map((t) => {
          const object = t.object ?? t.value_uri ?? t.value ?? "—";
          const predicate = t.predicate_uri ?? t.prop_uri ?? t.relation_uri ?? "—";
          const predicateType = t.predicate_type_uri ?? t.prop_type ?? "—";
          const objectType = t.object_type_uri ?? "—";
          const source = t.source_uri || entry.source_uri || "—";
          const timestamp = t.source_at || t.ledger_at || entry.source_at || entry.ledger_at || "—";
          return `<tr>
            ${uriCell(t.subject_uri)}
            ${uriCell(t.subject_type_uri)}
            ${uriCell(predicate)}
            ${uriCell(predicateType)}
            ${uriCell(object)}
            ${uriCell(objectType)}
            ${uriCell(source)}
            <td class="ledger-when" title="${timestamp}">${timestamp}</td>
          </tr>`;
        })
        .join("");

      return `<article class="ledger-entry">
        <header class="ledger-entry-head">
          <div class="ledger-entry-title">
            <span class="ledger-process">${entry.person_label || "Registration"}</span>
            <span class="ledger-class">${entry.process_uri || entry.process_id || "—"}</span>
          </div>
          <dl class="ledger-meta">
            <div><dt>Source at</dt><dd class="ledger-when">${entry.source_at || entry.ledger_at || "—"}</dd></div>
            <div><dt>Declarant</dt><dd>${entry.declarant_label || "—"}</dd></div>
            <div><dt>Birth</dt><dd class="ledger-uri">${entry.birth_uri || entry.registers_birth || "—"}</dd></div>
            <div><dt>Source</dt><dd class="ledger-uri">${entry.source_uri || entry.source_id || "—"}</dd></div>
          </dl>
          ${entry.declared_content ? `<p class="ledger-quote">${entry.declared_content}</p>` : ""}
        </header>
        <div class="ledger-scroll">
          <table class="ledger-table ledger-assertions">
            <thead><tr>
              <th>Subject</th>
              <th>Subject type</th>
              <th>Predicate</th>
              <th>Predicate type</th>
              <th>Object</th>
              <th>Object type</th>
              <th>Source</th>
              <th>Timestamp</th>
            </tr></thead>
            <tbody>${triples || `<tr><td colspan="8" class="muted">No facts recorded</td></tr>`}</tbody>
          </table>
        </div>
      </article>`;
    })
    .join("");

  el.innerHTML = `
    <div class="ledger-stack">${cards}</div>
    <div class="agent-q"><strong>Ask PersonnelAgent:</strong> “List birth registrations.” · “Reconstruct Emma Petit’s registration lineage.”</div>
  `;
}
