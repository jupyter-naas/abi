"""The ``IAMStore`` contract every adapter passes: subclass it, provide ``store``."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

import pytest
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import (
    Attachment,
    ContainerRecord,
    GroupMapping,
    IAMConflictError,
    IAMNotFoundError,
    IAMStore,
    KeyRecord,
    LegacyPlacement,
    ManifestRecord,
    NameRewriter,
    PendingGrant,
    Placement,
    Policy,
    PrincipalRecord,
    RevisionConflictError,
    SigningKeyRecord,
    new_id,
)
from naas_abi_core.services.iam.names import (
    PLATFORM,
    UNRESOLVED,
    container_name,
)
from naas_abi_core.services.iam.policy import PolicyDocument, Statement

ORG = container_name("nexus", "organization", "org-1")
WS = container_name("nexus", "workspace", "ws-1", parent=ORG)
WS_2 = container_name("nexus", "workspace", "ws-2", parent=ORG)

DOCUMENT = PolicyDocument(
    statements=(
        Statement(
            "Allow", ("triple_store:Query",), ("abi:triple_store:graph/*",), "Read"
        ),
        Statement("Deny", ("*",), ("*",)),
    )
)


def user(subject: str = "bob", issuer: str = "https://idp.example") -> PrincipalRecord:
    return PrincipalRecord(
        id=new_id("usr"),
        kind="user",
        issuer=issuer,
        subject=subject,
        email=f"{subject}@example.com",
        display_name=subject.title(),
    )


def service_account(name: str = "module/acme/people") -> PrincipalRecord:
    return PrincipalRecord(id=new_id("sa"), kind="service_account", name=name)


def group(name: str = "sales") -> PrincipalRecord:
    return PrincipalRecord(id=new_id("grp"), kind="group", name=name)


def policy(policy_id: str | None = None, name: str = "read") -> Policy:
    return Policy(id=policy_id or new_id("pol"), name=name, document=DOCUMENT)


class IAMStoreContract(ABC):
    @pytest.fixture
    @abstractmethod
    def store(self) -> IAMStore: ...

    # -- principals ---------------------------------------------------------------

    def test_principals_round_trip(self, store: IAMStore):
        bob = store.create_principal(user())
        assert bob.created_at is not None and bob.created_at.tzinfo is not None
        assert store.get_principal(bob.id) == bob
        assert bob.status == "active" and bob.email == "bob@example.com"
        assert store.find_user("https://idp.example", "bob") == bob
        assert store.find_user("https://other.example", "bob") is None
        account = store.create_principal(service_account())
        assert store.find_service_account("module/acme/people") == account
        assert store.find_service_account("other") is None
        with pytest.raises(IAMNotFoundError):
            store.get_principal(new_id("usr"))

    def test_user_identity_and_service_account_names_are_unique(self, store: IAMStore):
        store.create_principal(user("bob"))
        with pytest.raises(IAMConflictError):
            store.create_principal(user("bob"))
        store.create_principal(user("bob", issuer="https://other.example"))
        store.create_principal(service_account("ci/nightly"))
        with pytest.raises(IAMConflictError):
            store.create_principal(service_account("ci/nightly"))
        # Groups and users carry no service-account name: no collision.
        store.create_principal(group("ci/nightly"))
        first = store.create_principal(group("sales"))
        with pytest.raises(IAMConflictError):
            store.create_principal(first)

    def test_update_keeps_identity_and_creation(self, store: IAMStore):
        bob = store.create_principal(user())
        from dataclasses import replace

        updated = store.update_principal(
            replace(
                bob,
                status="suspended",
                email="robert@example.com",
                issuer="https://evil.example",
                subject="mallory",
            )
        )
        assert updated.status == "suspended"
        assert updated.email == "robert@example.com"
        assert (updated.issuer, updated.subject) == ("https://idp.example", "bob")
        assert updated.created_at == bob.created_at
        assert store.get_principal(bob.id) == updated
        with pytest.raises(IAMNotFoundError):
            store.update_principal(user("ghost"))

    def test_a_linked_identity_finds_its_principal(self, store: IAMStore):
        bob = store.create_principal(user("bob"))
        store.link_identity("https://new.example", "s1", bob.id)
        assert store.find_user("https://new.example", "s1") == bob
        assert store.find_user("https://idp.example", "bob") == bob
        # Linking again to the same principal changes nothing.
        store.link_identity("https://new.example", "s1", bob.id)
        assert store.find_user("https://new.example", "s1") == bob

    def test_a_link_wins_over_a_principal_holding_the_identity(self, store: IAMStore):
        bob = store.create_principal(user("bob"))
        created_later = store.create_principal(user("s1", issuer="https://new.example"))
        store.link_identity("https://new.example", "s1", bob.id)
        assert store.find_user("https://new.example", "s1") == bob
        assert store.get_principal(created_later.id) == created_later

    def test_an_identity_links_to_one_principal(self, store: IAMStore):
        bob = store.create_principal(user("bob"))
        ann = store.create_principal(user("ann"))
        store.link_identity("https://new.example", "s1", bob.id)
        with pytest.raises(IAMConflictError):
            store.link_identity("https://new.example", "s1", ann.id)
        assert store.find_user("https://new.example", "s1") == bob

    def test_only_a_user_takes_a_link(self, store: IAMStore):
        account = store.create_principal(service_account())
        with pytest.raises(IAMNotFoundError):
            store.link_identity("https://new.example", "s1", new_id("usr"))
        with pytest.raises(IAMConflictError):
            store.link_identity("https://new.example", "s1", account.id)

    def test_a_link_is_a_change(self, store: IAMStore):
        bob = store.create_principal(user("bob"))
        before = store.revision()
        store.link_identity("https://new.example", "s1", bob.id)
        assert store.revision() > before

    def test_list_principals_pages_by_id_and_kind(self, store: IAMStore):
        created = [store.create_principal(user(f"u{i}")) for i in range(5)]
        store.create_principal(service_account())
        page = store.list_principals("user", limit=2)
        ids = sorted(p.id for p in created)
        assert [p.id for p in page.items] == ids[:2]
        assert page.next_after == ids[1]
        rest = store.list_principals("user", limit=10, after=page.next_after)
        assert [p.id for p in rest.items] == ids[2:]
        assert rest.next_after is None
        assert len(store.list_principals(limit=10).items) == 6
        with pytest.raises(ValueError):
            store.list_principals(limit=0)

    # -- groups -------------------------------------------------------------------

    def test_group_membership(self, store: IAMStore):
        sales = store.create_principal(group())
        bob = store.create_principal(user())
        ci = store.create_principal(service_account())
        store.add_group_member(sales.id, bob.id)
        store.add_group_member(sales.id, bob.id)  # idempotent
        store.add_group_member(sales.id, ci.id)
        assert store.list_group_members(sales.id) == sorted([bob.id, ci.id])
        assert store.groups_of(bob.id) == [sales.id]
        assert store.remove_group_member(sales.id, bob.id) is True
        assert store.remove_group_member(sales.id, bob.id) is False
        assert store.groups_of(bob.id) == []
        with pytest.raises(IAMNotFoundError):
            store.add_group_member(sales.id, new_id("usr"))

    def test_idp_group_mappings(self, store: IAMStore):
        sales = store.create_principal(group("sales"))
        ops = store.create_principal(group("ops"))
        store.map_idp_group(GroupMapping("acme", "Sales", sales.id))
        store.map_idp_group(GroupMapping("acme", "Sales", sales.id))  # idempotent
        store.map_idp_group(GroupMapping("acme", "Everyone", sales.id))
        store.map_idp_group(GroupMapping("acme", "Everyone", ops.id))
        store.map_idp_group(GroupMapping("other", "Ops", ops.id))
        assert store.resolve_idp_groups("acme", ["Sales", "Unknown"]) == [sales.id]
        assert store.resolve_idp_groups("acme", ["Everyone"]) == sorted(
            [sales.id, ops.id]
        )
        assert store.resolve_idp_groups("acme", ["Ops"]) == []
        assert store.resolve_idp_groups("acme", []) == []
        assert len(store.list_idp_group_mappings()) == 4
        assert store.list_idp_group_mappings(ops.id) == [
            GroupMapping("acme", "Everyone", ops.id),
            GroupMapping("other", "Ops", ops.id),
        ]
        assert store.unmap_idp_group(GroupMapping("other", "Ops", ops.id)) is True
        assert store.unmap_idp_group(GroupMapping("other", "Ops", ops.id)) is False
        with pytest.raises(IAMNotFoundError):
            store.map_idp_group(GroupMapping("acme", "X", new_id("grp")))

    # -- policies -----------------------------------------------------------------

    def test_policies_round_trip_with_revisions(self, store: IAMStore):
        created = store.create_policy(policy())
        assert created.revision == 1 and created.managed is False
        assert store.get_policy(created.id).document == DOCUMENT
        with pytest.raises(IAMConflictError):
            store.create_policy(policy(created.id))
        from dataclasses import replace

        document = PolicyDocument(
            statements=(Statement("Allow", ("iam:GetPolicy",), ("*",)),)
        )
        updated = store.update_policy(
            replace(created, name="renamed", document=document), expected_revision=1
        )
        assert (updated.revision, updated.name, updated.document) == (
            2,
            "renamed",
            document,
        )
        with pytest.raises(RevisionConflictError):
            store.update_policy(replace(created, name="stale"), expected_revision=1)
        with pytest.raises(IAMNotFoundError):
            store.update_policy(policy(), expected_revision=1)
        with pytest.raises(IAMNotFoundError):
            store.get_policy("pol_missing")

    def test_managed_policy_revision_moves_only_on_change(self, store: IAMStore):
        managed = Policy(
            id="builtin.viewer", name="Viewer", document=DOCUMENT, managed=True
        )
        first = store.put_managed_policy(managed)
        assert (first.revision, first.managed) == (1, True)
        revision = store.revision()
        assert store.put_managed_policy(managed).revision == 1
        assert store.revision() == revision
        from dataclasses import replace

        changed = store.put_managed_policy(replace(managed, description="new"))
        assert changed.revision == 2
        assert store.revision() > revision

    def test_list_policies_pages(self, store: IAMStore):
        ids = sorted(store.create_policy(policy()).id for _ in range(3))
        page = store.list_policies(limit=2)
        assert [p.id for p in page.items] == ids[:2]
        assert [p.id for p in store.list_policies(after=page.next_after).items] == ids[
            2:
        ]

    def test_owner_scopes_are_kept_and_filter_lists(self, store: IAMStore):
        from dataclasses import replace

        platform = store.create_policy(policy())
        mine = store.create_policy(replace(policy(), owner_scope=WS))
        org = store.create_policy(replace(policy(), owner_scope=ORG))
        assert platform.owner_scope == PLATFORM
        assert store.get_policy(mine.id).owner_scope == WS
        listed = store.list_policies(owner_scopes=[WS, ORG])
        assert [p.id for p in listed.items] == sorted([mine.id, org.id])
        assert store.list_policies(owner_scopes=[]).items == []
        updated = store.update_policy(replace(mine, name="renamed"), 1)
        assert updated.owner_scope == WS

        team = store.create_principal(replace(group(), owner_scope=WS))
        everyone = store.create_principal(group("everyone"))
        assert everyone.owner_scope == PLATFORM
        assert store.get_principal(team.id).owner_scope == WS
        owned = store.list_principals("group", owner_scopes=[WS])
        assert [g.id for g in owned.items] == [team.id]
        kept = store.update_principal(replace(team, name="analysts"))
        assert (kept.name, kept.owner_scope) == ("analysts", WS)

    def test_attached_policy_cannot_be_deleted(self, store: IAMStore):
        read = store.create_policy(policy())
        bob = store.create_principal(user())
        store.attach(Attachment(new_id("att"), read.id, bob.id))
        with pytest.raises(IAMConflictError):
            store.delete_policy(read.id)
        assert store.detach(read.id, bob.id, None) is True
        store.delete_policy(read.id)
        with pytest.raises(IAMNotFoundError):
            store.get_policy(read.id)
        with pytest.raises(IAMNotFoundError):
            store.delete_policy(read.id)

    def test_a_parent_is_kept_changed_and_lists_its_sub_policies(self, store: IAMStore):
        from dataclasses import replace

        parent = store.create_policy(policy())
        other = store.create_policy(policy())
        child = store.create_policy(replace(policy(), parent_id=parent.id))
        assert parent.parent_id is None
        assert store.get_policy(child.id).parent_id == parent.id
        assert [p.id for p in store.list_sub_policies(parent.id)] == [child.id]
        assert store.list_sub_policies(child.id) == []
        moved = store.update_policy(replace(child, parent_id=other.id), 1)
        assert (moved.parent_id, moved.revision) == (other.id, 2)
        assert store.list_sub_policies(parent.id) == []
        assert [p.id for p in store.list_sub_policies(other.id)] == [child.id]
        freed = store.update_policy(replace(moved, parent_id=None), 2)
        assert freed.parent_id is None
        # A parent that does not exist is refused, on create and on update.
        with pytest.raises(IAMNotFoundError):
            store.create_policy(replace(policy(), parent_id=new_id("pol")))
        with pytest.raises(IAMNotFoundError):
            store.update_policy(replace(freed, parent_id=new_id("pol")), 3)
        assert store.get_policy(child.id).revision == 3

    def test_a_parent_with_sub_policies_cannot_be_deleted(self, store: IAMStore):
        from dataclasses import replace

        parent = store.create_policy(policy())
        child = store.create_policy(replace(policy(), parent_id=parent.id))
        with pytest.raises(IAMConflictError):
            store.delete_policy(parent.id)
        store.delete_policy(child.id)
        store.delete_policy(parent.id)
        with pytest.raises(IAMNotFoundError):
            store.get_policy(parent.id)

    def test_a_managed_policy_has_no_parent(self, store: IAMStore):
        from dataclasses import replace

        parent = store.create_policy(policy())
        managed = store.put_managed_policy(
            Policy(
                id="builtin.viewer",
                name="Viewer",
                document=DOCUMENT,
                managed=True,
                parent_id=parent.id,
            )
        )
        assert managed.parent_id is None
        child = store.create_policy(replace(policy(), parent_id=managed.id))
        assert child.parent_id == "builtin.viewer"

    # -- attachments --------------------------------------------------------------

    def test_attachments(self, store: IAMStore):
        read = store.create_policy(policy())
        bob = store.create_principal(user())
        sales = store.create_principal(group())
        plain = store.attach(Attachment(new_id("att"), read.id, bob.id))
        scoped = store.attach(Attachment(new_id("att"), read.id, bob.id, WS))
        via_group = store.attach(Attachment(new_id("att"), read.id, sales.id))
        assert plain.scope is None and scoped.scope == WS
        assert plain.created_at is not None
        with pytest.raises(IAMConflictError):
            store.attach(Attachment(new_id("att"), read.id, bob.id, WS))
        assert {a.id for a in store.list_attachments(principal_id=bob.id)} == {
            plain.id,
            scoped.id,
        }
        assert len(store.list_attachments(policy_id=read.id)) == 3
        assert {a.id for a in store.attachments_for([bob.id, sales.id])} == {
            plain.id,
            scoped.id,
            via_group.id,
        }
        assert store.attachments_for([]) == []
        assert store.detach(read.id, bob.id, WS) is True
        assert store.detach(read.id, bob.id, WS) is False
        assert store.list_attachments(principal_id=bob.id) == [plain]

    def test_attach_needs_the_policy_and_the_principal(self, store: IAMStore):
        read = store.create_policy(policy())
        bob = store.create_principal(user())
        with pytest.raises(IAMNotFoundError):
            store.attach(Attachment(new_id("att"), "pol_missing", bob.id))
        with pytest.raises(IAMNotFoundError):
            store.attach(Attachment(new_id("att"), read.id, new_id("usr")))

    # -- pending grants -----------------------------------------------------------

    def test_pending_grants_round_trip(self, store: IAMStore):
        read = store.create_policy(policy())
        scope = WS
        first = store.add_pending_grant(
            PendingGrant(new_id("pgr"), "builtin", "bob@example.com", read.id, scope)
        )
        assert first.created_at is not None and first.scope == scope
        unscoped = store.add_pending_grant(
            PendingGrant(
                new_id("pgr"), "builtin", "bob@example.com", read.id, created_by="usr_a"
            )
        )
        assert unscoped.scope is None and unscoped.created_by == "usr_a"
        other_provider = store.add_pending_grant(
            PendingGrant(new_id("pgr"), "acme", "bob@example.com", read.id, scope)
        )
        with pytest.raises(IAMConflictError):
            store.add_pending_grant(
                PendingGrant(
                    new_id("pgr"), "builtin", "bob@example.com", read.id, scope
                )
            )
        with pytest.raises(IAMNotFoundError):
            store.add_pending_grant(
                PendingGrant(new_id("pgr"), "builtin", "x@example.com", "pol_missing")
            )
        # Ordered by id; ids made within one millisecond are not ordered.
        assert store.list_pending_grants() == sorted(
            [first, unscoped, other_provider], key=lambda g: g.id
        )
        assert store.list_pending_grants(provider="acme") == [other_provider]
        assert store.list_pending_grants(email="nobody@example.com") == []
        assert store.list_pending_grants(policy_id=read.id, provider="builtin") == (
            sorted([first, unscoped], key=lambda g: g.id)
        )
        assert store.get_pending_grant(first.id) == first
        assert store.get_pending_grant("pgr_missing") is None
        with pytest.raises(IAMConflictError):  # an invitee still names it
            store.delete_policy(read.id)
        assert store.remove_pending_grant(unscoped.id) is True
        assert store.remove_pending_grant(unscoped.id) is False
        assert store.list_pending_grants(provider="builtin") == [first]

    def test_claiming_a_pending_grant_attaches_it_once(self, store: IAMStore):
        read = store.create_policy(policy())
        bob = store.create_principal(user())
        scope = WS
        grant = store.add_pending_grant(
            PendingGrant(new_id("pgr"), "builtin", "bob@example.com", read.id, scope)
        )
        before = store.revision()
        attached = store.claim_pending_grant(grant.id, bob.id, new_id("att"))
        assert attached is not None and store.revision() > before
        assert (attached.policy_id, attached.principal_id, attached.scope) == (
            read.id,
            bob.id,
            scope,
        )
        assert store.list_attachments(principal_id=bob.id) == [attached]
        assert store.list_pending_grants() == []
        # The second claim finds nothing: exactly one caller wins.
        assert store.claim_pending_grant(grant.id, bob.id, new_id("att")) is None
        assert len(store.list_attachments(principal_id=bob.id)) == 1

    def test_claiming_keeps_an_attachment_that_exists(self, store: IAMStore):
        read = store.create_policy(policy())
        bob = store.create_principal(user())
        held = store.attach(Attachment(new_id("att"), read.id, bob.id, WS))
        grant = store.add_pending_grant(
            PendingGrant(new_id("pgr"), "builtin", "bob@example.com", read.id, WS)
        )
        assert store.claim_pending_grant(grant.id, bob.id, new_id("att")) == held
        assert store.list_attachments(principal_id=bob.id) == [held]
        assert store.list_pending_grants() == []

    def test_claiming_needs_the_principal(self, store: IAMStore):
        read = store.create_policy(policy())
        grant = store.add_pending_grant(
            PendingGrant(new_id("pgr"), "builtin", "bob@example.com", read.id)
        )
        with pytest.raises(IAMNotFoundError):
            store.claim_pending_grant(grant.id, new_id("usr"), new_id("att"))
        assert store.list_pending_grants() == [grant]

    # -- placements and containers ----------------------------------------------

    def test_placements(self, store: IAMStore):
        store.put_placement(Placement("document", "nexus-ws-1", WS))
        store.put_placement(Placement("document", "nexus-ws-1/*", WS))
        store.put_placement(Placement("triple_store", "http%3A%2F%2Fx", WS_2))
        store.put_placement(Placement("document", "nexus-ws-1", ORG))
        store.put_placement(Placement("document", "module", PLATFORM))
        assert store.list_placements("document") == [
            Placement("document", "module", PLATFORM),
            Placement("document", "nexus-ws-1", ORG),
            Placement("document", "nexus-ws-1/*", WS),
        ]
        assert len(store.list_placements()) == 4
        assert store.delete_placement("document", "nexus-ws-1/*") is True
        assert store.delete_placement("document", "nexus-ws-1/*") is False

    def test_containers(self, store: IAMStore):
        org = ContainerRecord("nexus", "organization", "org-1")
        ws = ContainerRecord("nexus", "workspace", "ws-1", ORG)
        store.put_container(org)
        store.put_container(ws)
        before = store.revision()
        store.put_container(ws)  # idempotent
        assert store.revision() == before
        with pytest.raises(IAMConflictError):  # a container never moves
            store.put_container(ContainerRecord("nexus", "workspace", "ws-1"))
        found = store.get_container("nexus", "workspace", "ws-1")
        assert found == ws and found is not None and found.name == WS
        assert store.get_container("nexus", "workspace", "ws-9") is None
        assert store.list_containers() == [org, ws]

    def test_deleting_containers_drops_the_placements_in_them(self, store: IAMStore):
        org = ContainerRecord("nexus", "organization", "org-1")
        ws = ContainerRecord("nexus", "workspace", "ws-1", ORG)
        other = ContainerRecord("nexus", "workspace", "ws-2", ORG)
        for record in (org, ws, other):
            store.put_container(record)
        project = container_name("crm", "project", "p-1", parent=WS)
        store.put_placement(Placement("document", "nexus-ws-1", WS))
        store.put_placement(Placement("crm", "deal-1", project))
        store.put_placement(Placement("document", "nexus-ws-2", WS_2))
        store.put_placement(Placement("document", "module", PLATFORM))
        before = store.revision()
        assert store.delete_containers([ws]) == 1
        assert store.revision() > before
        assert store.delete_containers([]) == 0
        assert store.list_containers() == [org, other]
        # What sat in it or below it goes; the rest stays.
        assert store.list_placements() == [
            Placement("document", "module", PLATFORM),
            Placement("document", "nexus-ws-2", WS_2),
        ]

    def test_rewriting_the_names(self, store: IAMStore):
        from dataclasses import replace

        old = PolicyDocument(
            statements=(
                Statement(
                    "Allow", ("triple_store:Query",), ("${scope}:triple_store:*",)
                ),
            )
        )
        written = store.create_policy(
            replace(policy(), document=old, owner_scope="abi:org-1:ws-1")
        )
        kept = store.create_policy(policy())
        team = store.create_principal(replace(group(), owner_scope="abi:org-1:-"))
        bob = store.create_principal(user())
        attached = store.attach(
            Attachment(new_id("att"), written.id, bob.id, "abi:org-1:ws-1")
        )
        unscoped = store.attach(Attachment(new_id("att"), kept.id, bob.id))
        invited = store.add_pending_grant(
            PendingGrant(
                new_id("pgr"), "builtin", "ann@example.com", kept.id, "abi:org-1:*"
            )
        )
        store.create_key(
            KeyRecord(
                "abcdefghijklmnop",
                bob.id,
                "a" * 64,
                kind="personal",
                scope=(
                    {
                        "effect": "Allow",
                        "actions": ["triple_store:Query"],
                        "resources": ["abi:org-1:ws-1:triple_store:graph/*"],
                    },
                ),
            )
        )
        store.put_placement(Placement("document", "today", WS_2))

        rewriter = _Rewriter()
        counts = store.rewrite_names(rewriter)
        assert counts["containers"] == 2
        assert (counts["policies"], counts["groups"]) == (1, 1)
        assert (counts["attachments"], counts["pending_grants"]) == (1, 1)
        assert counts["keys"] == 1
        assert store.list_containers() == list(rewriter.containers())
        rewritten = store.get_policy(written.id)
        assert rewritten.owner_scope == WS
        assert rewritten.revision == written.revision + 1
        assert rewritten.document.statements[0].resources == (
            "${scope}/triple_store:*",
        )
        assert store.get_policy(kept.id).revision == kept.revision
        assert store.get_principal(team.id).owner_scope == ORG
        assert {a.id: a.scope for a in store.list_attachments(principal_id=bob.id)} == {
            attached.id: WS,
            unscoped.id: None,
        }
        grant = store.get_pending_grant(invited.id)
        assert grant is not None and grant.scope == ORG + "/*"
        key = store.get_key("abcdefghijklmnop")
        assert key is not None and key.scope is not None
        assert key.scope[0]["resources"] == [WS + "/triple_store:graph/*"]
        assert Placement("document", "today", WS_2) in store.list_placements()

        # Again: what is a path already is kept.
        assert set(store.rewrite_names(rewriter).values()) == {0}
        assert store.get_policy(written.id).revision == written.revision + 1

    def test_a_placement_of_the_old_form_is_rewritten(self, store: IAMStore):
        """Only an upgraded store holds one: its SQL test seeds the row, the
        memory store ``seed_legacy_placement``."""
        if not hasattr(store, "seed_legacy_placement"):
            pytest.skip("seeded by the SQL upgrade tests")
        store.seed_legacy_placement(  # type: ignore[attr-defined]
            Placement("document", "nexus-ws-1"), "abi:org-1:ws-1"
        )
        store.seed_legacy_placement(  # type: ignore[attr-defined]
            Placement("document", "nexus-ws-gone"), "abi:org-1:ws-gone"
        )
        assert store.list_placements() == [
            Placement("document", "nexus-ws-1", UNRESOLVED),
            Placement("document", "nexus-ws-gone", UNRESOLVED),
        ]
        rewriter = _Rewriter()
        assert store.rewrite_names(rewriter)["placements"] == 1
        # One the rewriter names no container for stays UNRESOLVED, never the
        # old scope as a container: every name made from it still parses.
        assert store.list_placements() == [
            Placement("document", "nexus-ws-1", WS),
            Placement("document", "nexus-ws-gone", UNRESOLVED),
        ]
        assert rewriter.seen == [
            LegacyPlacement("document", "nexus-ws-1", "abi:org-1:ws-1"),
            LegacyPlacement("document", "nexus-ws-gone", "abi:org-1:ws-gone"),
        ]
        assert store.rewrite_names(rewriter)["placements"] == 0

    def test_no_legacy_scope_sets_on_a_new_store(self, store: IAMStore):
        assert store.legacy_scope_sets() == []
        assert store.drop_legacy_scope_sets() is False

    # -- catalogs and the store -----------------------------------------------------

    def test_catalogs_round_trip(self, store: IAMStore):
        catalog = ActionCatalog(
            service="triple_store",
            version=2,
            resource_types=(
                ResourceType("graph"),
                ResourceType("view", placement="platform"),
            ),
            actions=(
                ActionSpec(
                    "Query",
                    "read",
                    ("graph",),
                    subjects=("abi.svc.triple_store.v1.query",),
                ),
                ActionSpec("CreateGraph", "write", ("graph",), creates=True),
            ),
        )
        store.put_catalog(catalog)
        store.put_catalog(catalog)
        assert store.list_catalogs() == [catalog]

    def test_revision_moves_on_writes_only(self, store: IAMStore):
        start = store.revision()
        bob = store.create_principal(user())
        assert store.revision() > start
        after_write = store.revision()
        store.get_principal(bob.id)
        store.list_principals()
        store.detach("pol_missing", bob.id, None)
        store.remove_group_member(new_id("grp"), bob.id)
        assert store.revision() == after_write

    def test_install_id_is_stable(self, store: IAMStore):
        install_id = store.install_id()
        assert install_id and store.install_id() == install_id

    # -- keys, manifests and signing keys -------------------------------------------

    def test_keys_round_trip(self, store: IAMStore):
        sa = store.create_principal(service_account())
        expires = datetime(2030, 1, 1, tzinfo=UTC)
        created = store.create_key(
            KeyRecord(
                "abcdefghijklmnop",
                sa.id,
                "a" * 64,
                description="dev",
                expires_at=expires,
            )
        )
        assert created.created_at is not None and created.last_used_at is None
        assert store.get_key("abcdefghijklmnop") == created
        assert store.list_keys(sa.id) == [created]
        assert store.list_keys(new_id("sa")) == []
        with pytest.raises(IAMConflictError):
            store.create_key(KeyRecord("abcdefghijklmnop", sa.id, "b" * 64))
        with pytest.raises(IAMNotFoundError):
            store.create_key(KeyRecord("qrstuvwxyz234567", new_id("sa"), "b" * 64))
        with pytest.raises(IAMNotFoundError):
            store.get_key("missingmissingmi")

    def test_a_narrow_key_keeps_its_audience_resource_and_scope(self, store: IAMStore):
        bob = store.create_principal(user())
        scope = (
            {"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]},
        )
        created = store.create_key(
            KeyRecord(
                "abcdefghijklmnop",
                bob.id,
                "a" * 64,
                kind="personal",
                audience="abi:delegated:coding",
                resource="env-1",
                scope=scope,
            )
        )
        assert store.get_key("abcdefghijklmnop") == created
        assert created.audience == "abi:delegated:coding"
        assert created.resource == "env-1"
        assert created.scope == scope
        plain = store.create_key(KeyRecord("qrstuvwxyz234567", bob.id, "b" * 64))
        assert (plain.audience, plain.resource, plain.scope) == (None, None, None)
        assert {k.key_id for k in store.list_keys(bob.id)} == {
            "abcdefghijklmnop",
            "qrstuvwxyz234567",
        }
        # An empty scope is not no scope: it allows nothing.
        empty = store.create_key(
            KeyRecord("zzzzzzzzzzzzzzzz", bob.id, "c" * 64, kind="grant", scope=())
        )
        assert store.get_key(empty.key_id).scope == ()

    def test_token_floors_only_move_forward(self, store: IAMStore):
        bob = store.create_principal(user())
        assert store.token_floors() == {}
        first = datetime(2026, 1, 1, tzinfo=UTC)
        start = store.revision()
        store.set_token_floor(bob.id, first)
        assert store.token_floors() == {bob.id: first}
        assert store.revision() > start
        store.set_token_floor(bob.id, first - timedelta(days=1))
        assert store.token_floors() == {bob.id: first}
        later = first + timedelta(hours=1)
        store.set_token_floor(bob.id, later)
        assert store.token_floors() == {bob.id: later}
        with pytest.raises(IAMNotFoundError):
            store.set_token_floor(new_id("usr"), first)

    def test_revoking_a_key_keeps_the_first_time(self, store: IAMStore):
        sa = store.create_principal(service_account())
        store.create_key(KeyRecord("abcdefghijklmnop", sa.id, "a" * 64))
        first = datetime(2026, 1, 1, tzinfo=UTC)
        start = store.revision()
        assert store.revoke_key("abcdefghijklmnop", first).revoked_at == first
        assert store.revision() > start
        later = first + timedelta(days=1)
        assert store.revoke_key("abcdefghijklmnop", later).revoked_at == first

    def test_touching_a_key_is_not_a_change(self, store: IAMStore):
        sa = store.create_principal(service_account())
        store.create_key(KeyRecord("abcdefghijklmnop", sa.id, "a" * 64))
        start = store.revision()
        at = datetime(2026, 1, 1, tzinfo=UTC)
        store.touch_key("abcdefghijklmnop", at)
        assert store.get_key("abcdefghijklmnop").last_used_at == at
        assert store.revision() == start

    def test_deleting_keys_forgets_them_and_their_narrowing(self, store: IAMStore):
        bob = store.create_principal(user())
        for key_id in ("abcdefghijklmnop", "qrstuvwxyz234567", "zzzzzzzzzzzzzzzz"):
            store.create_key(
                KeyRecord(
                    key_id,
                    bob.id,
                    "a" * 64,
                    kind="grant",
                    audience="abi:delegated:app",
                    resource=f"/app-html/{key_id}",
                    scope=(),
                )
            )
        start = store.revision()
        assert store.delete_keys(["abcdefghijklmnop", "missingmissingmi"]) == 1
        assert store.delete_keys([]) == 0
        assert store.revision() == start  # housekeeping, not a grant
        assert {k.key_id for k in store.list_keys(bob.id)} == {
            "qrstuvwxyz234567",
            "zzzzzzzzzzzzzzzz",
        }
        with pytest.raises(IAMNotFoundError):
            store.get_key("abcdefghijklmnop")
        # The id is free again, and no narrowing of the old key comes back.
        again = store.create_key(KeyRecord("abcdefghijklmnop", bob.id, "b" * 64))
        assert (again.audience, again.resource, again.scope) == (None, None, None)

    def test_manifests_round_trip(self, store: IAMStore):
        sa = store.create_principal(service_account())
        document = {"version": "2026-10-13", "statements": []}
        pending = store.put_manifest(
            ManifestRecord(sa.id, "f" * 64, "people", "acme", document)
        )
        assert pending.status == "pending" and pending.submitted_at is not None
        assert store.get_manifest(sa.id, "f" * 64) == pending
        approved = store.put_manifest(
            ManifestRecord(
                sa.id,
                "f" * 64,
                "people",
                "acme",
                document,
                status="approved",
                submitted_at=pending.submitted_at,
                decided_at=datetime(2026, 1, 1, tzinfo=UTC),
                decided_by="sa_admin",
            )
        )
        assert store.list_manifests(sa.id) == [approved]
        assert store.list_manifests(status="pending") == []
        assert store.list_manifests(status="approved") == [approved]
        with pytest.raises(IAMNotFoundError):
            store.get_manifest(sa.id, "0" * 64)
        with pytest.raises(IAMNotFoundError):
            store.put_manifest(
                ManifestRecord(new_id("sa"), "f" * 64, "x", "acme", document)
            )

    def test_signing_keys_round_trip(self, store: IAMStore):
        now = datetime(2026, 10, 15, tzinfo=UTC)
        record = SigningKeyRecord(
            "20261015-0a1b2c3d", {"kty": "EC", "kid": "20261015-0a1b2c3d"}, now, now
        )
        store.add_signing_key(record)
        assert store.list_signing_keys() == [record]
        with pytest.raises(IAMConflictError):
            store.add_signing_key(record)
        retired = now + timedelta(minutes=20)
        store.retire_signing_key(record.kid, retired)
        store.retire_signing_key(record.kid, retired + timedelta(days=1))
        assert store.list_signing_keys()[0].retires_at == retired


class _Rewriter(NameRewriter):
    """The names of org-1 and its workspaces, as Nexus rewrites them: ``abi:O:W``
    to its workspace, ``abi:O:-`` to the org, ``abi:O:*`` below it."""

    def __init__(self) -> None:
        self.seen: list[LegacyPlacement] = []

    def containers(self) -> list[ContainerRecord]:
        return [
            ContainerRecord("nexus", "organization", "org-1"),
            ContainerRecord("nexus", "workspace", "ws-1", ORG),
        ]

    def _container(self, old: str) -> str:
        _, org, workspace = old.split(":")
        if workspace == "ws-gone":
            return old  # a workspace Nexus no longer knows: named nowhere
        if org == "-":
            return PLATFORM
        org_name = container_name("nexus", "organization", org)
        if workspace == "-":
            return org_name
        if workspace == "*":
            return org_name + "/*"
        return container_name("nexus", "workspace", workspace, parent=org_name)

    def _old(self, value: str) -> bool:
        return value.startswith("abi:") and value.count(":") == 2 and "/" not in value

    def scope(self, scope: str | None) -> str | None:
        return self._container(scope) if scope and self._old(scope) else scope

    def owner(self, owner: str) -> str:
        return self._container(owner) if self._old(owner) else owner

    def _pattern(self, pattern: str) -> str:
        if pattern.startswith("${scope}:"):
            return "${scope}/" + pattern[len("${scope}:") :]
        parts = pattern.split(":", 3)
        if len(parts) == 4 and parts[0] == "abi" and "/" not in parts[1] + parts[2]:
            container = self._container(":".join(parts[:3]))
            return (
                f"{container}/{parts[3]}"
                if container != PLATFORM
                else f"abi:{parts[3]}"
            )
        return pattern

    def statements(self, statements):
        return [
            {**s, "resources": [self._pattern(r) for r in s["resources"]]}
            for s in statements
        ]

    def document(self, document):
        return {**document, "statements": self.statements(document["statements"])}

    def placement(self, placement: LegacyPlacement) -> str:
        self.seen.append(placement)
        return self._container(placement.scope)
