/**
 * "Import LinkedIn data": upload a LinkedIn export (.zip, or the folder it
 * unpacks to) and follow the import until it is done.
 *
 * Shown only when the instance switches it on (config.imports.linkedin) and
 * the page runs inside Nexus, where the viewer has a session the upload is
 * made under. The routes are the instance's: GET linkedin/owners says whose
 * export the viewer may import (their own, or a colleague's for an
 * organization admin), POST linkedin/imports starts one, and
 * GET linkedin/imports/<id> reports its progress.
 */

import {
  fetchLinkedInImport,
  fetchLinkedInOwners,
  startLinkedInImport,
} from "../lib/api.js";
import { escapeHtml } from "../lib/dom.js";
import { isBundledInNexus } from "../lib/nexus.js";

const POLL_MS = 1000;

export function linkedInImportEnabled(config) {
  return Boolean(config.imports?.linkedin?.enabled) && isBundledInNexus();
}

function dialogHtml(label) {
  return `
    <div class="sparql-modal linkedin-import" hidden>
      <div class="sparql-modal-backdrop" data-close tabindex="-1"></div>
      <div class="sparql-modal-panel linkedin-import-panel" role="dialog" aria-modal="true"
        aria-labelledby="linkedin-import-title">
        <button type="button" class="sparql-modal-close" data-close aria-label="Close">×</button>
        <p class="sparql-modal-kicker">LinkedIn</p>
        <h2 class="sparql-modal-title" id="linkedin-import-title">${escapeHtml(label)}</h2>
        <form class="linkedin-import-form">
          <p class="linkedin-import-help">
            Upload the data export LinkedIn sends you (Settings › Data privacy ›
            Get a copy of your data): the <b>.zip</b> as it is, or the folder it unpacks to.
            Your connections are kept in your own drive and graph.
          </p>
          <label class="linkedin-import-owner" hidden>
            <span>Whose export is it?</span>
            <select name="owner_id"></select>
          </label>
          <div class="linkedin-import-pickers">
            <label class="button secondary">
              <input type="file" name="zip" accept=".zip,application/zip" hidden />
              Choose a .zip
            </label>
            <label class="button secondary">
              <input type="file" name="folder" webkitdirectory directory multiple hidden />
              Choose a folder
            </label>
          </div>
          <p class="linkedin-import-chosen stats"></p>
          <label class="linkedin-import-url" hidden>
            <span class="linkedin-import-url-why"></span>
            <input type="url" name="owner_linkedin_url"
              placeholder="https://www.linkedin.com/in/their-name" />
          </label>
          <div class="actions">
            <button type="submit" class="button" disabled>Import</button>
          </div>
        </form>
        <div class="linkedin-import-progress" hidden>
          <p class="linkedin-import-stage stats"></p>
          <div class="linkedin-import-bar"><span></span></div>
          <div class="linkedin-import-result"></div>
          <div class="actions" hidden>
            <button type="button" class="button" data-done>Close</button>
          </div>
        </div>
      </div>
    </div>`;
}

function summaryHtml(run) {
  if (run.status === "failed") {
    return `<p class="error-block">${escapeHtml(run.error || "The import failed.")}</p>`;
  }
  const result = run.result || {};
  const line = (count, text) =>
    `<li><b>${Number(count || 0).toLocaleString()}</b> ${escapeHtml(text)}</li>`;
  return `<ul class="linkedin-import-summary">
    ${line(result.created, "people created")}
    ${line(result.matched, "people matched to existing ones")}
    ${line(result.skipped, "rows skipped (no LinkedIn profile URL, or repeated)")}
  </ul>
  <p class="stats">Imported for ${escapeHtml(run.owner_name)}${
    result.owner_linkedin_url
      ? ` (<a href="${escapeHtml(result.owner_linkedin_url)}" target="_blank" rel="noopener">${escapeHtml(
          result.owner_linkedin_url.replace(/^https:\/\/www\./, ""),
        )}</a>)`
      : ""
  }.</p>`;
}

let openDialog = null;

/** The import button. Every button opens the one dialog of the page. */
export function linkedInImportButton(config) {
  const label = config.imports?.linkedin?.label || "Import LinkedIn data";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "button secondary linkedin-import-open";
  button.textContent = label;
  openDialog ??= wireDialog(label);
  button.addEventListener("click", () => openDialog());
  return button;
}

/** Build the dialog once and return what opens it. */
function wireDialog(label) {
  const holder = document.createElement("div");
  holder.innerHTML = dialogHtml(label);
  const modal = holder.firstElementChild;
  document.body.append(modal);
  const form = modal.querySelector(".linkedin-import-form");
  const owner = modal.querySelector(".linkedin-import-owner");
  const select = owner.querySelector("select");
  const zipInput = form.querySelector('input[name="zip"]');
  const folderInput = form.querySelector('input[name="folder"]');
  const chosen = form.querySelector(".linkedin-import-chosen");
  const urlField = form.querySelector(".linkedin-import-url");
  const urlWhy = urlField.querySelector(".linkedin-import-url-why");
  const urlInput = urlField.querySelector("input");
  const submit = form.querySelector('button[type="submit"]');
  const progress = modal.querySelector(".linkedin-import-progress");
  const stage = progress.querySelector(".linkedin-import-stage");
  const bar = progress.querySelector(".linkedin-import-bar span");
  const result = progress.querySelector(".linkedin-import-result");
  const doneActions = progress.querySelector(".actions");
  let files = [];
  let polling = null;
  let finished = false;

  const reset = () => {
    files = [];
    finished = false;
    form.reset();
    form.hidden = false;
    urlField.hidden = true;
    progress.hidden = true;
    doneActions.hidden = true;
    result.innerHTML = "";
    chosen.textContent = "";
    submit.disabled = true;
  };

  const close = () => {
    clearTimeout(polling);
    modal.hidden = true;
    document.body.classList.remove("sparql-modal-open");
    // A finished import changed the datasets: show the search again.
    if (finished) window.dispatchEvent(new HashChangeEvent("hashchange"));
  };

  const choose = (picked, describe) => {
    files = picked;
    chosen.textContent = files.length ? describe(files) : "";
    submit.disabled = !files.length;
  };

  // Another owner may have their URL on their account: ask again only if needed.
  select.addEventListener("change", () => {
    urlField.hidden = true;
    urlInput.value = "";
  });

  zipInput.addEventListener("change", () => {
    folderInput.value = "";
    choose([...zipInput.files].map((file) => [file, file.name]), ([[file]]) => file.name);
  });
  folderInput.addEventListener("change", () => {
    zipInput.value = "";
    const picked = [...folderInput.files].map((file) => [
      file,
      file.webkitRelativePath || file.name,
    ]);
    choose(picked, (items) => {
      const folder = items[0][1].split("/")[0];
      return `${folder} · ${items.length} files`;
    });
  });

  const follow = async (runId) => {
    try {
      const run = await fetchLinkedInImport(runId);
      stage.textContent = run.status === "running" ? run.stage : run.status === "failed" ? "Failed" : "Done";
      bar.style.width = `${run.progress || 0}%`;
      if (run.status === "running") {
        polling = setTimeout(() => follow(runId), POLL_MS);
        return;
      }
      finished = run.status === "succeeded";
      result.innerHTML = summaryHtml(run);
      doneActions.hidden = false;
    } catch (error) {
      result.innerHTML = `<p class="error-block">${escapeHtml(error.detail || error.message)}</p>`;
      doneActions.hidden = false;
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!files.length) return;
    const body = new FormData();
    if (!owner.hidden && select.value) body.set("owner_id", select.value);
    if (!urlField.hidden) body.set("owner_linkedin_url", urlInput.value.trim());
    for (const [file, path] of files) body.append("files", file, path);
    submit.disabled = true;
    form.hidden = true;
    progress.hidden = false;
    stage.textContent = "Uploading…";
    bar.style.width = "2%";
    try {
      const run = await startLinkedInImport(body);
      await follow(run.run_id);
    } catch (error) {
      if (error.detail?.code === "linkedin_url_required") {
        // Neither the account nor the export names the owner's LinkedIn
        // profile: ask for it, keep the files chosen, and let them retry.
        progress.hidden = true;
        form.hidden = false;
        urlField.hidden = false;
        urlWhy.textContent = error.detail.message;
        submit.disabled = false;
        urlInput.focus();
        return;
      }
      const detail =
        typeof error.detail === "string" ? error.detail : error.detail?.message || error.message;
      stage.textContent = "Not imported";
      result.innerHTML = `<p class="error-block">${escapeHtml(detail)}</p>`;
      doneActions.hidden = false;
    }
  });

  modal.addEventListener("click", (event) => {
    if (event.target.closest("[data-close], [data-done]")) close();
  });
  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });

  return async () => {
    reset();
    modal.hidden = false;
    document.body.classList.add("sparql-modal-open");
    try {
      const owners = await fetchLinkedInOwners();
      select.innerHTML = owners.owners
        .map(
          (user) =>
            `<option value="${escapeHtml(user.id)}"${user.id === owners.me ? " selected" : ""}>${escapeHtml(
              user.id === owners.me ? `${user.name} (me)` : user.name,
            )}</option>`,
        )
        .join("");
      owner.hidden = !owners.can_import_for_others;
    } catch (error) {
      form.hidden = true;
      progress.hidden = false;
      stage.textContent = "Not available here";
      result.innerHTML = `<p class="error-block">${escapeHtml(
        typeof error.detail === "string" ? error.detail : error.message,
      )}</p>`;
      doneActions.hidden = false;
    }
  };
}
