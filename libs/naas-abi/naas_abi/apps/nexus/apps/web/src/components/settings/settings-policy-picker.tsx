'use client';

/**
 * The policy a workspace's Features and Access pages set, picked in the Settings column under the
 * Features heading, as the organization and the workspace are atop it: "<W> access" (the
 * workspace's offer) first, then the workspace's other policies. The pick is the URL's `?policy=`
 * (`settings-policy.ts`), carried by the links of those pages; with another policy than "<W>
 * access", the Features group lists the pages of the features it grants.
 */
import { useEffect, type ReactNode } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { create } from 'zustand';
import { SearchPicker } from '@/components/shell/sidebar/search-picker';
import { useHoverTip } from '@/components/ui/hover-tip';
import {
  createFeatureAccessApi,
  type FeatureAccessApi,
} from '@/app/workspace/[workspaceId]/settings/features/feature-access-api';
import { editsOffer, type FeatureAccessState } from '@/app/workspace/[workspaceId]/settings/features/feature-access-model';
import { SCOPE_PICKER_DESCRIPTIONS } from './settings-page-descriptions';
import { grantedLinks, policyDriven, policyOfSearch, withPolicy } from './settings-policy';
import type { SettingsLink, SettingsLinkGroup } from './settings-levels';
import './settings-policy-picker.css';

/** The tip waits a pause, as the organization's and the workspace's pickers. */
const POLICY_TIP_DELAY_MS = 1500;

type PolicyView = { status: 'loading' } | { status: 'ready'; state: FeatureAccessState } | { status: 'failed' };

const viewKey = (workspaceId: string, policyId: string | null) => `${workspaceId}|${policyId ?? ''}`;

/**
 * What the column knows of a workspace's policies, by workspace and policy picked: the list the
 * picker offers and the features the policy grants (one read of `/feature-access?policy=`).
 * `forget` drops a workspace's, read again when the column next shows it (a page changed what a
 * policy grants).
 */
export const usePolicyViewStore = create<{
  views: Record<string, PolicyView>;
  load: (workspaceId: string, policyId: string | null, api?: FeatureAccessApi) => void;
  forget: (workspaceId: string) => void;
}>((set, get) => ({
  views: {},
  load: (workspaceId, policyId, api = createFeatureAccessApi()) => {
    const key = viewKey(workspaceId, policyId);
    // A failed read is read again next time, not kept.
    const known = get().views[key];
    if (known && known.status !== 'failed') return;
    set((s) => ({ views: { ...s.views, [key]: { status: 'loading' } } }));
    api.read(workspaceId, policyId).then(
      (state) => set((s) => ({ views: { ...s.views, [key]: { status: 'ready', state } } })),
      () => set((s) => ({ views: { ...s.views, [key]: { status: 'failed' } } }))
    );
  },
  forget: (workspaceId) =>
    set((s) => ({
      views: Object.fromEntries(Object.entries(s.views).filter(([key]) => !key.startsWith(`${workspaceId}|`))),
    })),
}));

/** The policy picker: a search dropdown of the workspace's policies, "<W> access" first. */
export function SettingsPolicyPicker({
  state,
  policyId,
  onPick,
}: {
  state: FeatureAccessState;
  policyId: string | null;
  /** The id picked, null for "<W> access". */
  onPick: (policyId: string | null) => void;
}) {
  const access = state.access_policy;
  const listed = state.policies?.length ? state.policies : access ? [access] : [];
  const value = policyId ?? access?.id ?? listed[0]?.id ?? '';
  const current = listed.find((p) => p.id === value)?.name ?? state.policy?.name ?? value;
  const hover = useHoverTip({ title: 'Policy', description: SCOPE_PICKER_DESCRIPTIONS.policy, delay: POLICY_TIP_DELAY_MS });
  if (listed.length === 0) return null;
  return (
    <div ref={hover.ref} className="settings-policy-picker search-picker-stack" data-policy-picker="" {...hover.anchorProps}>
      {hover.tip}
      <SearchPicker
        single
        size="sm"
        ariaLabel="Switch policy"
        items={listed.map((p) => ({ value: p.id, label: p.name }))}
        value={[value]}
        onToggle={(id) => {
          if (id !== value) onPick(access && id === access.id ? null : id);
        }}
        onClear={() => undefined}
        loading={false}
        error={null}
        label={current}
        noun="policies"
        nativeTitles={false}
      />
    </div>
  );
}

/** What the column does with the policy picked: the links it carries, the Features group's
 *  pages, and the picker under that group's heading. */
export type PolicyNav = {
  /** A link's href, with the policy picked when it opens one of the pages that set it. */
  href: (href: string) => string;
  /** A group's links: the Features group's under another policy, those of what it grants. */
  links: (group: SettingsLinkGroup) => SettingsLink[];
  /** Under a group's heading: the picker, for the Features group. */
  picker: (group: SettingsLinkGroup) => ReactNode;
};

/**
 * A workspace's Settings column under the policy picked (`?policy=`): `children` draws the
 * groups with it. Reads the URL's search: render it inside a Suspense boundary.
 */
export function WorkspacePolicyNav({
  workspaceId,
  children,
}: {
  workspaceId: string;
  children: (nav: PolicyNav) => ReactNode;
}) {
  const pathname = usePathname() ?? '';
  const router = useRouter();
  const policyId = policyOfSearch(useSearchParams());
  const load = usePolicyViewStore((s) => s.load);
  const view = usePolicyViewStore((s) => s.views[viewKey(workspaceId, policyId)]);
  useEffect(() => {
    load(workspaceId, policyId);
  }, [load, workspaceId, policyId]);

  const state = view?.status === 'ready' ? view.state : null;
  // Another policy than "<W> access": the features it grants (Granted: `everyone`).
  const granted =
    policyId && state && !editsOffer(state)
      ? new Set(state.features.filter((row) => row.choice === 'everyone').map((row) => row.key))
      : null;
  const nav: PolicyNav = {
    href: (href) => (policyDriven(href) ? withPolicy(href, policyId) : href),
    links: (group) => (group.label === 'Features' ? grantedLinks(group.links, granted) : group.links),
    picker: (group) =>
      group.label === 'Features' && state ? (
        <SettingsPolicyPicker
          state={state}
          policyId={policyId}
          onPick={(next) => router.push(withPolicy(pathname, next))}
        />
      ) : null,
  };
  return <>{children(nav)}</>;
}
