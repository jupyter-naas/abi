/**
 * Organization Settings › General: the organization's identity, the pure part (what
 * the form edits, and the `PATCH /api/organizations/<id>` body of what changed).
 */

export const IDENTITY_FIELDS = [
  'name',
  'legal_name',
  'registration_number',
  'vat_number',
  'website',
  'contact_email',
  'address_line1',
  'address_line2',
  'postal_code',
  'city',
  'country',
] as const;

export type IdentityField = (typeof IDENTITY_FIELDS)[number];
export type OrganizationIdentity = Record<IdentityField, string>;

/** One input of the identity form: Organization Settings › General and Platform › New organization. */
export type IdentityFieldSpec = {
  field: IdentityField;
  label: string;
  placeholder?: string;
  hint?: string;
  type?: 'text' | 'url' | 'email';
  autoComplete?: string;
};

export const ORGANIZATION_FIELDS: IdentityFieldSpec[] = [
  { field: 'name', label: 'Name', placeholder: 'Acme', hint: 'How the organization is shown in Nexus' },
  { field: 'legal_name', label: 'Legal name', placeholder: 'Acme Holding SAS', autoComplete: 'organization' },
  { field: 'registration_number', label: 'Registration number', placeholder: 'SIREN, company number…' },
  { field: 'vat_number', label: 'VAT number', placeholder: 'FR12345678901' },
];

export const CONTACT_FIELDS: IdentityFieldSpec[] = [
  { field: 'website', label: 'Website', placeholder: 'https://acme.com', type: 'url', autoComplete: 'url' },
  { field: 'contact_email', label: 'Contact email', placeholder: 'contact@acme.com', type: 'email', autoComplete: 'email' },
];

export const ADDRESS_FIELDS: IdentityFieldSpec[] = [
  { field: 'address_line1', label: 'Address', placeholder: 'Street and number', autoComplete: 'address-line1' },
  { field: 'address_line2', label: 'Address, line 2', placeholder: 'Building, floor…', autoComplete: 'address-line2' },
  { field: 'postal_code', label: 'Postal code', autoComplete: 'postal-code' },
  { field: 'city', label: 'City', autoComplete: 'address-level2' },
  { field: 'country', label: 'Country', autoComplete: 'country-name' },
];

/** The form's values from `GET /api/organizations/<id>`: a missing field is blank. */
export function identityFrom(data: Partial<Record<IdentityField, unknown>>): OrganizationIdentity {
  const identity = {} as OrganizationIdentity;
  for (const field of IDENTITY_FIELDS) {
    const value = data[field];
    identity[field] = typeof value === 'string' ? value : '';
  }
  return identity;
}

/**
 * What changed, as the PATCH body: trimmed, a cleared field sent as null (the API
 * clears it). The name cannot be cleared, so a blank name is left out.
 */
export function identityChanges(
  initial: OrganizationIdentity,
  current: OrganizationIdentity
): Partial<Record<IdentityField, string | null>> {
  const changes: Partial<Record<IdentityField, string | null>> = {};
  for (const field of IDENTITY_FIELDS) {
    const before = initial[field].trim();
    const after = current[field].trim();
    if (before === after) continue;
    if (field === 'name' && !after) continue;
    changes[field] = after || null;
  }
  return changes;
}

/** A website as typed ("acme.com") made a URL the API accepts ("https://acme.com"). */
export function normalizeWebsite(value: string): string {
  const trimmed = value.trim();
  if (!trimmed || /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

/** The API's refusal of a save, in words for the page. */
export function identitySaveError(status: number, detail: unknown): string {
  if (status === 403) return "Only the organization's administrators can change its details.";
  if (status === 422 && Array.isArray(detail)) {
    const fields = detail
      .map((issue) => (Array.isArray(issue?.loc) ? issue.loc[issue.loc.length - 1] : null))
      .filter((field): field is string => typeof field === 'string');
    if (fields.includes('website')) return 'The website is an http(s) address, such as https://example.com.';
    if (fields.includes('contact_email')) return 'The contact email is not an email address.';
    if (fields.includes('timezone')) return 'The timezone is not one the server knows.';
    if (fields.length) return `Check ${fields.join(', ').replace(/_/g, ' ')}.`;
  }
  if (typeof detail === 'string' && detail) return detail;
  return 'The changes could not be saved.';
}

/**
 * A new organization's identity, as the create body takes it: trimmed, blanks left
 * out, the website made a URL. The name is the caller's (`POST` needs it apart).
 */
export function identityCreateFields(
  values: OrganizationIdentity
): Partial<Record<Exclude<IdentityField, 'name'>, string>> {
  const body: Partial<Record<Exclude<IdentityField, 'name'>, string>> = {};
  for (const field of IDENTITY_FIELDS) {
    if (field === 'name') continue;
    const value = field === 'website' ? normalizeWebsite(values[field]) : values[field].trim();
    if (value) body[field] = value;
  }
  return body;
}
