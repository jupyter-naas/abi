import { describe, expect, it } from 'vitest';
import {
  appHtmlPathPrefix,
  appIframeSandbox,
  isBundledAppHtmlUrl,
  REMOTE_APP_SANDBOX,
  remoteAppGrantUrl,
  remoteAppParts,
  pagesSsoAudience,
  withAppHtmlAccessToken,
  withPagesSsoToken,
  withRemoteAppWorkspace,
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

  it('finds the module and app of a remote module app URL', () => {
    expect(remoteAppParts('/app-html/remote/acme.research/console/index.html?x=1')).toEqual({
      moduleId: 'acme.research',
      app: 'console',
      rest: 'index.html?x=1',
    });
    expect(remoteAppParts('https://nexus.localhost/app-html/remote/acme/console')).toEqual({
      moduleId: 'acme',
      app: 'console',
      rest: '',
    });
    expect(remoteAppParts('/app-html/remote/acme/console?x=1')).toEqual({
      moduleId: 'acme',
      app: 'console',
      rest: '?x=1',
    });
    expect(remoteAppParts('/app-html/remote/acme/console#top')).toEqual({
      moduleId: 'acme',
      app: 'console',
      rest: '#top',
    });
    expect(remoteAppParts('/app-html/report/counter_uas/dashboard/')).toBe(null);
    expect(remoteAppParts('https://portal.example.com/app')).toBe(null);
  });

  it('builds the grant URL on the API origin', () => {
    expect(
      remoteAppGrantUrl('https://api.example.com/', '/app-remote/g/acme/console/', 'index.html'),
    ).toBe('https://api.example.com/app-remote/g/acme/console/index.html');
    expect(remoteAppGrantUrl('https://api.example.com', '/app-remote/g/acme/console/', '?x=1')).toBe(
      'https://api.example.com/app-remote/g/acme/console/?x=1',
    );
  });

  it('never frames a remote module app with allow-same-origin', () => {
    const remote = appIframeSandbox('/app-html/remote/acme/console/index.html');
    expect(remote).toBe(REMOTE_APP_SANDBOX);
    expect(remote).not.toContain('allow-same-origin');
    expect(appIframeSandbox('/app-html/report/counter_uas/dashboard/')).toContain(
      'allow-same-origin',
    );
  });
});

describe('remote app links name their workspace', () => {
  it('adds the workspace to a remote app catalog URL only', () => {
    expect(withRemoteAppWorkspace('/app-html/remote/acme.research/console/index.html', 'ws 1')).toBe(
      '/app-html/remote/acme.research/console/index.html?workspace_id=ws%201',
    );
    expect(withRemoteAppWorkspace('/app-html/remote/acme.research/console/?q=1#top', 'ws-1')).toBe(
      '/app-html/remote/acme.research/console/?q=1&workspace_id=ws-1#top',
    );
    expect(withRemoteAppWorkspace('/app-html/report/counter_uas/index.html', 'ws-1')).toBe(
      '/app-html/report/counter_uas/index.html',
    );
    expect(withRemoteAppWorkspace('/app-html/remote/acme.research/console/', '')).toBe(
      '/app-html/remote/acme.research/console/',
    );
  });
});
