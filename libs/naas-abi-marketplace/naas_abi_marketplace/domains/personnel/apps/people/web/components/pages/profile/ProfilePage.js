import { fetchPerson } from "../../../lib/api.js";
import { avatarHtml, escapeHtml, flagHtml, highlight, ICONS } from "../../../lib/dom.js";
import { profileHref, searchHref } from "../../../lib/routes.js";
import { sectionHtml } from "../../profile/sections.js";
import { missingDatasetHtml } from "../results/ResultsPage.js";

function relatedHtml(config, related, query) {
  const people = related?.people || [];
  if (!people.length) return "";
  return `
    <section class="card">
      <h2>More in ${escapeHtml(related.value)}</h2>
      <ul class="related">
        ${people
          .map(
            (person) => `
          <li>
            <a href="${profileHref(config, person.slug, { query })}">
              ${avatarHtml(person, "sm")}
              <span>
                <span class="related-name">${escapeHtml(person.full_name)}</span><br />
                <span class="related-headline">${escapeHtml(person.headline || "")}</span>
              </span>
            </a>
          </li>`,
          )
          .join("")}
      </ul>
    </section>`;
}

function notFoundHtml(config, slug) {
  return `
    <div class="results">
      <div class="empty-state">
        <h2>No profile for “${escapeHtml(slug)}”</h2>
        <p>The link may be out of date, or that person may not be in this directory.</p>
        <p><a class="chip" href="${searchHref(config, {})}">Browse everyone</a></p>
      </div>
    </div>`;
}

export async function mountProfile(view, { config, params, slug }) {
  const query = params.get("q") || "";
  view.innerHTML = `<div class="profile"><p class="stats">Loading…</p></div>`;

  let person;
  try {
    person = await fetchPerson(slug);
  } catch (error) {
    view.innerHTML =
      error.detail?.error === "missing_dataset"
        ? `<div class="results">${missingDatasetHtml(error.detail)}</div>`
        : notFoundHtml(config, slug);
    return { showTopbarSearch: true, query, title: config.brand?.name };
  }

  const tokens = query
    ? query
        .normalize("NFKD")
        .replace(/\p{Diacritic}/gu, "")
        .toLowerCase()
        .split(/[^a-z0-9+]+/)
        .filter(Boolean)
    : [];

  const sections = person.sections || [];
  const sideIds = new Set(["sources"]);
  const mainSections = sections.filter((section) => !sideIds.has(section.id));
  const sideSections = sections.filter((section) => sideIds.has(section.id));
  const place = [person.organization, ...(person.place || [])].filter(Boolean);

  view.innerHTML = `
    <div class="profile">
      <div class="intro">
        <div class="intro-cover"></div>
        <div class="intro-body">
          ${avatarHtml(person, "md").replace("avatar-md", "avatar-md intro-photo")}
          <h1 class="intro-name">${highlight(person.full_name, tokens)}</h1>
          <p class="intro-headline">${highlight(person.headline || "", tokens)}</p>
          <p class="intro-place">${flagHtml(person.country_code)}${ICONS.place}
            <span>${escapeHtml(place.join(" · "))}</span></p>
          ${person.quote ? `<p class="intro-quote">${highlight(person.quote, tokens)}</p>` : ""}
          ${
            person.facts?.length
              ? `<dl class="facts">${person.facts
                  .map(
                    (fact) => `<div class="fact">
                      <dt class="fact-label">${escapeHtml(fact.label)}</dt>
                      <dd class="fact-value">${escapeHtml(fact.value)}</dd>
                    </div>`,
                  )
                  .join("")}</dl>`
              : ""
          }
          <div class="actions">
            <button type="button" class="button secondary" data-copy-link>${ICONS.link} Copy link</button>
            ${
              person.public_profile_url
                ? `<a class="button secondary" href="${escapeHtml(person.public_profile_url)}"
                     rel="noopener noreferrer" target="_blank">Published profile</a>`
                : ""
            }
          </div>
        </div>
      </div>

      <div class="profile-columns">
        <div>${mainSections.map((section) => sectionHtml(section, tokens)).join("")}</div>
        <aside class="side">
          ${sideSections.map((section) => sectionHtml(section, tokens)).join("")}
          ${relatedHtml(config, person.related, query)}
        </aside>
      </div>
    </div>`;

  const copyButton = view.querySelector("[data-copy-link]");
  copyButton?.addEventListener("click", async () => {
    // No location.search: inside Nexus it can carry an access token.
    const href = `${location.origin}${location.pathname}${profileHref(config, person.slug)}`;
    try {
      await navigator.clipboard.writeText(href);
      copyButton.textContent = "Link copied";
    } catch {
      copyButton.textContent = href;
    }
  });

  return { showTopbarSearch: true, query, title: `${person.full_name} · ${config.brand?.name}` };
}
