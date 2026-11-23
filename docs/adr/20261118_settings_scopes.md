# Settings scopes: what belongs to the platform, what to an organization

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

Nexus has four settings scopes: Platform, Organization, Workspace and Account.
A shared header switches between Platform, Organization and Account (#1493).

Some settings sat at the wrong level. Organization › General showed a read-only
**Domain**, "the domain used to access this organization". It was really the
first verified email domain, and without one, the browser's current host. No
organization is reached by its own domain: every organization of a deployment
shares the same web and API addresses. The **favicon**, the **tab title** and
the **default logo** came from the configuration's `tenant:` block, which no
settings page showed. Meanwhile an organization had no place for its own
identity (legal name, registration, address).

One deployment (a tenant) may host several organizations. A setting that would
make no sense with two organizations on the same deployment is not an
organization's.

## Decision

1. **Platform › General shows the site's identity.** It is the first Platform
   page, read-only, from `tenant:`:
   - the name (`tenant.name`, new and optional; the tab title stands in without it);
   - the tab title, favicon and link preview;
   - the default logo;
   - the look of the sign-in page;
   - the web and API addresses the deployment serves.

   These change in the configuration and apply at the next start. Editing them
   in the app would need storage and permissions of their own.
2. **The favicon and tab title are the platform's only.** A browser has one tab
   icon per site. It shows before anyone signs in, when no organization is known,
   and browsers cache it per site. The identity provider's sign-in pages take
   the same favicon (`branding.favicon_url`).
3. **Logos and colors are layered:** organization, then tenant, then ABI.
   The tenant's logo and colors stand where no organization is known (sign-in,
   the identity provider, mail). An organization's own branding takes over
   inside it. The identity provider follows the same rule: a default
   `branding`, overridden per email domain once the address is known.
4. **An organization's domains are email domains.** Organization › Domains is
   the domains an organization proved it owns (a DNS record): people with these
   addresses are recognized as its own and sign in through the provider the
   domain routes to. They are never an access address. Organization › General
   lists the verified ones.
5. **Organization › General holds the organization's identity:**
   - the name and the read-only organization ID;
   - legal name, registration number, VAT number;
   - website, contact email, postal address.

   Migration `0072_organization_identity` adds these as optional columns.
   - **Who changes them:** owners and admins (`UpdateOrganization`, admin level).
     They can also be given when the organization is created.
   - **Who reads them:** every member, through `GetOrganization` (read level).
   - **Where they never appear:** the public sign-in branding.
   - **Seeding never sets them**, since it rewrites a seeded organization's
     branding on every start.

## Consequences

- One rule places a new setting: if it would not make sense with two
  organizations on the same deployment, it is the platform's.
- Platform › General is read-only. An administrator changes the site identity
  in the configuration, not in the app.
- An organization's identity is visible to all its members. Public business
  details are fine there; anything private (an internal contact) would need its
  own admin-only field.
- `/settings/general` now opens Platform › General. The bare path used to
  redirect to a workspace's General settings; only old bookmarks change.
