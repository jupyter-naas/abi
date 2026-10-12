import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { Map } from 'lucide-react';

import { mapsIconMap } from './maps-icons';

/** Leaflet divIcon size; keep in sync with `.maps-layer-marker` in CSS. */
export const MAPS_LAYER_MARKER_PX = 16;

const MARKER_ICON_PX = 11;

/** Organization logo pin (replaces Lucide badge when markerLogoUrl is set). */
export function mapsLayerLogoPinHtml(logoUrl: string, _color: string): string {
  const safe = logoUrl.replace(/"/g, '&quot;');
  return renderToStaticMarkup(
    createElement(
      'span',
      { className: 'maps-layer-marker maps-layer-marker--logo' },
      createElement('img', {
        src: safe,
        alt: '',
        className: 'maps-layer-marker__logo',
        'aria-hidden': true,
      }),
    ),
  );
}

/** HTML for a map pin that matches the All layers legend swatch. */
export function mapsLayerPinHtml(markerIcon: string, color: string): string {
  const Icon = mapsIconMap[markerIcon] ?? Map;
  return renderToStaticMarkup(
    createElement(
      'span',
      { className: 'maps-layer-marker', style: { backgroundColor: color } },
      createElement(Icon, {
        size: MARKER_ICON_PX,
        strokeWidth: 2.25,
        color: '#ffffff',
        'aria-hidden': true,
      }),
    ),
  );
}
