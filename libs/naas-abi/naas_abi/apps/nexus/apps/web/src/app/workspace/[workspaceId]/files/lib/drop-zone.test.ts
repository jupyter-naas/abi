// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { carriesExternalFiles, leavesDropZone } from './drop-zone';

describe('leavesDropZone', () => {
  // The overlay covering the zone fired dragleave on the row below it: the zone
  // hid the overlay, dragover showed it again (a strobe), and a drop on the
  // vanishing overlay reached no handler, so the browser opened the file.
  it('is false while the drag moves between the zone own children', () => {
    const zone = document.createElement('div');
    const row = document.createElement('div');
    const overlay = document.createElement('div');
    zone.append(row, overlay);
    expect(leavesDropZone(zone, overlay)).toBe(false);
    expect(leavesDropZone(zone, row)).toBe(false);
    expect(leavesDropZone(zone, zone)).toBe(false);
  });

  it('is true when the drag goes outside the zone or out of the window', () => {
    const zone = document.createElement('div');
    const outside = document.createElement('div');
    expect(leavesDropZone(zone, outside)).toBe(true);
    expect(leavesDropZone(zone, null)).toBe(true);
  });
});

describe('carriesExternalFiles', () => {
  it('is true for files dragged from the computer, not for a row moved in the page', () => {
    expect(carriesExternalFiles(['Files'])).toBe(true);
    expect(carriesExternalFiles(['application/x-nexus-file'])).toBe(false);
    expect(carriesExternalFiles(['text/plain'])).toBe(false);
    expect(carriesExternalFiles([])).toBe(false);
  });
});
