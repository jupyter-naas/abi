import { describe, expect, it } from 'vitest';
import type { MemberCandidate } from '@/lib/people';
import { addPeopleListing, addableRoles, moveActive, optionText } from './add-people-model';

const person = (over: Partial<MemberCandidate>): MemberCandidate => ({
  user_id: 'usr_flo',
  name: 'Florent',
  email: 'florent@naas.ai',
  avatar: null,
  status: 'active',
  org_role: 'member',
  ...over,
});

const FLO = person({});
const FLO2 = person({ user_id: 'usr_flo2', name: null, email: 'florent.frvservices@gmail.com' });

describe('the listbox of Add people', () => {
  it('offers nothing below two characters', () => {
    expect(addPeopleListing('F', { text: 'F', items: [FLO] })).toEqual({ ready: false, options: [], excluded: 0 });
  });

  it("never shows an older text's suggestions", () => {
    expect(addPeopleListing('Flor', { text: 'Flo', items: [FLO] }).ready).toBe(false);
  });

  it('lists the suggestions of the text, and no create entry while some match', () => {
    const listing = addPeopleListing('Flo', { text: 'Flo', items: [FLO, FLO2] });
    expect(listing.ready).toBe(true);
    expect(listing.options.map(optionText)).toEqual(['Florent', 'florent.frvservices@gmail.com']);
  });

  it('leaves out people already members here, and says how many', () => {
    const listing = addPeopleListing('Flo', { text: 'Flo', items: [FLO, FLO2] }, new Set(['usr_flo']));
    expect(listing.options.map((o) => o.key)).toEqual(['candidate:usr_flo2']);
    expect(listing.excluded).toBe(1);
  });

  it("offers Create user '<text>' when nobody matches", () => {
    const listing = addPeopleListing('Zoé', { text: 'Zoé', items: [] });
    expect(listing.options.map(optionText)).toEqual(["Create user 'Zoé'"]);
    const allMembers = addPeopleListing('Flo', { text: 'Flo', items: [FLO] }, new Set(['usr_flo']));
    expect(allMembers.options.map((o) => o.kind)).toEqual(['create']);
  });

  it('offers Create user for an email no suggestion has (someone of another organization)', () => {
    const typed = 'florent@other.org';
    const listing = addPeopleListing(typed, { text: typed, items: [FLO] });
    expect(listing.options.map((o) => o.kind)).toEqual(['candidate', 'create']);
    const exact = addPeopleListing('florent@naas.ai', { text: 'florent@naas.ai', items: [FLO] });
    expect(exact.options.map((o) => o.kind)).toEqual(['candidate']);
  });
});

describe('the keyboard', () => {
  it('moves down and up, wrapping around', () => {
    expect(moveActive(-1, 'ArrowDown', 3)).toBe(0);
    expect(moveActive(0, 'ArrowDown', 3)).toBe(1);
    expect(moveActive(2, 'ArrowDown', 3)).toBe(0);
    expect(moveActive(-1, 'ArrowUp', 3)).toBe(2);
    expect(moveActive(0, 'ArrowUp', 3)).toBe(2);
    expect(moveActive(2, 'ArrowUp', 3)).toBe(1);
  });

  it('goes to the first and the last with Home and End', () => {
    expect(moveActive(1, 'Home', 3)).toBe(0);
    expect(moveActive(1, 'End', 3)).toBe(2);
  });

  it('has nothing to move to in an empty list', () => {
    expect(moveActive(0, 'ArrowDown', 0)).toBe(-1);
  });
});

describe('the roles a pick offers', () => {
  it('gives owner only to an owner', () => {
    expect(addableRoles('admin')).toEqual(['member', 'viewer', 'admin']);
    expect(addableRoles(undefined)).toEqual(['member', 'viewer', 'admin']);
    expect(addableRoles('owner')).toEqual(['member', 'viewer', 'admin', 'owner']);
  });
});
