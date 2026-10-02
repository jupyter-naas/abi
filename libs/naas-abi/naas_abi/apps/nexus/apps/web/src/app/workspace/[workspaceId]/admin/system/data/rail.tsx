'use client';

/** Every kernel service, grouped, with what is unavailable and why. */
import { History, Keyboard } from 'lucide-react';
import type { ResourceServiceInfo } from './data-types';
import { Hint } from './data-ui';
import { viewFor } from './services/registry';
import { SERVICE_GROUPS } from './services/types';

export function ServiceRail({
  services,
  active,
  onSelect,
  onRecent,
  onShortcuts,
}: {
  services: ResourceServiceInfo[];
  active: string | null;
  onSelect: (name: string) => void;
  onRecent: () => void;
  onShortcuts: () => void;
}) {
  const grouped = SERVICE_GROUPS.map((group) => ({
    group,
    items: services
      .map((s) => ({ info: s, view: viewFor(s.name) }))
      .filter((s) => s.view.group === group)
      .sort((a, b) => a.view.label.localeCompare(b.view.label)),
  })).filter((g) => g.items.length);

  return (
    <nav className="data-rail" aria-label="Services">
      <div className="data-rail-scroll">
        {grouped.map(({ group, items }) => (
          <div key={group} className="data-rail-group">
            <p className="data-rail-group-label">{group}</p>
            {items.map(({ info, view }) => {
              const Icon = view.icon;
              const button = (
                <button
                  key={info.name}
                  type="button"
                  data-data-service={info.name}
                  className={`data-rail-item${info.name === active ? ' data-rail-item-active' : ''}${
                    info.available ? '' : ' data-rail-item-off'
                  }`}
                  aria-current={info.name === active ? 'page' : undefined}
                  aria-disabled={!info.available}
                  onClick={() => info.available && onSelect(info.name)}
                >
                  <Icon size={15} strokeWidth={1.75} aria-hidden="true" />
                  <span className="data-rail-label">{view.label}</span>
                  {!info.available && <span className="data-rail-off">off</span>}
                </button>
              );
              return info.available ? (
                button
              ) : (
                <Hint key={info.name} label={info.reason || 'Unavailable'} side="right">
                  {button}
                </Hint>
              );
            })}
          </div>
        ))}
      </div>
      <div className="data-rail-footer">
        <button type="button" className="data-rail-footer-button" onClick={onRecent}>
          <History size={14} aria-hidden="true" />
          <span className="data-rail-label">Recent changes</span>
        </button>
        <Hint label="Keyboard shortcuts" shortcut="?">
          <button type="button" className="data-icon-button" aria-label="Keyboard shortcuts" onClick={onShortcuts}>
            <Keyboard size={14} aria-hidden="true" />
          </button>
        </Hint>
      </div>
    </nav>
  );
}
