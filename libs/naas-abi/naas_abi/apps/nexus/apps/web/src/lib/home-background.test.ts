import { describe, expect, it } from 'vitest';

import {
  DEFAULT_FRAMING,
  MAX_BACKGROUND_ZOOM,
  MIN_BACKGROUND_ZOOM,
  isApiBackgroundUrl,
  panFraming,
  parseBackgroundImageUrl,
  wheelZoomStep,
} from './home-background';

describe('isApiBackgroundUrl', () => {
  it('matches the API wallpaper, relative or absolute', () => {
    expect(isApiBackgroundUrl('/api/workspaces/ws-1/background-image?v=abc.png')).toBe(true);
    expect(isApiBackgroundUrl('http://localhost:9879/api/workspaces/ws-1/background-image?v=abc.png')).toBe(true);
  });

  it('leaves external and upload URLs to CSS', () => {
    expect(isApiBackgroundUrl('https://example.com/hero.jpg')).toBe(false);
    expect(isApiBackgroundUrl('/uploads/logos/x.png')).toBe(false);
    expect(isApiBackgroundUrl('/api/workspaces/ws-1/background-image/draft/abc.png')).toBe(false);
    expect(isApiBackgroundUrl(undefined)).toBe(false);
  });
});

describe('parseBackgroundImageUrl', () => {
  it('splits the API URL into image and framing', () => {
    expect(parseBackgroundImageUrl('http://api/api/workspaces/ws-1/background-image?v=a.png&x=30&y=70&z=2')).toEqual({
      imageUrl: 'http://api/api/workspaces/ws-1/background-image?v=a.png',
      framing: { x: 30, y: 70, zoom: 2 },
      fileName: 'a.png',
    });
  });

  it('defaults and clamps framing', () => {
    expect(parseBackgroundImageUrl('/api/workspaces/ws-1/background-image?v=a.png').framing).toEqual(DEFAULT_FRAMING);
    expect(parseBackgroundImageUrl('/api/workspaces/ws-1/background-image?v=a.png&x=-5&y=500&z=99').framing).toEqual({
      x: 0,
      y: 100,
      zoom: MAX_BACKGROUND_ZOOM,
    });
  });

  it('zooms out down to 50%, no further', () => {
    expect(MIN_BACKGROUND_ZOOM).toBe(0.5);
    expect(parseBackgroundImageUrl('/api/workspaces/ws-1/background-image?v=a.png&z=0.5').framing.zoom).toBe(0.5);
    expect(parseBackgroundImageUrl('/api/workspaces/ws-1/background-image?v=a.png&z=0.2').framing.zoom).toBe(0.5);
  });

  it('leaves external URLs untouched', () => {
    expect(parseBackgroundImageUrl('https://example.com/a.jpg?x=1')).toEqual({
      imageUrl: 'https://example.com/a.jpg?x=1',
      framing: DEFAULT_FRAMING,
    });
  });
});

describe('panFraming', () => {
  const box = { width: 400, height: 200 };

  it('does nothing when the image exactly fits and is not zoomed', () => {
    expect(panFraming(DEFAULT_FRAMING, 50, 50, box, 2)).toEqual(DEFAULT_FRAMING);
  });

  it('moves the focal point against the drag on a wide image', () => {
    // 4:1 image in a 2:1 frame: covers at 800px wide, 400px overflow → 4px per %.
    const next = panFraming(DEFAULT_FRAMING, 40, 0, box, 4);
    expect(next.x).toBeCloseTo(40);
    expect(next.y).toBe(50);
  });

  it('lets a zoomed image pan in both directions', () => {
    // Fits at zoom 1; at zoom 2 each % moves the image frame·(z−1)/100 px.
    const next = panFraming({ x: 50, y: 50, zoom: 2 }, -40, 20, box, 2);
    expect(next.x).toBeCloseTo(60);
    expect(next.y).toBeCloseTo(40);
  });

  it('clamps to the image edges', () => {
    expect(panFraming({ x: 50, y: 50, zoom: 2 }, 10_000, -10_000, box, 2)).toEqual({ x: 0, y: 100, zoom: 2 });
  });

  it('lets an image zoomed out, smaller than the frame, follow the drag', () => {
    // Fits at zoom 1; at zoom 0.5 each % moves the image frame·(1−z)/100 px the other way:
    // the image goes with the pointer, from flush left (x 0) to flush right (x 100).
    const next = panFraming({ x: 50, y: 50, zoom: 0.5 }, 40, -20, box, 2);
    expect(next.x).toBeCloseTo(70);
    expect(next.y).toBeCloseTo(30);
    expect(panFraming({ x: 50, y: 50, zoom: 0.5 }, 10_000, -10_000, box, 2)).toEqual({ x: 100, y: 0, zoom: 0.5 });
  });
});

describe('wheelZoomStep', () => {
  it('zooms only with Ctrl held: in when scrolling up, out when scrolling down', () => {
    expect(wheelZoomStep({ ctrlKey: true, deltaY: -100 }, 0.25)).toBe(0.25);
    expect(wheelZoomStep({ ctrlKey: true, deltaY: 100 }, 0.25)).toBe(-0.25);
  });

  it('leaves a plain scroll to the page', () => {
    expect(wheelZoomStep({ ctrlKey: false, deltaY: -100 }, 0.25)).toBeNull();
    expect(wheelZoomStep({ ctrlKey: true, deltaY: 0 }, 0.25)).toBeNull();
  });
});
