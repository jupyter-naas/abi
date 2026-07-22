import {
  buildReferentialsIndex,
  validateReferentialEntry,
  type ReferentialsIndex,
} from '@/lib/pnl/referentials';

describe('validateReferentialEntry', () => {
  const index: ReferentialsIndex = buildReferentialsIndex({
    customers: [
      {
        organization_slug: 'flex_office',
        company_name: 'FLEX OFFICE',
        customer_name: 'ACME CLIENT',
        customer_vat_number: '',
        customer_billing_address_city: '',
        customer_emails: '',
      },
    ],
    suppliers: [
      {
        organization_slug: 'flex_office',
        company_name: 'FLEX OFFICE',
        supplier_name: 'ACME SUPPLIER',
        supplier_vat_number: '',
        supplier_postal_address_city: '',
      },
    ],
    categories: [
      {
        organization_slug: 'flex_office',
        company_name: 'FLEX OFFICE',
        category_group_label: '2.Ventes',
        category_label: 'CA Clients',
      },
    ],
  });

  it('accepts known thirdparty and category tuple', () => {
    const result = validateReferentialEntry(index, {
      thirdparty: 'acme client',
      famille_2: '2.Ventes',
      categorie_2: 'CA Clients',
    });
    expect(result.valid).toBe(true);
    expect(result.normalized.thirdparty).toBe('ACME CLIENT');
  });

  it('rejects unknown thirdparty', () => {
    const result = validateReferentialEntry(index, {
      thirdparty: 'UNKNOWN',
      famille_2: '2.Ventes',
      categorie_2: 'CA Clients',
    });
    expect(result.valid).toBe(false);
  });
});
