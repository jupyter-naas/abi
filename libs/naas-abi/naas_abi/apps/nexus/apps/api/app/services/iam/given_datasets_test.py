from naas_abi.apps.nexus.apps.api.app.services.iam import given_datasets
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    Offer,
    in_offer_form,
    offer_document,
    offer_of,
    with_offer,
)
from naas_abi_core.services.iam.policy import MAX_PATTERNS


def test_a_closed_namespace_is_named_within_the_scope_and_read_back():
    assert given_datasets.closed_name("finance") == "${scope}/nexus:dataset/finance"
    assert given_datasets.namespace_of("${scope}/nexus:dataset/finance") == "finance"
    # Anything else is no closure: a dataset, a wildcard, an absolute name, another type.
    assert given_datasets.namespace_of("${scope}/nexus:dataset/finance/sales") is None
    assert given_datasets.namespace_of("${scope}/nexus:dataset/*") is None
    assert given_datasets.namespace_of("abi:nexus:dataset/finance") is None
    assert given_datasets.namespace_of("${scope}/nexus:layout/finance") is None


def test_the_namespaces_a_workspace_closes_are_a_deny_of_its_offer_and_back():
    offer = Offer.of(features=["datasets"], datasets_closed=["hr", "finance"])
    document = offer_document(offer)
    deny = [s for s in document["statements"] if s["sid"] == given_datasets.DENY_SID]
    assert deny == [
        {
            "sid": "OfferDatasetsDeny",
            "effect": "Deny",
            "actions": list(given_datasets.ACTIONS),
            "resources": ["${scope}/nexus:dataset/finance", "${scope}/nexus:dataset/hr"],
        }
    ]
    assert in_offer_form(document)
    assert offer_of(document).datasets_closed == frozenset({"hr", "finance"})


def test_closing_past_the_pattern_limit_writes_parts():
    closed = [f"ns{i:03}" for i in range(MAX_PATTERNS + 3)]
    statements = given_datasets.statements(closed)
    assert [s["sid"] for s in statements] == ["OfferDatasetsDeny", "OfferDatasetsDeny2"]
    assert offer_of({"statements": statements}).datasets_closed == frozenset(closed)


def test_reopening_keeps_the_rest_of_the_offer():
    document = offer_document(Offer.of(features=["datasets", "chat"], datasets_closed=["hr"]))
    reopened = with_offer(document, Offer.of(features=["datasets", "chat"]))
    assert offer_of(reopened).datasets_closed == frozenset()
    assert offer_of(reopened).features == frozenset({"datasets", "chat"})


def test_merging_never_opens_what_either_closes():
    a = Offer.of(datasets_closed=["hr"])
    b = Offer.of(datasets_closed=["finance"])
    assert a.merged(b).datasets_closed == frozenset({"hr", "finance"})
    assert a.merged(b).without(b).datasets_closed == frozenset({"hr"})
    assert not a.is_empty()


def test_a_closed_dataset_is_named_in_its_namespace_and_read_back():
    # One dataset of a namespace, as IAM names it (``dataset/<namespace>/<name>``).
    assert given_datasets.closed_name("finance/sales") == "${scope}/nexus:dataset/finance/sales"
    assert given_datasets.entry_of("${scope}/nexus:dataset/finance/sales") == "finance/sales"
    assert given_datasets.entry_of("${scope}/nexus:dataset/finance") == "finance"
    assert given_datasets.entry_of("${scope}/nexus:dataset/finance/*") is None
    assert given_datasets.entry_of("${scope}/nexus:dataset/a/b/c") is None
    assert given_datasets.split_entry("finance/sales") == ("finance", "sales")
    assert given_datasets.split_entry("finance") == ("finance", None)
    assert given_datasets.valid_entry("finance/sales") and given_datasets.valid_entry("finance")
    assert not given_datasets.valid_entry("finance/") and not given_datasets.valid_entry("a/b/c")


def test_a_workspace_closes_whole_namespaces_and_single_datasets_in_one_deny():
    offer = Offer.of(features=["datasets"], datasets_closed=["hr", "finance/sales"])
    document = offer_document(offer)
    deny = [s for s in document["statements"] if s["sid"] == given_datasets.DENY_SID]
    assert deny[0]["resources"] == [
        "${scope}/nexus:dataset/finance/sales",
        "${scope}/nexus:dataset/hr",
    ]
    assert offer_of(document).datasets_closed == frozenset({"hr", "finance/sales"})
