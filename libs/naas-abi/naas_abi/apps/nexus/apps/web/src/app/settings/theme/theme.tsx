'use client';

import { useState, type ReactNode } from 'react';
import { FileText, Folder, Inbox, MoreHorizontal, Plus, RefreshCw, Trash2, Users } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, type DialogSize } from '@/components/ui/dialog';
import { useConfirm, usePrompt } from '@/components/ui/dialogs';
import { EmptyState } from '@/components/ui/empty-state';
import { Field } from '@/components/ui/field';
import { Input, Select, Textarea } from '@/components/ui/input';
import { KpiCard } from '@/components/ui/kpi-card';
import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';
import { Notice } from '@/components/ui/notice';
import { PageHeader } from '@/components/ui/page-header';
import { SearchBox } from '@/components/ui/search-box';
import { Loading, Spinner } from '@/components/ui/spinner';
import { ColumnResizeHandle, useColumnResize } from '@/components/ui/split-pane';
import { Tabs } from '@/components/ui/tabs';
import { toast } from '@/components/ui/toast';
import { Toolbar, ToolbarGroup, ToolbarSeparator } from '@/components/ui/toolbar';
import { TreeRow, TreeTwisty, treeRowClass } from '@/components/ui/tree-row';
import { settingsTable, SettingsPageHeader } from '@/components/settings/settings-ui';
import { themeSections, type KitEntry } from './theme-model';

/** One section of the page: what the entries are for, where they live, then the specimens. */
function Specimen({ id, entries, children }: { id: string; entries: KitEntry[]; children: ReactNode }) {
  return (
    <Card
      title={<span id={id}>{entries.map((e) => e.label).join(' · ')}</span>}
      description={entries.map((e) => e.use).join(' ')}
      actions={
        <span className="hidden gap-1 sm:flex">
          {entries.map((e) => (
            <Badge key={e.module} variant="outline" mono>
              ui/{e.module}
            </Badge>
          ))}
        </span>
      }
      bodyClassName="space-y-4"
    >
      {children}
    </Card>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="w-24 shrink-0 text-xs text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}

const MENU_ITEMS: MenuEntry[] = [
  { id: 'new', label: 'New file', shortcut: '⌘N' },
  { id: 'open', label: 'Open…', shortcut: '⌘O' },
  { id: 'sep', kind: 'separator' },
  { id: 'heading', kind: 'heading', label: 'View' },
  { id: 'grid', label: 'Grid', checked: true },
  { id: 'list', label: 'List', checked: false },
  { id: 'more', kind: 'submenu', label: 'Export', items: [{ id: 'csv', label: 'CSV' }, { id: 'xlsx', label: 'Excel' }] },
  { id: 'sep2', kind: 'separator' },
  { id: 'archive', label: 'Archive', destructive: true },
  { id: 'disabled', label: 'Not available', disabled: true },
];

function SplitDemo() {
  const [width, setWidth] = useState(160);
  const { isDragging, handleDragStart } = useColumnResize(width, (next) => setWidth(Math.min(320, Math.max(96, next))));
  return (
    <div className="flex h-28 border border-border">
      <div style={{ width }} className="shrink-0 bg-muted/40 p-3 text-xs text-muted-foreground">
        Left pane · {Math.round(width)}px
      </div>
      <ColumnResizeHandle onMouseDown={handleDragStart} label="Drag to resize" isActive={isDragging} />
      <div className="flex-1 p-3 text-xs text-muted-foreground">Right pane</div>
    </div>
  );
}

/**
 * Platform Settings › Theme: every kit component in its states, with this platform's tokens
 * and branding. A component that is not here does not exist yet: add it to `components/ui`,
 * to `theme-model.ts`, then here.
 */
export default function ThemePage() {
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState<'all' | 'mine' | 'shared'>('all');
  const [segment, setSegment] = useState<'grid' | 'list'>('grid');
  const [dialog, setDialog] = useState<DialogSize | null>(null);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const { confirm, dialog: confirmDialog } = useConfirm();
  const { prompt, dialog: promptDialog } = usePrompt();
  const sections = Object.fromEntries(themeSections().map((s) => [s.id, s.entries]));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Theme"
        badge={`${themeSections().length} sections`}
        description="The design kit every Nexus page is built from (components/ui). Use these; do not restyle them in a feature."
      />

      <nav aria-label="Theme sections" className="flex flex-wrap gap-2 text-xs">
        {themeSections().map((s) => (
          <a key={s.id} href={`#${s.id}`} className="border border-border px-2 py-1 text-muted-foreground hover:bg-muted hover:text-foreground">
            {s.entries[0].label}
          </a>
        ))}
      </nav>

      <Specimen id="buttons" entries={sections.buttons}>
        <Row label="md (header)">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Delete</Button>
          <Button variant="destructive-ghost">Remove</Button>
          <Button variant="link">Link</Button>
        </Row>
        <Row label="sm (inline)">
          <Button size="sm"><Plus size={14} /> Add</Button>
          <Button size="sm" variant="secondary">Cancel</Button>
          <Button size="sm" disabled>Disabled</Button>
          <Button size="sm" disabled><Spinner size={14} /> Saving…</Button>
        </Row>
        <Row label="icon">
          <Button size="icon" variant="ghost" aria-label="Refresh"><RefreshCw size={14} /></Button>
          <Button size="icon" variant="secondary" aria-label="More"><MoreHorizontal size={14} /></Button>
          <Button size="icon" variant="destructive-ghost" aria-label="Delete"><Trash2 size={14} /></Button>
        </Row>
      </Specimen>

      <Specimen id="badges" entries={sections.badges}>
        <Row label="variants">
          <Badge>Neutral</Badge>
          <Badge variant="primary">Primary</Badge>
          <Badge variant="success">Running</Badge>
          <Badge variant="info">Queued</Badge>
          <Badge variant="warning">Degraded</Badge>
          <Badge variant="destructive">Failed</Badge>
          <Badge variant="outline">Outline</Badge>
          <Badge mono>usr_8f2c</Badge>
        </Row>
      </Specimen>

      <Specimen id="fields" entries={sections.fields}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" hint="Shown to every member." htmlFor="theme-name">
            <Input id="theme-name" placeholder="Acme" />
          </Field>
          <Field label="Email" error="Enter an email address." htmlFor="theme-email">
            <Input id="theme-email" defaultValue="acme" aria-invalid className="border-destructive" />
          </Field>
          <Field label="Role" htmlFor="theme-role">
            <Select id="theme-role" defaultValue="member">
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </Select>
          </Field>
          <Field label="Disabled" htmlFor="theme-disabled">
            <Input id="theme-disabled" disabled defaultValue="Read-only" />
          </Field>
          <Field label="Description" htmlFor="theme-description" className="sm:col-span-2">
            <Textarea id="theme-description" rows={3} placeholder="What this workspace is for" />
          </Field>
          <Checkbox label="Send a weekly digest" defaultChecked />
        </div>
      </Specimen>

      <Specimen id="search" entries={sections.search}>
        <Row label="md">
          <SearchBox value={search} onChange={setSearch} placeholder="Search people…" className="w-72" />
        </Row>
        <Row label="sm">
          <SearchBox value={search} onChange={setSearch} placeholder="Filter" size="sm" className="w-56" />
        </Row>
      </Specimen>

      <Specimen id="notices" entries={sections.notices}>
        <Notice tone="success">Changes saved.</Notice>
        <Notice tone="error">The workspace could not be loaded. Try again in a moment.</Notice>
        <Notice tone="warning">This key expires in 3 days.</Notice>
        <Notice tone="info">Members see this page read-only.</Notice>
      </Specimen>

      <Specimen id="empty" entries={sections.empty}>
        <div className="grid gap-4 sm:grid-cols-2">
          <EmptyState
            framed
            icon={<Inbox size={22} />}
            title="No API keys yet"
            description="Create a key to call the API from a script."
            action={<Button size="sm"><Plus size={14} /> Create key</Button>}
          />
          <EmptyState icon={<Users size={22} />} title="No member matches “zed”" description="Clear the search to see everyone." />
        </div>
      </Specimen>

      <Specimen id="loading" entries={sections.loading}>
        <Row label="inline"><Spinner /> <Spinner size={12} /></Row>
        <Loading label="Loading members…" className="border border-dashed border-border py-6" />
      </Specimen>

      <Specimen id="cards" entries={sections.cards}>
        <div className="grid gap-4 sm:grid-cols-3">
          <KpiCard label="Members" value={42} hint="in 3 workspaces" icon={Users} trend={{ value: 12, label: 'vs last week' }} />
          <KpiCard label="Failed runs" value={3} trend={{ value: -40 }} />
          <Card title="Card" description="Padded body" actions={<Button size="sm" variant="secondary">Edit</Button>}>
            <p className="text-sm text-muted-foreground">Body text.</p>
          </Card>
        </div>
      </Specimen>

      <Specimen id="page-header" entries={sections['page-header']}>
        <PageHeader title="Members" badge="42" description="People who can open this workspace." actions={<Button><Plus size={14} /> Invite</Button>} />
        <SettingsPageHeader title="In settings" description="SettingsPageHeader adds Reload left of the actions." actions={<Button>Save</Button>} />
      </Specimen>

      <Specimen id="toolbar" entries={sections.toolbar}>
        <div className="border border-border">
          <Toolbar
            label="Demo toolbar"
            end={
              <>
                <Button size="icon" variant="ghost" aria-label="Refresh"><RefreshCw size={14} /></Button>
                <Button size="sm"><Plus size={14} /> New</Button>
              </>
            }
          >
            <ToolbarGroup>
              <SearchBox value={search} onChange={setSearch} size="sm" placeholder="Search files" className="w-48" />
            </ToolbarGroup>
            <ToolbarSeparator />
            <Tabs
              label="Layout"
              variant="segmented"
              value={segment}
              onChange={setSegment}
              items={[{ id: 'grid', label: 'Grid' }, { id: 'list', label: 'List' }]}
            />
          </Toolbar>
          <table className={settingsTable.table}>
            <thead>
              <tr className={settingsTable.headRow}>
                <th className={settingsTable.th}>Name</th>
                <th className={settingsTable.th}>Status</th>
              </tr>
            </thead>
            <tbody>
              {['report.pdf', 'notes.md'].map((name) => (
                <tr key={name} className={settingsTable.row}>
                  <td className={settingsTable.td}>{name}</td>
                  <td className={settingsTable.td}><Badge variant="success">Synced</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Specimen>

      <Specimen id="tabs" entries={sections.tabs}>
        <Tabs
          label="Scope"
          value={tab}
          onChange={setTab}
          items={[
            { id: 'all', label: 'All', count: 12 },
            { id: 'mine', label: 'Mine', count: 3 },
            { id: 'shared', label: 'Shared with me' },
          ]}
        />
      </Specimen>

      <Specimen id="menus" entries={sections.menus}>
        <Row label="menu bar">
          <MenuBar label="Demo menus" title="Files">
            <Menu label="File" items={MENU_ITEMS} />
            <Menu label="Edit" items={[{ id: 'undo', label: 'Undo', shortcut: '⌘Z' }]} />
            <Menu label="View" disabled title="Nothing to view" items={[]} />
          </MenuBar>
        </Row>
        <Row label="overflow">
          <Menu
            align="end"
            trigger={<Button size="icon" variant="ghost" aria-label="More actions"><MoreHorizontal size={14} /></Button>}
            items={[{ id: 'rename', label: 'Rename' }, { id: 'archive', label: 'Archive', destructive: true }]}
          />
        </Row>
      </Specimen>

      <Specimen id="tree" entries={sections.tree}>
        <ul className="w-64 list-none space-y-0.5 border border-border p-2">
          <li>
            <TreeRow
              twisty={<TreeTwisty expanded={expanded} label="Toggle Projects" onToggle={() => setExpanded(!expanded)} />}
              actions={<Button size="icon" variant="ghost" className="h-5 w-5" aria-label="More"><MoreHorizontal size={12} /></Button>}
            >
              <button type="button" className={treeRowClass()}><Folder size={11} /> <span className="truncate">Projects</span></button>
            </TreeRow>
            {expanded ? (
              <ul className="ml-3 list-none space-y-0.5 p-0">
                <li>
                  <TreeRow twisty={<TreeTwisty />}>
                    <button type="button" className={treeRowClass({ active: true })}><FileText size={11} /> <span className="truncate">Roadmap (open)</span></button>
                  </TreeRow>
                </li>
                <li>
                  <TreeRow twisty={<TreeTwisty />}>
                    <span className={treeRowClass({ muted: true })}><FileText size={11} /> <span className="truncate">project.json</span></span>
                  </TreeRow>
                </li>
              </ul>
            ) : null}
          </li>
        </ul>
      </Specimen>

      <Specimen id="split" entries={sections.split}>
        <SplitDemo />
      </Specimen>

      <Specimen id="dialogs" entries={sections.dialogs}>
        <Row label="sizes">
          {(['sm', 'md', 'lg', 'xl', 'full'] as DialogSize[]).map((size) => (
            <Button key={size} size="sm" variant="secondary" onClick={() => setDialog(size)}>
              {size}
            </Button>
          ))}
        </Row>
        <Row label="confirm">
          <Button size="sm" variant="secondary" onClick={() => void confirm({ title: 'Archive this page?', description: 'You can restore it from the archive.', confirmLabel: 'Archive', destructive: false })}>
            Confirm
          </Button>
          <Button size="sm" variant="destructive" onClick={() => void confirm({ title: 'Delete workspace “acme”?', description: 'Its files, chats and agents are deleted. This cannot be undone.', confirmText: 'acme' })}>
            Type to confirm
          </Button>
          <Button size="sm" variant="secondary" onClick={() => void prompt({ title: 'Rename', defaultValue: 'Roadmap', confirmLabel: 'Rename' })}>
            Prompt
          </Button>
        </Row>
        {confirmDialog}
        {promptDialog}
        <Dialog
          open={dialog !== null}
          size={dialog ?? 'md'}
          title={`Dialog · ${dialog}`}
          description="Header, scrolling body, footer."
          dismissible={!saving}
          onClose={() => setDialog(null)}
          onSubmit={() => setDialog(null)}
          footer={
            <>
              <span className="text-xs text-muted-foreground">⌘↵ to save</span>
              <Button variant="ghost" onClick={() => setDialog(null)} disabled={saving}>Cancel</Button>
              <Button variant="secondary" onClick={() => { setSaving(true); window.setTimeout(() => setSaving(false), 2000); }} disabled={saving}>
                {saving ? 'Saving…' : 'Not dismissible for 2 s'}
              </Button>
              <Button onClick={() => setDialog(null)} disabled={saving}>Save</Button>
            </>
          }
        >
          <Field label="Name" htmlFor="theme-dialog-name">
            <Input id="theme-dialog-name" defaultValue="Roadmap" />
          </Field>
        </Dialog>
      </Specimen>

      <Specimen id="toasts" entries={sections.toasts}>
        <Row label="tones">
          <Button size="sm" variant="secondary" onClick={() => toast.success('Saved', 'The workspace name is now “Acme”.')}>Success</Button>
          <Button size="sm" variant="secondary" onClick={() => toast.error('Could not delete', 'The server answered 409: the key is in use.')}>Error</Button>
          <Button size="sm" variant="secondary" onClick={() => toast({ title: 'Export started', detail: 'You will get a link by email.' })}>Info</Button>
        </Row>
      </Specimen>
    </div>
  );
}
