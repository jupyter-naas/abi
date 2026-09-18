/**
 * The registered profile sections.
 *
 * config.yaml chooses which of these appear, in what order, under what title
 * and with what text when they are empty. It cannot add one: a section is a
 * renderer, and a renderer lives here.
 */

import { escapeHtml, highlight, periodText } from "../../lib/dom.js";

const H = (value, tokens) => highlight(value ?? "", tokens);

function entry({ title, meta, text, extra = "" }, tokens) {
  return `
    <div class="entry">
      <div class="entry-head">
        <p class="entry-title">${H(title, tokens)}</p>
        ${meta ? `<p class="entry-meta">${H(meta, tokens)}</p>` : ""}
      </div>
      ${text ? `<p class="entry-text">${H(text, tokens)}</p>` : ""}
      ${extra}
    </div>`;
}

function aboutSection(items, tokens) {
  return items.map((text) => `<p>${H(text, tokens)}</p>`).join("");
}

function experienceSection(items, tokens) {
  return items
    .map((group) => {
      const roles = group.roles || [];
      const single = roles.length === 1;
      if (single) {
        const role = roles[0];
        return entry(
          {
            title: role.title,
            meta: [group.organization, group.location].filter(Boolean).join(" · "),
            text: role.description,
            extra: `<p class="role-meta">${escapeHtml(periodText(role))}</p>`,
          },
          tokens,
        );
      }
      const rolesHtml = roles
        .map(
          (role) => `
          <li class="role">
            <p class="role-title">${H(role.title, tokens)}</p>
            <p class="role-meta">${escapeHtml(periodText(role))}</p>
            ${role.description ? `<p class="entry-text">${H(role.description, tokens)}</p>` : ""}
          </li>`,
        )
        .join("");
      return entry(
        {
          title: group.organization,
          meta: [group.location, periodText(group)].filter(Boolean).join(" · "),
          extra: `<ul class="roles">${rolesHtml}</ul>`,
        },
        tokens,
      );
    })
    .join("");
}

function educationSection(items, tokens) {
  return items
    .map((item) =>
      entry(
        {
          title: item.school,
          meta: [
            [item.degree, item.field_of_study].filter(Boolean).join(", "),
            periodText(item, { presentLabel: "" }),
          ]
            .filter(Boolean)
            .join(" · "),
          text: item.description,
        },
        tokens,
      ),
    )
    .join("");
}

function skillsSection(items, tokens) {
  return `<ul class="chips">${items
    .map((skill) => `<li>${H(skill, tokens)}</li>`)
    .join("")}</ul>`;
}

function certificationsSection(items, tokens) {
  return items
    .map((item) => {
      const meta = [
        item.issuer,
        item.issued ? `Issued ${item.issued.slice(0, 7)}` : "",
        item.expires ? `Expires ${item.expires.slice(0, 7)}` : "",
        item.status,
      ]
        .filter(Boolean)
        .join(" · ");
      const link = item.credential_url
        ? `<p class="entry-text"><a href="${escapeHtml(item.credential_url)}" rel="noopener noreferrer" target="_blank">Show credential</a></p>`
        : "";
      return entry({ title: item.name, meta, extra: link }, tokens);
    })
    .join("");
}

function languagesSection(items, tokens) {
  return items
    .map((item) => entry({ title: item.name, meta: item.proficiency }, tokens))
    .join("");
}

function recommendationsSection(items, tokens) {
  return items
    .map(
      (item) => `
      <div class="quote-card">
        <div class="quote-author">
          <span>
            <span class="quote-author-name">${H(item.author_name, tokens)}</span><br />
            <span class="quote-author-meta">${escapeHtml(
              [item.author_headline, item.relationship, item.written_on].filter(Boolean).join(" · "),
            )}</span>
          </span>
        </div>
        <p>${H(item.content, tokens)}</p>
      </div>`,
    )
    .join("");
}

function interestsSection(items, tokens) {
  return items
    .map((item) => entry({ title: item.name, meta: item.kind, text: item.description }, tokens))
    .join("");
}

function sourcesSection(items) {
  return `<ul class="sources">${items
    .map(
      (item) =>
        `<li><a href="${escapeHtml(item.url)}" rel="noopener noreferrer" target="_blank">${escapeHtml(
          item.label || item.url,
        )}</a></li>`,
    )
    .join("")}</ul>`;
}

export const SECTION_RENDERERS = {
  about: aboutSection,
  experience: experienceSection,
  education: educationSection,
  skills: skillsSection,
  certifications: certificationsSection,
  languages: languagesSection,
  recommendations: recommendationsSection,
  interests: interestsSection,
  sources: sourcesSection,
};

export const REGISTERED_SECTION_IDS = Object.freeze(Object.keys(SECTION_RENDERERS));

export function sectionHtml(section, tokens, { sidebar = false } = {}) {
  const render = SECTION_RENDERERS[section.id];
  if (!render) return "";
  const items = section.items || [];
  const body = items.length
    ? render(items, tokens)
    : // An empty section is stated, not hidden: nothing recorded is an answer.
      `<p class="empty">${escapeHtml(section.empty_text)}</p>`;
  const cardClass = sidebar ? "card profile-sidebar-card" : "card";
  return `
    <section class="${cardClass}" id="section-${escapeHtml(section.id)}" data-section-id="${escapeHtml(section.id)}">
      <h2>${escapeHtml(section.label)}</h2>
      ${body}
    </section>`;
}
