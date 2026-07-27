"""Tests for ShopifyIntegration against a live Shopify shop.

Credentials are read from the module configuration when the ABI engine is
running, and fall back to the SHOPIFY_SHOP / SHOPIFY_CLIENT_ID /
SHOPIFY_CLIENT_SECRET environment variables otherwise. Every test is skipped
when no credentials are available.

Each read test is also skipped when the shop has not granted the scope it
needs, so the suite reports honestly on any shop rather than failing on
permissions the app was never given.
"""

import os

import pytest
from naas_abi_core import logger
from naas_abi_marketplace.applications.shopify.integrations.ShopifyIntegration import (
    SCOPE_METHOD_MAP,
    SCOPES_WITHOUT_QUERY,
    ShopifyIntegration,
    ShopifyIntegrationConfiguration,
)

# A ShopifyQL statement that is valid on every shop, used to prove the
# analytics endpoint parses and returns a table.
TOTAL_SALES_QUERY = "FROM sales SHOW total_sales GROUP BY day SINCE -30d UNTIL today"

# Shopify rejects these because of how the shop or app is set up, not because
# the query is malformed — treat them as a skip rather than a failure.
ENVIRONMENT_LIMITS = (
    "not associated with any fulfillment service",
    "not available for this account",
)


def _credentials() -> tuple[str, str, str, str] | None:
    """Read Shopify credentials from the module config, then the environment."""
    try:
        from naas_abi_marketplace.applications.shopify import ABIModule

        configuration = ABIModule.get_instance().configuration
        shop = configuration.shop
        client_id = configuration.client_id
        client_secret = configuration.client_secret
        api_version = configuration.api_version
    except (ImportError, ValueError):
        # ValueError: the engine has not loaded the module (standalone pytest).
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass

        shop = os.getenv("SHOPIFY_SHOP")
        client_id = os.getenv("SHOPIFY_CLIENT_ID")
        client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")
        api_version = os.getenv("SHOPIFY_API_VERSION", "2026-07")

    if not (shop and client_id and client_secret):
        return None

    return shop, client_id, client_secret, api_version


@pytest.fixture(scope="module")
def integration() -> ShopifyIntegration:
    """A ShopifyIntegration bound to the configured shop."""
    credentials = _credentials()

    if credentials is None:
        pytest.skip(
            "Shopify credentials not configured "
            "(SHOPIFY_SHOP / SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET)"
        )

    shop, client_id, client_secret, api_version = credentials

    return ShopifyIntegration(
        ShopifyIntegrationConfiguration(
            shop=shop,
            client_id=client_id,
            client_secret=client_secret,
            api_version=api_version,
        )
    )


@pytest.fixture(scope="module")
def granted_scopes(integration: ShopifyIntegration) -> set[str]:
    """The set of access scopes the shop has granted this app."""
    return {scope["handle"] for scope in integration.get_access_scopes()}


@pytest.fixture
def requires_scope(granted_scopes: set[str]):
    """Skip the calling test unless the shop granted the given scope."""

    def _requires(scope: str) -> None:
        if scope not in granted_scopes:
            pytest.skip(f"Scope not granted on this shop: {scope}")

    return _requires


def read(call, scope: str):
    """Run a read, turning shop-setup limitations into a skip."""
    try:
        return call()
    except NotImplementedError as error:
        pytest.skip(f"{scope}: {error}")
    except Exception as error:
        message = str(error)

        if any(limit in message for limit in ENVIRONMENT_LIMITS):
            pytest.skip(f"{scope} not available on this shop: {message[:200]}")

        raise


# --------------------------------------------------------------------------- #
# Configuration — no network
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "shop",
    [
        "my-store",
        "my-store.myshopify.com",
        "https://my-store.myshopify.com",
        "https://my-store.myshopify.com/",
    ],
)
def test_configuration_normalises_shop(shop: str):
    configuration = ShopifyIntegrationConfiguration(
        shop=shop, client_id="id", client_secret="secret"
    )

    assert configuration.shop == "my-store"


def test_configuration_builds_urls():
    configuration = ShopifyIntegrationConfiguration(
        shop="my-store.myshopify.com",
        client_id="id",
        client_secret="secret",
        api_version="2026-07",
    )
    shopify = ShopifyIntegration(configuration)

    assert shopify.token_url == (
        "https://my-store.myshopify.com/admin/oauth/access_token"
    )
    assert shopify.graphql_url == (
        "https://my-store.myshopify.com/admin/api/2026-07/graphql.json"
    )
    assert shopify.access_scopes_url == (
        "https://my-store.myshopify.com/admin/oauth/access_scopes.json"
    )


def test_paginate_rejects_undeclared_variable():
    """_paginate must refuse a variable whose GraphQL type is not declared."""
    shopify = ShopifyIntegration(
        ShopifyIntegrationConfiguration(
            shop="my-store", client_id="id", client_secret="secret"
        )
    )

    with pytest.raises(ValueError, match="query"):
        shopify._paginate("orders", "id", variables={"query": "status:open"})


# --------------------------------------------------------------------------- #
# Scope coverage
# --------------------------------------------------------------------------- #


def test_scope_method_map_names_real_methods():
    """Every scope in the map must point at a method that exists."""
    missing = [
        f"{scope} -> {method}"
        for scope, method in SCOPE_METHOD_MAP.items()
        if not callable(getattr(ShopifyIntegration, method, None))
    ]

    assert not missing, f"SCOPE_METHOD_MAP names methods that do not exist: {missing}"


def test_scopes_without_query_are_mapped():
    """Every unsupported scope must still appear in the scope map."""
    unmapped = sorted(SCOPES_WITHOUT_QUERY - set(SCOPE_METHOD_MAP))

    assert not unmapped, f"Scopes missing from SCOPE_METHOD_MAP: {unmapped}"


@pytest.mark.parametrize("scope", sorted(SCOPES_WITHOUT_QUERY))
def test_unsupported_scope_raises_not_implemented(scope: str):
    """Scopes with no Admin GraphQL read surface must say so explicitly."""
    shopify = ShopifyIntegration(
        ShopifyIntegrationConfiguration(
            shop="my-store", client_id="id", client_secret="secret"
        )
    )
    method = getattr(shopify, SCOPE_METHOD_MAP[scope])

    with pytest.raises(NotImplementedError, match=scope):
        method()


def test_every_granted_scope_has_a_method(granted_scopes: set[str]):
    """The shop must not grant a scope this integration cannot account for."""
    uncovered = sorted(granted_scopes - set(SCOPE_METHOD_MAP))

    logger.info(f"Granted scopes: {len(granted_scopes)}")
    assert not uncovered, f"Granted scopes with no integration method: {uncovered}"


# --------------------------------------------------------------------------- #
# Permissions and identity — no scope required
# --------------------------------------------------------------------------- #


def test_get_access_scopes(integration: ShopifyIntegration):
    scopes = integration.get_access_scopes()

    assert isinstance(scopes, list), f"Expected list, got {type(scopes)}"
    assert scopes, "Expected at least one granted scope"
    assert all("handle" in scope for scope in scopes)
    logger.info(f"Granted scopes: {len(scopes)}")


def test_get_app_installation(integration: ShopifyIntegration):
    installation = integration.get_app_installation()

    assert installation.get("id"), f"Expected an installation id, got {installation}"
    assert installation.get("app"), "Expected the app object"
    assert installation.get("accessScopes"), "Expected the granted access scopes"
    logger.info(f"App: {installation['app'].get('title')}")


def test_get_shop(integration: ShopifyIntegration):
    shop = integration.get_shop()

    assert shop.get("name"), f"Expected a shop name, got {shop}"
    assert shop.get("myshopifyDomain", "").endswith(".myshopify.com")
    logger.info(f"Shop: {shop['name']} ({shop['myshopifyDomain']})")


def test_access_scopes_agree_with_app_installation(integration: ShopifyIntegration):
    """The REST and GraphQL views of the granted scopes must match."""
    rest = {scope["handle"] for scope in integration.get_access_scopes()}
    graphql = {
        scope["handle"] for scope in integration.get_app_installation()["accessScopes"]
    }

    assert rest == graphql, (
        f"Scope sources disagree — REST only: {sorted(rest - graphql)}, "
        f"GraphQL only: {sorted(graphql - rest)}"
    )


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #


def test_get_products(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_products")
    products = read(
        lambda: integration.get_products(page_size=3, max_pages=1), "read_products"
    )

    assert isinstance(products, list)
    if products:
        assert products[0].get("id", "").startswith("gid://shopify/Product/")
        assert "variants" in products[0]
        logger.info(f"Product[0]: {products[0]['title']}")


def test_get_products_honours_page_size(
    integration: ShopifyIntegration, requires_scope
):
    """page_size and max_pages must bound how much a read returns."""
    requires_scope("read_products")
    products = read(
        lambda: integration.get_products(page_size=1, max_pages=1), "read_products"
    )

    assert len(products) <= 1, f"Expected at most 1 product, got {len(products)}"


def test_get_product_listings(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_product_listings")
    listings = read(
        lambda: integration.get_product_listings(page_size=3, max_pages=1),
        "read_product_listings",
    )

    assert isinstance(listings, list)
    if listings:
        assert "products" in listings[0]
        logger.info(f"Publications: {len(listings)}")


# --------------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------------- #


def test_get_customers(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_customers")
    customers = read(
        lambda: integration.get_customers(page_size=3, max_pages=1), "read_customers"
    )

    assert isinstance(customers, list)
    if customers:
        assert customers[0].get("id", "").startswith("gid://shopify/Customer/")
        assert "amountSpent" in customers[0]
        logger.info(f"Customers fetched: {len(customers)}")


def test_get_customer_events(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_customer_events")
    events = read(
        lambda: integration.get_customer_events(page_size=3, max_pages=1),
        "read_customer_events",
    )

    assert isinstance(events, list)
    if events:
        assert events[0].get("id")
        assert "createdAt" in events[0]


def test_get_customer_payment_methods(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_customer_payment_methods")
    requires_scope("read_customers")

    customers = integration.get_customers(page_size=1, max_pages=1)
    if not customers:
        pytest.skip("Shop has no customers")

    methods = read(
        lambda: integration.get_customer_payment_methods(customers[0]["id"]),
        "read_customer_payment_methods",
    )

    assert isinstance(methods, list)


def test_get_customer_merge_preview(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_customer_merge")
    requires_scope("read_customers")

    customers = integration.get_customers(page_size=2, max_pages=1)
    if len(customers) < 2:
        pytest.skip("Shop has fewer than two customers")

    preview = read(
        lambda: integration.get_customer_merge_preview(
            customers[0]["id"], customers[1]["id"]
        ),
        "read_customer_merge",
    )

    assert "defaultFields" in preview, f"Expected defaultFields, got {preview}"


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #


def test_get_orders(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_orders")
    orders = read(
        lambda: integration.get_orders(page_size=3, max_pages=1), "read_orders"
    )

    assert isinstance(orders, list)
    if orders:
        assert orders[0].get("name", "").startswith("#")
        assert "lineItems" in orders[0]
        assert "currentTotalPriceSet" in orders[0]
        logger.info(f"Order[0]: {orders[0]['name']}")


def test_get_orders_returns_custom_attributes(
    integration: ShopifyIntegration, requires_scope
):
    """Line items must carry customAttributes — the personalization input."""
    requires_scope("read_orders")
    orders = read(
        lambda: integration.get_orders(page_size=3, max_pages=1), "read_orders"
    )

    if not orders:
        pytest.skip("Shop has no orders")

    assert "customAttributes" in orders[0], (
        "Order is missing customAttributes — personalization would be lost"
    )

    line_items = (orders[0].get("lineItems") or {}).get("nodes") or []
    if not line_items:
        pytest.skip("First order has no line items")

    assert "customAttributes" in line_items[0], (
        "Line item is missing customAttributes — personalization would be lost"
    )


def test_get_order_by_name_and_gid_agree(
    integration: ShopifyIntegration, requires_scope
):
    """Both lookup forms must resolve to the same order."""
    requires_scope("read_orders")
    orders = read(
        lambda: integration.get_orders(page_size=1, max_pages=1), "read_orders"
    )

    if not orders:
        pytest.skip("Shop has no orders")

    expected = orders[0]

    by_gid = integration.get_order(expected["id"])
    by_name = integration.get_order(expected["name"])
    by_bare_name = integration.get_order(expected["name"].lstrip("#"))

    assert by_gid is not None, f"GID lookup failed for {expected['id']}"
    assert by_gid["id"] == expected["id"]
    assert by_name is not None, f"Name lookup failed for {expected['name']}"
    assert by_name["id"] == expected["id"]
    assert by_bare_name is not None, "Lookup without the leading '#' failed"
    assert by_bare_name["id"] == expected["id"]
    logger.info(f"Resolved {expected['name']} through both lookup forms")


def test_get_order_unknown_name_returns_none(
    integration: ShopifyIntegration, requires_scope
):
    """An order number that does not exist must return None, not raise."""
    requires_scope("read_orders")

    assert integration.get_order("#99999999") is None


def test_get_orders_applies_search_query(
    integration: ShopifyIntegration, requires_scope
):
    """A search_query must reach Shopify and constrain the result."""
    requires_scope("read_orders")
    paid = read(
        lambda: integration.get_orders(
            search_query="financial_status:paid", page_size=5, max_pages=1
        ),
        "read_orders",
    )

    assert isinstance(paid, list)
    for order in paid:
        assert order["displayFinancialStatus"] in {
            "PAID",
            "PARTIALLY_REFUNDED",
            "REFUNDED",
        }, f"Unexpected status for a paid query: {order['displayFinancialStatus']}"


def test_get_orders_sorts_by_created_at_descending(
    integration: ShopifyIntegration, requires_scope
):
    requires_scope("read_orders")
    orders = read(
        lambda: integration.get_orders(page_size=5, max_pages=1), "read_orders"
    )

    if len(orders) < 2:
        pytest.skip("Shop has fewer than two orders")

    created = [order["createdAt"] for order in orders]
    assert created == sorted(created, reverse=True), (
        f"Expected newest-first ordering, got {created}"
    )


def test_get_all_orders(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_all_orders")
    orders = read(
        lambda: integration.get_all_orders(page_size=3, max_pages=1), "read_all_orders"
    )

    assert isinstance(orders, list)


def test_get_draft_orders(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_draft_orders")
    drafts = read(
        lambda: integration.get_draft_orders(page_size=3, max_pages=1),
        "read_draft_orders",
    )

    assert isinstance(drafts, list)
    if drafts:
        assert drafts[0].get("id", "").startswith("gid://shopify/DraftOrder/")


def test_get_abandoned_checkouts(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_checkouts")
    checkouts = read(
        lambda: integration.get_abandoned_checkouts(page_size=3, max_pages=1),
        "read_checkouts",
    )

    assert isinstance(checkouts, list)
    if checkouts:
        assert "abandonedCheckoutUrl" in checkouts[0]


def test_get_order_edit_session_unknown_id(
    integration: ShopifyIntegration, requires_scope
):
    """An unknown session id must resolve to None, not raise."""
    requires_scope("read_order_edits")
    session = read(
        lambda: integration.get_order_edit_session("gid://shopify/OrderEditSession/1"),
        "read_order_edits",
    )

    assert session is None


# --------------------------------------------------------------------------- #
# Fulfilment
# --------------------------------------------------------------------------- #


def test_get_assigned_fulfillment_orders(
    integration: ShopifyIntegration, requires_scope
):
    requires_scope("read_assigned_fulfillment_orders")
    fulfillment_orders = read(
        lambda: integration.get_assigned_fulfillment_orders(page_size=3, max_pages=1),
        "read_assigned_fulfillment_orders",
    )

    assert isinstance(fulfillment_orders, list)


def test_get_fulfillment_services(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_custom_fulfillment_services")
    services = read(
        integration.get_fulfillment_services, "read_custom_fulfillment_services"
    )

    assert isinstance(services, list)
    if services:
        assert services[0].get("serviceName")
        assert services[0].get("type") in {"MANUAL", "THIRD_PARTY", "GIFT_CARD"}


def test_get_return_reason_definitions(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_returns")
    reasons = read(
        lambda: integration.get_return_reason_definitions(page_size=5, max_pages=1),
        "read_returns",
    )

    assert isinstance(reasons, list)
    if reasons:
        assert reasons[0].get("handle")


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #


def test_get_locations(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_locations")
    locations = read(
        lambda: integration.get_locations(page_size=5, max_pages=1), "read_locations"
    )

    assert isinstance(locations, list)
    assert locations, "Every shop has at least one location"
    assert locations[0].get("id", "").startswith("gid://shopify/Location/")
    logger.info(f"Locations: {[location['name'] for location in locations]}")


def test_get_inventory_shipments(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_inventory_shipments")
    shipments = read(
        lambda: integration.get_inventory_shipments(page_size=3, max_pages=1),
        "read_inventory_shipments",
    )

    assert isinstance(shipments, list)


def test_get_inventory_shipment_received_items(
    integration: ShopifyIntegration, requires_scope
):
    requires_scope("read_inventory_shipments_received_items")
    shipments = read(
        lambda: integration.get_inventory_shipment_received_items(
            page_size=3, max_pages=1
        ),
        "read_inventory_shipments_received_items",
    )

    assert isinstance(shipments, list)
    if shipments:
        assert "lineItems" in shipments[0]


# --------------------------------------------------------------------------- #
# Pricing and discounts
# --------------------------------------------------------------------------- #


def test_get_discounts(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_discounts")
    discounts = read(
        lambda: integration.get_discounts(page_size=3, max_pages=1), "read_discounts"
    )

    assert isinstance(discounts, list)
    if discounts:
        # discountNodes returns the concrete node type — DiscountCodeNode for
        # code discounts, DiscountAutomaticNode for automatic ones.
        assert discounts[0].get("id", "").startswith("gid://shopify/Discount")
        assert discounts[0].get("discount", {}).get("__typename")


def test_get_price_rules(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_price_rules")
    rules = read(
        lambda: integration.get_price_rules(page_size=3, max_pages=1),
        "read_price_rules",
    )

    assert isinstance(rules, list)


def test_get_discount_allocator_functions(
    integration: ShopifyIntegration, requires_scope
):
    requires_scope("read_discounts_allocator_functions")
    functions = read(
        lambda: integration.get_discount_allocator_functions(page_size=5, max_pages=1),
        "read_discounts_allocator_functions",
    )

    assert isinstance(functions, list)
    for function in functions:
        assert function["apiType"] == "discounts_allocator"


# --------------------------------------------------------------------------- #
# B2B and sales channels
# --------------------------------------------------------------------------- #


def test_get_companies(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_companies")
    companies = read(
        lambda: integration.get_companies(page_size=3, max_pages=1), "read_companies"
    )

    assert isinstance(companies, list)
    if companies:
        assert companies[0].get("id", "").startswith("gid://shopify/Company/")


def test_get_channels(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_channels")
    channels = read(
        lambda: integration.get_channels(page_size=5, max_pages=1), "read_channels"
    )

    assert isinstance(channels, list)


def test_get_publications(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_publications")
    publications = read(
        lambda: integration.get_publications(page_size=5, max_pages=1),
        "read_publications",
    )

    assert isinstance(publications, list)
    if publications:
        assert publications[0].get("id", "").startswith("gid://shopify/Publication/")


def test_get_app_installations(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_apps")
    installations = read(
        lambda: integration.get_app_installations(page_size=3, max_pages=1),
        "read_apps",
    )

    assert isinstance(installations, list)
    if installations:
        assert installations[0].get("app", {}).get("title")


def test_get_shop_locales(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_locales")
    locales = read(integration.get_shop_locales, "read_locales")

    assert isinstance(locales, list)
    assert locales, "Every shop has at least one locale"
    assert any(locale["primary"] for locale in locales), "Expected a primary locale"
    logger.info(f"Locales: {[locale['locale'] for locale in locales]}")


# --------------------------------------------------------------------------- #
# Shipping
# --------------------------------------------------------------------------- #


def test_get_delivery_profiles(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_shipping")
    profiles = read(
        lambda: integration.get_delivery_profiles(page_size=3, max_pages=1),
        "read_shipping",
    )

    assert isinstance(profiles, list)
    assert profiles, "Every shop has a default delivery profile"
    assert any(profile["default"] for profile in profiles)


# --------------------------------------------------------------------------- #
# Checkout customizations
# --------------------------------------------------------------------------- #


def test_get_cart_transforms(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_cart_transforms")
    transforms = read(
        lambda: integration.get_cart_transforms(page_size=5, max_pages=1),
        "read_cart_transforms",
    )

    assert isinstance(transforms, list)


def test_get_all_cart_transforms(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_all_cart_transforms")
    transforms = read(
        lambda: integration.get_all_cart_transforms(page_size=5, max_pages=1),
        "read_all_cart_transforms",
    )

    assert isinstance(transforms, list)


def test_get_delivery_customizations(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_delivery_customizations")
    customizations = read(
        lambda: integration.get_delivery_customizations(page_size=5, max_pages=1),
        "read_delivery_customizations",
    )

    assert isinstance(customizations, list)


def test_get_payment_customizations(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_payment_customizations")
    customizations = read(
        lambda: integration.get_payment_customizations(page_size=5, max_pages=1),
        "read_payment_customizations",
    )

    assert isinstance(customizations, list)


def test_get_validations(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_validations")
    validations = read(
        lambda: integration.get_validations(page_size=5, max_pages=1),
        "read_validations",
    )

    assert isinstance(validations, list)


def test_get_checkout_and_accounts_configurations(
    integration: ShopifyIntegration, requires_scope
):
    requires_scope("read_checkout_and_accounts_configurations")
    configurations = read(
        lambda: integration.get_checkout_and_accounts_configurations(
            page_size=5, max_pages=1
        ),
        "read_checkout_and_accounts_configurations",
    )

    assert isinstance(configurations, list)
    if configurations:
        assert "isPublished" in configurations[0]


# --------------------------------------------------------------------------- #
# Point of sale
# --------------------------------------------------------------------------- #


def test_get_cash_tracking_sessions(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_cash_tracking")
    sessions = read(
        lambda: integration.get_cash_tracking_sessions(page_size=3, max_pages=1),
        "read_cash_tracking",
    )

    assert isinstance(sessions, list)


# --------------------------------------------------------------------------- #
# Shopify Payments
# --------------------------------------------------------------------------- #


def test_get_shopify_payments_account(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_shopify_payments_accounts")
    account = read(
        integration.get_shopify_payments_account, "read_shopify_payments_accounts"
    )

    if account is None:
        pytest.skip("Shopify Payments is not enabled on this shop")

    assert account.get("id")
    assert "balance" in account
    logger.info(f"Shopify Payments currency: {account.get('defaultCurrency')}")


def test_get_shopify_payments_bank_accounts(
    integration: ShopifyIntegration, requires_scope
):
    requires_scope("read_shopify_payments_bank_accounts")
    accounts = read(
        lambda: integration.get_shopify_payments_bank_accounts(page_size=5),
        "read_shopify_payments_bank_accounts",
    )

    assert isinstance(accounts, list)
    for account in accounts:
        assert account.get("status")


def test_get_shopify_payments_payouts(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_shopify_payments_payouts")
    payouts = read(
        lambda: integration.get_shopify_payments_payouts(page_size=5),
        "read_shopify_payments_payouts",
    )

    assert isinstance(payouts, list)
    if payouts:
        assert payouts[0].get("net", {}).get("currencyCode")
        logger.info(f"Payouts fetched: {len(payouts)}")


def test_get_shopify_payments_disputes(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_shopify_payments_disputes")
    disputes = read(
        lambda: integration.get_shopify_payments_disputes(page_size=3, max_pages=1),
        "read_shopify_payments_disputes",
    )

    assert isinstance(disputes, list)


# --------------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------------- #


def test_run_shopifyql_query(integration: ShopifyIntegration, requires_scope):
    requires_scope("read_analytics")
    response = read(
        lambda: integration.run_shopifyql_query(TOTAL_SALES_QUERY), "read_analytics"
    )

    assert not response.get("parseErrors"), (
        f"ShopifyQL parse errors: {response.get('parseErrors')}"
    )

    columns = [column["name"] for column in response["tableData"]["columns"]]
    assert columns == ["day", "total_sales"], f"Unexpected columns: {columns}"
    logger.info(f"ShopifyQL rows: {len(response['tableData']['rows'])}")


def test_run_shopifyql_query_reports_parse_errors(
    integration: ShopifyIntegration, requires_scope
):
    """An invalid statement must come back as parseErrors, not an exception."""
    requires_scope("read_analytics")
    response = read(
        lambda: integration.run_shopifyql_query("FROM nowhere SHOW nothing"),
        "read_analytics",
    )

    assert response.get("parseErrors"), (
        f"Expected parse errors for an invalid statement, got {response}"
    )


# --------------------------------------------------------------------------- #
# Customer Account API equivalents
# --------------------------------------------------------------------------- #


def test_get_customer_account_customers(
    integration: ShopifyIntegration, requires_scope
):
    requires_scope("customer_read_customers")
    customers = read(
        lambda: integration.get_customer_account_customers(page_size=3, max_pages=1),
        "customer_read_customers",
    )

    assert isinstance(customers, list)


def test_get_customer_account_orders(integration: ShopifyIntegration, requires_scope):
    requires_scope("customer_read_orders")
    orders = read(
        lambda: integration.get_customer_account_orders(page_size=3, max_pages=1),
        "customer_read_orders",
    )

    assert isinstance(orders, list)


def test_get_customer_account_companies(
    integration: ShopifyIntegration, requires_scope
):
    requires_scope("customer_read_companies")
    locations = read(
        lambda: integration.get_customer_account_companies(page_size=3, max_pages=1),
        "customer_read_companies",
    )

    assert isinstance(locations, list)
    if locations:
        assert locations[0].get("id", "").startswith("gid://shopify/CompanyLocation/")
