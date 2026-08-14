function chip(status) {
  const cls =
    status === "active" ? "" : status === "on-leave" || status === "notice-period" ? "warn" : "muted";
  return `<span class="chip ${cls}">${status}</span>`;
}

function renderBars(rows, labelKey, valueKey) {
  const max = Math.max(...rows.map((r) => r[valueKey]), 1);
  return `<div class="bars">${rows
    .map(
      (r) => `
      <div class="bar-row">
        <span>${r[labelKey]}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${(100 * r[valueKey]) / max}%"></div></div>
        <strong>${r[valueKey]}</strong>
      </div>`
    )
    .join("")}</div>`;
}

function renderPyramid(rows) {
  const max = Math.max(...rows.flatMap((r) => [r.Male || 0, r.Female || 0]), 1);
  return `<div class="pyramid">${rows
    .map((r) => {
      const m = r.Male || 0;
      const f = r.Female || 0;
      return `<div class="pyramid-row">
        <span>${r.band}</span>
        <div class="pyramid-pair">
          <div class="pyramid-male" style="width:${(100 * m) / max}%" title="Male ${m}"></div>
          <div class="pyramid-female" style="width:${(100 * f) / max}%" title="Female ${f}"></div>
        </div>
        <span>${m} · ${f}</span>
      </div>`;
    })
    .join("")}</div>
    <p style="margin:0.7rem 0 0;font-size:0.75rem;color:var(--muted)">Left = Male · Right = Female</p>`;
}

/** @param {HTMLElement} el @param {{ loadJson: (rel: string) => Promise<object> }} ctx */
export async function mountPage(el, ctx) {
  const { loadJson } = ctx;
  const [kpis, roster, families, status, pyramid] = await Promise.all([
    loadJson("workforce/kpis.json"),
    loadJson("workforce/roster.json"),
    loadJson("workforce/by_job_family.json"),
    loadJson("workforce/status_mix.json"),
    loadJson("workforce/age_pyramid.json"),
  ]);
  const k = kpis.kpis;
  el.innerHTML = `
    <div class="kpis">
      <div class="kpi"><span>Active headcount</span><strong>${k.active_headcount.value}</strong></div>
      <div class="kpi"><span>On leave</span><strong>${k.on_leave.value}</strong></div>
      <div class="kpi"><span>Notice period</span><strong>${k.notice_period.value}</strong></div>
      <div class="kpi"><span>Open roles</span><strong>${k.open_roles.value}</strong></div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <h2>Headcount by job family</h2>
        ${renderBars(families.records, "jobFamily", "headcount")}
      </div>
      <div class="panel">
        <h2>Age pyramid</h2>
        ${renderPyramid(pyramid.records)}
      </div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <h2>Status mix</h2>
        ${renderBars(status.records, "status_value", "count")}
      </div>
      <div class="panel">
        <h2>Roster</h2>
        <table>
          <thead><tr><th>Name</th><th>Title</th><th>Family</th><th>Status</th></tr></thead>
          <tbody>
            ${roster.records
              .map(
                (r) => `<tr>
                <td>${r.personLabel}<br><small style="color:var(--muted)">${r.employee_id}</small></td>
                <td>${r.job_title}</td>
                <td>${r.job_family}</td>
                <td>${chip(r.status_value)}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </div>
    <div class="agent-q"><strong>Ask PersonnelAgent:</strong> “Who is on leave?” · “How is headcount split by job family?” · “Tell me about employee E-10428.”</div>
  `;
}
