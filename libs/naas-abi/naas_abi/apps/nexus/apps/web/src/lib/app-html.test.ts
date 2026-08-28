import { describe, expect, it } from 'vitest';
import {
  appHtmlPathPrefix,
  isBundledAppHtmlUrl,
  pagesSsoAudience,
  withAppHtmlAccessToken,
  withPagesSsoToken,
} from './app-html';

describe('app-html helpers', () => {
  it('detects bundled app-html URLs', () => {
    expect(isBundledAppHtmlUrl('/app-html/report/counter_uas/dashboard/')).toBe(true);
    expect(isBundledAppHtmlUrl('https://nexus.localhost/app-html/axi/devops/')).toBe(
      true,
    );
    expect(isBundledAppHtmlUrl('/workspace/primary/apps')).toBe(false);
  });

  it('derives path_prefix locks for scoped JWTs', () => {
    expect(appHtmlPathPrefix('/app-html/report/counter_uas/dashboard/')).toBe(
      '/app-html/report/counter_uas/',
    );
    expect(
      appHtmlPathPrefix(
        'https://nexus.localhost/app-html/report/counter_uas/map/?report_date=2026-07-26',
      ),
    ).toBe('/app-html/report/counter_uas/');
  });

  it('appends token without dropping existing query params', () => {
    expect(
      withAppHtmlAccessToken(
        '/app-html/report/counter_uas/map/?report_date=2026-07-26',
        'abc.def',
      ),
    ).toBe(
      '/app-html/report/counter_uas/map/?report_date=2026-07-26&token=abc.def',
    );
    expect(
      withAppHtmlAccessToken('/app-html/report/counter_uas/dashboard/', 'tok'),
    ).toBe('/app-html/report/counter_uas/dashboard/?token=tok');
  });

  it('derives Pages SSO audience from an absolute portal URL', () => {
    expect(pagesSsoAudience('https://portal.example.com/login')).toBe(
      'portal.example.com',
    );
    expect(pagesSsoAudience('/app-html/example/web/')).toBe(null);
  });

  it('appends sso without dropping existing query params', () => {
    expect(
      withPagesSsoToken('https://portal.example.com/login', 'abc.def'),
    ).toBe('https://portal.example.com/login?sso=abc.def');
    expect(
      withPagesSsoToken(
        'https://portal.example.com/login?next=/',
        'tok',
      ),
    ).toBe('https://portal.example.com/login?next=/&sso=tok');
  });
});
