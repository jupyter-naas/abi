/**
 * "Import LinkedIn data": upload a LinkedIn export (.zip, or the folder it
 * unpacks to) and follow the import until it is done.
 *
 * Shown only when the instance switches it on (config.imports.linkedin) and
 * the page runs inside Nexus, where the viewer has a session the upload is
 * made under. The routes are the instance's: GET linkedin/owners says whose
 * export the viewer may import (their own, or a colleague's for an
 * organization admin), POST linkedin/imports starts one, and
 * GET linkedin/imports/<id> reports its progress. POST …/cancel stops it.
 *
 * The dialog does not block the rest of the app: a toast in the top-right
 * corner shows and hides the panel while a run is in progress or finished.
 */

import {
  cancelLinkedInImport,
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
      <div class="sparql-modal-backdrop" data-hide tabindex="-1"></div>
      <div class="sparql-modal-panel linkedin-import-panel" role="dialog" aria-modal="true"
        aria-labelledby="linkedin-import-title">
        <button type="button" class="sparql-modal-close" data-hide aria-label="Hide">×</button>
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
          <ol class="linkedin-import-log" hidden></ol>
          <div class="linkedin-import-result"></div>
          <div class="actions linkedin-import-running" hidden>
            <button type="button" class="button secondary" data-cancel>Cancel</button>
            <button type="button" class="button secondary" data-hide>Hide</button>
          </div>
          <div class="actions linkedin-import-done" hidden>
            <button type="button" class="button" data-done>Close</button>
          </div>
        </div>
      </div>
    </div>`;
}

function toastHtml(label) {
  return `
    <button type="button" class="linkedin-import-toast" hidden>
      <span class="linkedin-import-toast-kicker">LinkedIn</span>
      <span class="linkedin-import-toast-title">${escapeHtml(label)}</span>
      <span class="linkedin-import-toast-stage"></span>
      <span class="linkedin-import-toast-bar"><span></span></span>
    </button>`;
}

function summaryHtml(run) {
  if (run.status === "failed") {
    return `<p class="error-block">${escapeHtml(run.error || "The import failed.")}</p>`;
  }
  if (run.status === "cancelled") {
    return `<p class="stats">Import cancelled.</p>`;
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

function stageLabel(run) {
  if (run.status === "failed") return "Failed";
  if (run.status === "cancelled") return "Cancelled";
  if (run.status === "succeeded") return "Done";
  return run.stage || "Starting";
}

function barWidth(run) {
  if (run.status === "succeeded") return 100;
  return Math.max(0, Math.min(100, Number(run.progress) || 0));
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
  const toastHolder = document.createElement("div");
  toastHolder.innerHTML = toastHtml(label);
  const toast = toastHolder.firstElementChild;
  document.body.append(toast);
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
  const log = progress.querySelector(".linkedin-import-log");
  const result = progress.querySelector(".linkedin-import-result");
  const runningActions = progress.querySelector(".linkedin-import-running");
  const doneActions = progress.querySelector(".linkedin-import-done");
  const toastStage = toast.querySelector(".linkedin-import-toast-stage");
  const toastBar = toast.querySelector(".linkedin-import-toast-bar span");
  let files = [];
  let polling = null;
  let runId = null;
  let finished = false;

  const showPanel = () => {
    modal.hidden = false;
    document.body.classList.add("sparql-modal-open");
  };

  const hidePanel = () => {
    modal.hidden = true;
    document.body.classList.remove("sparql-modal-open");
  };

  const reset = () => {
    files = [];
    finished = false;
    runId = null;
    form.reset();
    form.hidden = false;
    urlField.hidden = true;
    progress.hidden = true;
    runningActions.hidden = true;
    doneActions.hidden = true;
    result.innerHTML = "";
    log.innerHTML = "";
    log.hidden = true;
    chosen.textContent = "";
    submit.disabled = true;
    stage.textContent = "";
    bar.style.width = "0%";
    toast.hidden = true;
    toastStage.textContent = "";
    toastBar.style.width = "0%";
  };

  const paint = (run) => {
    const labelText = stageLabel(run);
    const width = `${barWidth(run)}%`;
    stage.textContent = labelText;
    bar.style.width = width;
    toastStage.textContent = labelText;
    toastBar.style.width = width;
    const lines = Array.isArray(run.logs) ? run.logs : [];
    log.innerHTML = lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("");
    log.hidden = !lines.length;
    if (log.lastElementChild) log.lastElementChild.scrollIntoView({ block: "nearest" });
  };

  const closeDone = () => {
    clearTimeout(polling);
    hidePanel();
    const wasFinished = finished;
    reset();
    if (wasFinished) window.dispatchEvent(new HashChangeEvent("hashchange"));
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

  const follow = async (id) => {
    try {
      const run = await fetchLinkedInImport(id);
      paint(run);
      if (run.status === "running") {
        runningActions.hidden = false;
        doneActions.hidden = true;
        polling = setTimeout(() => follow(id), POLL_MS);
        return;
      }
      finished = run.status === "succeeded";
      result.innerHTML = summaryHtml(run);
      runningActions.hidden = true;
      doneActions.hidden = false;
    } catch (error) {
      result.innerHTML = `<p class="error-block">${escapeHtml(error.detail || error.message)}</p>`;
      runningActions.hidden = true;
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
    runningActions.hidden = false;
    doneActions.hidden = true;
    stage.textContent = "Uploading…";
    bar.style.width = "2%";
    toast.hidden = false;
    toastStage.textContent = "Uploading…";
    toastBar.style.width = "2%";
    try {
      const run = await startLinkedInImport(body);
      runId = run.run_id;
      paint(run);
      await follow(run.run_id);
    } catch (error) {
      if (error.detail?.code === "linkedin_url_required") {
        // Neither the account nor the export names the owner's LinkedIn
        // profile: ask for it, keep the files chosen, and let them retry.
        progress.hidden = true;
        form.hidden = false;
        toast.hidden = true;
        urlField.hidden = false;
        urlWhy.textContent = error.detail.message;
        submit.disabled = false;
        urlInput.focus();
        return;
      }
      const detail =
        typeof error.detail === "string" ? error.detail : error.detail?.message || error.message;
      stage.textContent = "Not imported";
      toastStage.textContent = "Not imported";
      result.innerHTML = `<p class="error-block">${escapeHtml(detail)}</p>`;
      runningActions.hidden = true;
      doneActions.hidden = false;
    }
  });

  modal.addEventListener("click", async (event) => {
    if (event.target.closest("[data-done]")) {
      closeDone();
      return;
    }
    if (event.target.closest("[data-hide]")) {
      hidePanel();
      return;
    }
    if (event.target.closest("[data-cancel]") && runId) {
      event.target.closest("[data-cancel]").disabled = true;
      try {
        await cancelLinkedInImport(runId);
      } catch (error) {
        result.innerHTML = `<p class="error-block">${escapeHtml(error.detail || error.message)}</p>`;
      }
    }
  });
  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") hidePanel();
  });
  toast.addEventListener("click", () => {
    if (modal.hidden) showPanel();
    else hidePanel();
  });

  return async () => {
    if (runId) {
      showPanel();
      return;
    }
    reset();
    showPanel();
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
      runningActions.hidden = true;
      doneActions.hidden = false;
    }
  };
}
