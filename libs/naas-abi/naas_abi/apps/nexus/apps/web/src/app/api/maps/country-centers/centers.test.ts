import { describe, expect, it } from 'vitest';
import { compactCountryCenters } from './centers';

const feature = (properties: Record<string, unknown>) => ({ type: 'Feature', properties, geometry: null });

describe('compactCountryCenters', () => {
  it('keeps names (own first, no sovereign), label point and continent', () => {
    const rows = compactCountryCenters({
      features: [
        feature({ NAME: 'Fr. S. Antarctic Lands', SOVEREIGNT: 'France', ADMIN: 'French Southern and Antarctic Lands', LABEL_X: 69, LABEL_Y: -49, CONTINENT: 'Seven seas (open ocean)' }),
        feature({ NAME: 'France', ADMIN: 'France', NAME_DE: 'Frankreich', ISO_A2: '-99', ISO_A3: 'FRA', LABEL_X: 2.55, LABEL_Y: 46.7, CONTINENT: 'Europe' }),
        feature({ NAME: 'Broken', LABEL_X: 'x' }),
      ],
    });
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ name: 'Fr. S. Antarctic Lands', continent: null });
    expect(rows[0]!.names).not.toContain('France');
    expect(rows[1]).toEqual({
      name: 'France',
      names: ['France', 'Frankreich', 'FRA'],
      lat: 46.7,
      lng: 2.55,
      continent: 'Europe',
    });
  });
});
