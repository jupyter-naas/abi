/**
 * The brand colors a page last showed (a workspace's, an organization's), kept in the browser so
 * a hard refresh paints them at once: without them the page shows the platform's colors until the
 * JavaScript has loaded and the workspace or organization has been read (1 to 2 s), then switches.
 *
 * `BRAND_COLOR_BOOT`, an inline script of the root layout, puts the page's kept colors in a
 * `<style id="nexus-brand-boot">` before it paints. Where the app applies the colors (the
 * workspace shell, the settings shell) it calls `rememberBrandColors`, whose inline variables win
 * over that sheet, and the sheet is dropped: what the app decides is what stays. A page is named
 * by the workspace or organization of its path (and whether it is a Settings page, which sets more
 * variables), so another workspace never borrows them. Colors only (no secret); nothing is kept
 * during a view ("View as"), whose storage is memory (`view-storage-guard.ts`).
 */

import { VIEW_FLAG_COOKIE } from './view-flag';

export const BRAND_COLORS_KEY = 'nexus-brand-colors';
export const BRAND_BOOT_STYLE_ID = 'nexus-brand-boot';
// It runs before the view guard (view-storage-guard.ts): during a view it reads nothing.
const VIEW_AS_COOKIE = VIEW_FLAG_COOKIE;
const MAX_SCOPES = 50;
// What may be put back: CSS variables holding a color (hex, HSL triplet, color-mix of them),
// never a URL or another function that loads or runs something.
const VARIABLE = /^--[a-z0-9-]{1,40}$/;
const VALUE = /^(?!.*(?:url|image|expression|var)\s*\()[#a-z0-9%.,()\s-]{1,80}$/i;

/** The key of a path's colors: `workspace:<id or slug>` or `organization:<id>`, `/settings` added
 *  on a Settings page; null for a page of neither. */
export function brandScopeOf(pathname: string): string | null {
  const [, first, second, third] = pathname.split('/');
  if (!second) return null;
  const settings = third === 'settings' ? '/settings' : '';
  if (first === 'workspace') return `workspace:${second}${settings}`;
  if (first === 'organizations') return `organization:${second}${settings}`;
  return null;
}

type Kept = Record<string, Record<string, string>>;

function read(): Kept {
  try {
    const raw = JSON.parse(window.localStorage.getItem(BRAND_COLORS_KEY) ?? '{}');
    return raw && typeof raw === 'object' ? (raw as Kept) : {};
  } catch {
    return {};
  }
}

/**
 * The colors the page at `pathname` applies, kept for its next hard refresh (added to what another
 * shell of the same page applies); none (the platform's) forgets the page. Drops the boot sheet:
 * the app's own colors are on the document now.
 */
export function rememberBrandColors(pathname: string, variables: Record<string, string>): void {
  if (typeof window === 'undefined') return;
  document.getElementById(BRAND_BOOT_STYLE_ID)?.remove();
  const scope = brandScopeOf(pathname);
  if (!scope) return;
  try {
    const kept = read();
    const safe = Object.fromEntries(
      Object.entries(variables).filter(([name, value]) => VARIABLE.test(name) && VALUE.test(value))
    );
    const previous = kept[scope];
    delete kept[scope];
    if (Object.keys(safe).length > 0) kept[scope] = { ...(previous ?? {}), ...safe };
    const scopes = Object.keys(kept);
    for (const old of scopes.slice(0, Math.max(0, scopes.length - MAX_SCOPES))) delete kept[old];
    window.localStorage.setItem(BRAND_COLORS_KEY, JSON.stringify(kept));
  } catch {
    // Storage full or refused: the page only flashes the platform's colors, as before.
  }
}

/** Inline in the root layout: this page's kept colors, in a sheet, before it paints. */
export const BRAND_COLOR_BOOT = `(function(){try{
if(document.cookie.split(';').some(function(c){return c.trim().split('=')[0]===${JSON.stringify(VIEW_AS_COOKIE)};}))return;
var p=location.pathname.split('/'),s=null,t=p[3]==='settings'?'/settings':'';
if(p[2]){if(p[1]==='workspace')s='workspace:'+p[2]+t;else if(p[1]==='organizations')s='organization:'+p[2]+t;}
if(!s)return;
var all=JSON.parse(localStorage.getItem(${JSON.stringify(BRAND_COLORS_KEY)})||'{}'),v=all&&all[s];
if(!v||typeof v!=='object')return;
var n=${VARIABLE.toString()},c=${VALUE.toString()},css='';
for(var k in v){if(Object.prototype.hasOwnProperty.call(v,k)&&n.test(k)&&typeof v[k]==='string'&&c.test(v[k]))css+=k+':'+v[k]+';';}
if(!css)return;
var el=document.createElement('style');el.id=${JSON.stringify(BRAND_BOOT_STYLE_ID)};el.textContent=':root{'+css+'}';
document.head.appendChild(el);
}catch(e){}})();`;
