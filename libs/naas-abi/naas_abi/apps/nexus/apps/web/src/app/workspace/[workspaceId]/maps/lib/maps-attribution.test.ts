// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';

import { attributionHtml } from './maps-attribution';
import { createBasemapTileLayer } from './maps-basemaps';

const OSM = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

afterEach(() => {
  document.body.innerHTML = '';
});

async function attributionControl(attribution: string): Promise<HTMLElement> {
  const L = await import('leaflet');
  const container = document.createElement('div');
  document.body.appendChild(container);
  const map = L.map(container).setView([20, 0], 2);
  createBasemapTileLayer(L, { kind: 'tile', url: 'https://tile.example/{z}/{x}/{y}.png', attribution }).addTo(map);
  return container.querySelector('.leaflet-control-attribution') as HTMLElement;
}

describe('basemap attributions', () => {
  it('keeps a stored attribution to text and https links in the map', async () => {
    const control = await attributionControl(
      '© OSM <img src=x onerror="alert(1)"> <a href="javascript:alert(1)">x</a> <svg onload=alert(1)>',
    );
    expect(control.querySelector('img, svg[onload], script, iframe')).toBeNull();
    expect([...control.querySelectorAll('a')].map((a) => a.getAttribute('href'))).not.toContain('javascript:alert(1)');
    expect(control.textContent).toContain('<img src=x onerror="alert(1)">');
  });

  it('keeps the links of the built-in attributions', async () => {
    const control = await attributionControl(OSM);
    const link = [...control.querySelectorAll('a')].find((a) => a.textContent === 'OpenStreetMap');
    expect(link?.getAttribute('href')).toBe('https://www.openstreetmap.org/copyright');
    expect(link?.getAttribute('rel')).toBe('noopener noreferrer');
    expect(control.textContent).toContain('© OpenStreetMap contributors');
  });

  it('keeps every other link form escaped', () => {
    expect(attributionHtml(undefined)).toBe('');
    expect(attributionHtml('<a href="https://x.example" onclick="y">x</a>')).toBe(
      '&lt;a href="https://x.example" onclick="y"&gt;x&lt;/a&gt;',
    );
    expect(attributionHtml('<a href="https://x.example"><img src=x></a>')).not.toContain('<img');
  });
});
