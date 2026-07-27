"""Shopify Admin GraphQL API integration.

Docs: https://shopify.dev/docs/api/admin-graphql/latest

Authentication uses the OAuth ``client_credentials`` grant, which exchanges a
Shopify app's Client ID / Client Secret for a short-lived Admin API access
token scoped to a single shop. The token is cached in memory and refreshed
automatically shortly before it expires.

There is one public read method per access scope granted to the app. Each
method's docstring names the scope it requires. Scopes whose data has no
Admin GraphQL query root field are still represented by a method, which raises
``NotImplementedError`` explaining where that data actually lives — so the
scope-to-method mapping stays complete and discoverable.

Call :meth:`ShopifyIntegration.get_access_scopes` to list the scopes actually
granted on the shop before relying on any of these methods.
"""

import json as json_module
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
from naas_abi_core import logger
from naas_abi_core.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)

# HTTP status codes worth retrying. Shopify returns 429 when the REST leaky
# bucket is empty and 5xx when a storefront/admin node is briefly unavailable.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Backoff sleeps (seconds) between retries, following the Fibonacci sequence up
# to the 5th number: 1, 1, 2, 3, 5. This gives 5 retries (6 attempts total)
# before the request is allowed to fail.
_FIBONACCI_BACKOFF_SECONDS = (1, 1, 2, 3, 5)

# Shopify signals GraphQL query-cost exhaustion with a 200 response whose
# ``errors[].extensions.code`` is THROTTLED — not with an HTTP status — so it
# has to be detected in the body and retried like a 429.
_THROTTLED_CODE = "THROTTLED"

# Refresh the client_credentials token this long before it actually expires, so
# a request is never sent with a token that lapses in flight.
_TOKEN_EXPIRY_MARGIN = timedelta(seconds=60)

# Every Shopify access scope this integration knows about, mapped to the method
# that reads its data. Methods listed under SCOPES_WITHOUT_QUERY raise
# NotImplementedError — the scope is real but the Admin GraphQL API has no
# query root field for it.
#
# This is the single source of truth for scope coverage:
# ShopifyIntegration_test.py asserts that every scope granted on the shop
# appears here and that every value names a real method.
SCOPE_METHOD_MAP: dict[str, str] = {
    # ----- catalogue
    "read_products": "get_products",
    "read_product_listings": "get_product_listings",
    # ----- customers
    "read_customers": "get_customers",
    "read_customer_events": "get_customer_events",
    "read_customer_payment_methods": "get_customer_payment_methods",
    "read_customer_merge": "get_customer_merge_preview",
    "read_customer_data_erasure": "get_customer_data_erasure",
    # ----- orders
    "read_orders": "get_orders",
    "read_all_orders": "get_all_orders",
    "read_draft_orders": "get_draft_orders",
    "read_checkouts": "get_abandoned_checkouts",
    "read_order_edits": "get_order_edit_session",
    # ----- fulfilment
    "read_assigned_fulfillment_orders": "get_assigned_fulfillment_orders",
    "read_custom_fulfillment_services": "get_fulfillment_services",
    "read_returns": "get_return_reason_definitions",
    # ----- inventory
    "read_locations": "get_locations",
    "read_inventory_shipments": "get_inventory_shipments",
    "read_inventory_shipments_received_items": (
        "get_inventory_shipment_received_items"
    ),
    # ----- pricing / discounts
    "read_discounts": "get_discounts",
    "read_price_rules": "get_price_rules",
    "read_discounts_allocator_functions": "get_discount_allocator_functions",
    # ----- b2b / channels
    "read_companies": "get_companies",
    "read_channels": "get_channels",
    "read_publications": "get_publications",
    "read_apps": "get_app_installations",
    "read_locales": "get_shop_locales",
    # ----- shipping
    "read_shipping": "get_delivery_profiles",
    # ----- customizations
    "read_cart_transforms": "get_cart_transforms",
    "read_all_cart_transforms": "get_all_cart_transforms",
    "read_delivery_customizations": "get_delivery_customizations",
    "read_payment_customizations": "get_payment_customizations",
    "read_validations": "get_validations",
    "read_checkout_and_accounts_configurations": (
        "get_checkout_and_accounts_configurations"
    ),
    # ----- point of sale
    "read_cash_tracking": "get_cash_tracking_sessions",
    # ----- shopify payments
    "read_shopify_payments_accounts": "get_shopify_payments_account",
    "read_shopify_payments_bank_accounts": "get_shopify_payments_bank_accounts",
    "read_shopify_payments_payouts": "get_shopify_payments_payouts",
    "read_shopify_payments_disputes": "get_shopify_payments_disputes",
    # ----- analytics
    "read_analytics": "run_shopifyql_query",
    "read_analytics_annotations": "get_analytics_annotations",
    "read_reports": "get_reports",
    # ----- customer account api equivalents
    "customer_read_customers": "get_customer_account_customers",
    "customer_read_orders": "get_customer_account_orders",
    "customer_read_companies": "get_customer_account_companies",
    # ----- no Admin GraphQL read surface
    "read_app_proxy": "get_app_proxy",
    "read_audit_events": "get_audit_events",
    "read_checkout_branding_settings": "get_checkout_branding_settings",
    "read_checkout_kit_enhanced_buyer_events": (
        "get_checkout_kit_enhanced_buyer_events"
    ),
    "read_custom_pixels": "get_custom_pixels",
    "read_discovery": "get_discovery",
}

# Scopes whose method raises NotImplementedError because the Admin GraphQL API
# exposes no query root field for them. Each method's docstring names the
# surface that actually serves the data.
SCOPES_WITHOUT_QUERY: frozenset[str] = frozenset(
    {
        "read_analytics_annotations",
        "read_app_proxy",
        "read_audit_events",
        "read_checkout_branding_settings",
        "read_checkout_kit_enhanced_buyer_events",
        "read_custom_pixels",
        "read_customer_data_erasure",
        "read_discovery",
        "read_reports",
    }
)


# --------------------------------------------------------------------------- #
# GraphQL selection sets
#
# Kept as module constants so the methods below stay readable. Each is the
# body of a `nodes { ... }` selection on the matching connection.
# --------------------------------------------------------------------------- #

_MONEY_BAG = """
    shopMoney { amount currencyCode }
    presentmentMoney { amount currencyCode }
"""

_MONEY_V2 = """
    amount
    currencyCode
"""

# Shopify Payments processing fees live on OrderTransaction.fees (type often
# distinguishes the card rate from the flat "Shopify fee"). Empty for gateways
# that are not Shopify Payments.
_ORDER_TRANSACTION_FIELDS = f"""
    id
    kind
    status
    gateway
    formattedGateway
    processedAt
    test
    amountSet {{ {_MONEY_BAG} }}
    fees {{
        id
        type
        rate
        rateName
        flatFeeName
        amount {{ {_MONEY_V2} }}
        flatFee {{ {_MONEY_V2} }}
        taxAmount {{ {_MONEY_V2} }}
    }}
"""

_PRODUCT_FIELDS = """
    id
    title
    handle
    description
    productType
    vendor
    status
    tags
    totalInventory
    createdAt
    updatedAt
    publishedAt
    variants(first: 100) {
        nodes {
            id
            title
            sku
            barcode
            price
            compareAtPrice
            inventoryQuantity
            availableForSale
        }
    }
"""

_CUSTOMER_FIELDS = """
    id
    displayName
    firstName
    lastName
    email
    phone
    note
    tags
    state
    verifiedEmail
    numberOfOrders
    createdAt
    updatedAt
    amountSpent { amount currencyCode }
    defaultAddress { address1 address2 city province country zip }
"""

_ORDER_FIELDS = f"""
    id
    name
    email
    phone
    note
    tags
    createdAt
    updatedAt
    processedAt
    cancelledAt
    closedAt
    confirmed
    test
    displayFinancialStatus
    displayFulfillmentStatus
    customAttributes {{ key value }}
    currentTotalPriceSet {{ {_MONEY_BAG} }}
    currentSubtotalPriceSet {{ {_MONEY_BAG} }}
    totalPriceSet {{ {_MONEY_BAG} }}
    totalShippingPriceSet {{ {_MONEY_BAG} }}
    totalTaxSet {{ {_MONEY_BAG} }}
    totalRefundedSet {{ {_MONEY_BAG} }}
    currentTotalAdditionalFeesSet {{ {_MONEY_BAG} }}
    originalTotalAdditionalFeesSet {{ {_MONEY_BAG} }}
    additionalFees {{
        id
        name
        price {{ {_MONEY_BAG} }}
    }}
    transactions {{
        {_ORDER_TRANSACTION_FIELDS}
    }}
    customer {{ id displayName email }}
    shippingAddress {{ address1 address2 city province country zip }}
    lineItems(first: 100) {{
        nodes {{
            id
            name
            title
            quantity
            sku
            vendor
            # Line-item properties carry the buyer's personalization input
            # (engraving text, per-side messages, chosen model). Keys are
            # merchant-defined and localized per storefront language, so they
            # must never be hardcoded downstream.
            customAttributes {{ key value }}
            originalUnitPriceSet {{ {_MONEY_BAG} }}
            discountedTotalSet {{ {_MONEY_BAG} }}
            product {{ id title handle }}
            variant {{ id title sku }}
        }}
    }}
"""

_DRAFT_ORDER_FIELDS = f"""
    id
    name
    status
    email
    note2
    tags
    invoiceUrl
    createdAt
    updatedAt
    completedAt
    totalPriceSet {{ {_MONEY_BAG} }}
    subtotalPriceSet {{ {_MONEY_BAG} }}
    customer {{ id displayName email }}
    lineItems(first: 100) {{
        nodes {{
            id
            name
            title
            quantity
            sku
            originalUnitPriceSet {{ {_MONEY_BAG} }}
        }}
    }}
"""

_ABANDONED_CHECKOUT_FIELDS = f"""
    id
    name
    abandonedCheckoutUrl
    createdAt
    updatedAt
    completedAt
    note
    taxesIncluded
    totalPriceSet {{ {_MONEY_BAG} }}
    subtotalPriceSet {{ {_MONEY_BAG} }}
    customer {{ id displayName email }}
    lineItems(first: 100) {{
        nodes {{
            id
            title
            quantity
            sku
            originalUnitPriceSet {{ {_MONEY_BAG} }}
        }}
    }}
"""

_COMPANY_FIELDS = """
    id
    name
    externalId
    note
    lifetimeDuration
    customerSince
    createdAt
    updatedAt
    contactCount
    locationsCount { count precision }
    ordersCount { count precision }
    totalSpent { amount currencyCode }
"""

_COMPANY_LOCATION_FIELDS = """
    id
    name
    externalId
    createdAt
    updatedAt
    company { id name }
    billingAddress { address1 address2 city province country zip }
    shippingAddress { address1 address2 city province country zip }
"""

_LOCATION_FIELDS = """
    id
    name
    isActive
    legacyResourceId
    fulfillsOnlineOrders
    hasActiveInventory
    shipsInventory
    isFulfillmentService
    createdAt
    updatedAt
    address { address1 address2 city province country zip phone }
"""

_DISCOUNT_NODE_FIELDS = """
    id
    discount {
        __typename
        ... on DiscountCodeBasic {
            title status summary startsAt endsAt usageLimit asyncUsageCount
        }
        ... on DiscountCodeBxgy {
            title status summary startsAt endsAt usageLimit asyncUsageCount
        }
        ... on DiscountCodeFreeShipping {
            title status summary startsAt endsAt usageLimit asyncUsageCount
        }
        ... on DiscountAutomaticBasic { title status summary startsAt endsAt }
        ... on DiscountAutomaticBxgy { title status summary startsAt endsAt }
        ... on DiscountAutomaticFreeShipping {
            title status summary startsAt endsAt
        }
        ... on DiscountAutomaticApp { title status startsAt endsAt }
        ... on DiscountCodeApp {
            title status startsAt endsAt usageLimit asyncUsageCount
        }
    }
"""

_FULFILLMENT_ORDER_FIELDS = """
    id
    status
    requestStatus
    createdAt
    updatedAt
    fulfillAt
    order { id name }
    assignedLocation { name address1 city province countryCode zip }
    lineItems(first: 100) {
        nodes {
            id
            totalQuantity
            remainingQuantity
            sku
            productTitle
        }
    }
"""

_INVENTORY_SHIPMENT_FIELDS = """
    id
    name
    status
    barcode
    dateCreated
    dateShipped
    dateReceived
    lineItemTotalQuantity
    totalAcceptedQuantity
    totalReceivedQuantity
    totalRejectedQuantity
"""

_EVENT_FIELDS = """
    id
    action
    message
    createdAt
    criticalAlert
    appTitle
    attributeToApp
    attributeToUser
"""

_DISPUTE_FIELDS = """
    id
    status
    type
    reasonDetails { reason networkReasonCode }
    amount { amount currencyCode }
    evidenceDueBy
    evidenceSentOn
    finalizedOn
    initiatedAt
    legacyResourceId
    order { id name }
"""

_PAYOUT_FIELDS = """
    id
    status
    transactionType
    issuedAt
    legacyResourceId
    net { amount currencyCode }
    gross { amount currencyCode }
    summary {
        adjustmentsFee { amount currencyCode }
        adjustmentsGross { amount currencyCode }
        chargesFee { amount currencyCode }
        chargesGross { amount currencyCode }
        refundsFee { amount currencyCode }
        refundsFeeGross { amount currencyCode }
        reservedFundsFee { amount currencyCode }
        reservedFundsGross { amount currencyCode }
        retriedPayoutsFee { amount currencyCode }
        retriedPayoutsGross { amount currencyCode }
    }
"""


@dataclass
class ShopifyIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for the Shopify Admin GraphQL integration.

    Attributes:
        shop (str): Shop identifier. Accepts either the subdomain ("my-store")
            or the full domain ("my-store.myshopify.com").
        client_id (str): Shopify app Client ID (API key).
        client_secret (str): Shopify app Client Secret.
        api_version (str): Admin API version, e.g. "2026-07".
        page_size (int): Default number of nodes fetched per paginated request.
    """

    shop: str
    client_id: str
    client_secret: str
    api_version: str = "2026-07"
    page_size: int = 50

    def __post_init__(self) -> None:
        # Accept "my-store", "my-store.myshopify.com" or a full URL.
        self.shop = (
            self.shop.replace("https://", "")
            .replace("http://", "")
            .replace(".myshopify.com", "")
            .rstrip("/")
            .strip()
        )


class ShopifyIntegration(Integration):
    """Shopify Admin GraphQL API integration — read-only, one method per scope."""

    __configuration: ShopifyIntegrationConfiguration

    def __init__(self, configuration: ShopifyIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        self.__access_token: str | None = None
        self.__token_expires_at: datetime | None = None

        shop_domain = f"https://{configuration.shop}.myshopify.com"
        self.token_url = f"{shop_domain}/admin/oauth/access_token"
        self.access_scopes_url = f"{shop_domain}/admin/oauth/access_scopes.json"
        self.graphql_url = (
            f"{shop_domain}/admin/api/{configuration.api_version}/graphql.json"
        )

    # ------------------------------------------------------------------ auth

    def _get_access_token(self) -> str:
        """Return a valid Admin API access token, refreshing it when needed.

        Exchanges the app's Client ID / Client Secret for a short-lived token
        via the OAuth ``client_credentials`` grant and caches it in memory
        until shortly before it expires.

        Raises:
            IntegrationConnectionError: If authentication fails.
        """
        now = datetime.now(UTC)
        if (
            self.__access_token
            and self.__token_expires_at
            and now < self.__token_expires_at
        ):
            return self.__access_token

        try:
            response = requests.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.__configuration.client_id,
                    "client_secret": self.__configuration.client_secret,
                },
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(
                f"Shopify authentication request failed: {e!s}"
            ) from e

        if not response.ok:
            raise IntegrationConnectionError(
                f"Shopify authentication failed: "
                f"{response.status_code} {response.reason} — {response.text}"
            )

        result = response.json()
        access_token = result.get("access_token")
        if not access_token:
            raise IntegrationConnectionError(
                f"Shopify did not return an access token: {result}"
            )

        # `expires_in` is seconds; Shopify currently issues 24h tokens but the
        # value is authoritative, so honour it rather than hardcoding a TTL.
        expires_in = int(result.get("expires_in", 86400))
        self.__access_token = access_token
        self.__token_expires_at = (
            now + timedelta(seconds=expires_in) - _TOKEN_EXPIRY_MARGIN
        )
        return access_token

    # --------------------------------------------------------------- requests

    def _execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query against the Shopify Admin API.

        Retries transient failures (429/5xx, and 200-with-THROTTLED responses)
        with Fibonacci backoff before giving up.

        Args:
            query (str): The GraphQL document to execute.
            variables (dict, optional): Variables for the query.

        Returns:
            dict: The ``data`` object of the response.

        Raises:
            IntegrationConnectionError: If the request fails or the API returns
                GraphQL errors.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self._get_access_token(),
        }

        last_error: IntegrationConnectionError | None = None
        for attempt, sleep_seconds in enumerate((*_FIBONACCI_BACKOFF_SECONDS, None)):
            retryable = False
            try:
                response = requests.post(
                    self.graphql_url,
                    headers=headers,
                    json={"query": query, "variables": variables or {}},
                    timeout=60,
                )
            except requests.exceptions.RequestException as e:
                last_error = IntegrationConnectionError(
                    f"Shopify API request failed: {e!s}"
                )
                retryable = True
            else:
                if response.ok:
                    result = response.json()
                    errors = result.get("errors")
                    if not errors:
                        if "data" not in result:
                            raise IntegrationConnectionError(
                                "Unexpected Shopify response: "
                                + json_module.dumps(result)[:2000]
                            )
                        return result["data"]

                    detail = json_module.dumps(errors, ensure_ascii=False)
                    last_error = IntegrationConnectionError(
                        f"Shopify GraphQL errors: {detail}"
                    )
                    # A THROTTLED error means the query-cost bucket is empty;
                    # everything else (bad field, missing scope) is permanent.
                    retryable = any(
                        (e.get("extensions") or {}).get("code") == _THROTTLED_CODE
                        for e in errors
                        if isinstance(e, dict)
                    )
                    if not retryable:
                        raise last_error
                else:
                    try:
                        detail = json_module.dumps(response.json(), ensure_ascii=False)
                    except ValueError:
                        detail = response.text
                    last_error = IntegrationConnectionError(
                        f"Shopify API {response.status_code} {response.reason} "
                        f"for {self.graphql_url} — {detail}"
                    )
                    retryable = response.status_code in _RETRYABLE_STATUS_CODES
                    if not retryable:
                        raise last_error

            # `sleep_seconds is None` marks the final attempt — no retries left.
            if sleep_seconds is None or not retryable:
                break
            logger.warning(
                "Shopify request failed (attempt %d/%d); retrying in %ds — %s",
                attempt + 1,
                len(_FIBONACCI_BACKOFF_SECONDS) + 1,
                sleep_seconds,
                last_error,
            )
            time.sleep(sleep_seconds)

        raise last_error  # type: ignore[misc]

    def _paginate(
        self,
        root_field: str,
        selection: str,
        variables: dict[str, Any] | None = None,
        variable_types: dict[str, str] | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """Follow every cursor of a Shopify GraphQL connection.

        Builds a query of the form::

            query Paginate($first: Int!, $after: String, ...) {
                <root_field>(first: $first, after: $after, ...) {
                    nodes { <selection> }
                    pageInfo { hasNextPage endCursor }
                }
            }

        Args:
            root_field (str): Connection field on the Query root, e.g. "orders".
            selection (str): Field selection applied to each node.
            variables (dict, optional): Extra arguments forwarded to the field
                (e.g. ``{"query": "financial_status:paid"}``).
            variable_types (dict, optional): GraphQL type of each extra
                variable (e.g. ``{"query": "String"}``). Required for every key
                in ``variables``.
            page_size (int, optional): Nodes per page. Defaults to the
                configured ``page_size``.
            max_pages (int, optional): Stop after this many pages. ``None``
                exhausts the connection.

        Returns:
            list[dict]: Every node across all fetched pages.
        """
        variables = dict(variables or {})
        variable_types = dict(variable_types or {})

        # Drop unset optional arguments so Shopify applies its own defaults
        # rather than receiving explicit nulls it may reject.
        variables = {k: v for k, v in variables.items() if v is not None}

        missing = set(variables) - set(variable_types)
        if missing:
            raise ValueError(
                f"Missing GraphQL type declaration for variables: {sorted(missing)}"
            )

        declarations = ["$first: Int!", "$after: String"]
        arguments = ["first: $first", "after: $after"]
        for name in variables:
            declarations.append(f"${name}: {variable_types[name]}")
            arguments.append(f"{name}: ${name}")

        query = f"""
        query Paginate({", ".join(declarations)}) {{
            {root_field}({", ".join(arguments)}) {{
                nodes {{ {selection} }}
                pageInfo {{ hasNextPage endCursor }}
            }}
        }}
        """

        nodes: list[dict[str, Any]] = []
        cursor: str | None = None
        page = 0

        while True:
            data = self._execute(
                query,
                variables={
                    **variables,
                    "first": page_size or self.__configuration.page_size,
                    "after": cursor,
                },
            )
            connection = data[root_field]
            nodes.extend(connection.get("nodes") or [])

            page += 1
            if max_pages is not None and page >= max_pages:
                break

            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        logger.debug("Shopify %s: fetched %d node(s)", root_field, len(nodes))
        return nodes

    # ------------------------------------------------------------ permissions

    def get_access_scopes(self) -> list[dict[str, Any]]:
        """List the access scopes (permissions) granted to this app on the shop.

        Endpoint: GET /admin/oauth/access_scopes.json

        This endpoint requires no scope of its own — call it first to find out
        which of the methods below the current app is actually allowed to use.

        Returns:
            list[dict]: One entry per granted scope, each with a ``handle``.
        """
        try:
            response = requests.get(
                self.access_scopes_url,
                headers={"X-Shopify-Access-Token": self._get_access_token()},
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(
                f"Shopify access scopes request failed: {e!s}"
            ) from e

        if not response.ok:
            raise IntegrationConnectionError(
                f"Shopify access scopes request failed: "
                f"{response.status_code} {response.reason} — {response.text}"
            )
        return response.json().get("access_scopes", [])

    def get_app_installation(self) -> dict[str, Any]:
        """Get the current app installation, including its granted scopes.

        Query: currentAppInstallation

        Requires no scope. Complements :meth:`get_access_scopes` by also
        returning the app identity and its scope descriptions.

        Returns:
            dict: The ``currentAppInstallation`` object.
        """
        query = """
        query GetAppInstallation {
            currentAppInstallation {
                id
                accessScopes { handle description }
                app { id title handle apiKey }
            }
        }
        """
        return self._execute(query)["currentAppInstallation"]

    def get_shop(self) -> dict[str, Any]:
        """Get the shop's own profile.

        Query: shop

        Requires no scope — every Admin API token can read the shop object.

        Returns:
            dict: The ``shop`` object.
        """
        query = """
        query GetShop {
            shop {
                id
                name
                email
                myshopifyDomain
                url
                contactEmail
                currencyCode
                ianaTimezone
                weightUnit
                createdAt
                plan { displayName partnerDevelopment shopifyPlus }
                billingAddress { address1 city province country zip }
            }
        }
        """
        return self._execute(query)["shop"]

    # --------------------------------------------------------------- products

    def get_products(
        self,
        search_query: str | None = None,
        sort_key: str | None = None,
        reverse: bool = False,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List products, variants and their inventory.

        Scope: ``read_products``
        Query: products

        Args:
            search_query (str, optional): Shopify search syntax, e.g.
                "status:active", "vendor:Acme", "created_at:>=2026-01-01".
            sort_key (str, optional): A ``ProductSortKeys`` value, e.g. "TITLE",
                "CREATED_AT", "UPDATED_AT", "INVENTORY_TOTAL".
            reverse (bool): Reverse the sort order.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Product nodes.
        """
        return self._paginate(
            "products",
            _PRODUCT_FIELDS,
            variables={
                "query": search_query,
                "sortKey": sort_key,
                "reverse": reverse,
            },
            variable_types={
                "query": "String",
                "sortKey": "ProductSortKeys",
                "reverse": "Boolean",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_product_listings(
        self,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List each sales-channel publication together with its products.

        Scope: ``read_product_listings``
        Query: publications { products }

        This is the "product listings" view — which products are published to
        which sales channel — as opposed to :meth:`get_products`, which returns
        the catalogue itself.

        Args:
            page_size (int, optional): Publications per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Publication nodes, each with a ``products`` connection.
        """
        selection = """
            id
            autoPublish
            catalog { id title status }
            products(first: 100) {
                nodes { id title handle status vendor productType }
            }
        """
        return self._paginate(
            "publications",
            selection,
            page_size=page_size or 10,
            max_pages=max_pages,
        )

    # -------------------------------------------------------------- customers

    def get_customers(
        self,
        search_query: str | None = None,
        sort_key: str | None = None,
        reverse: bool = False,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List customers and their lifetime spend.

        Scope: ``read_customers``
        Query: customers

        Args:
            search_query (str, optional): Shopify search syntax, e.g.
                "country:France", "orders_count:>5", "email:*@acme.com".
            sort_key (str, optional): A ``CustomerSortKeys`` value, e.g. "NAME",
                "CREATED_AT", "UPDATED_AT".
            reverse (bool): Reverse the sort order.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Customer nodes.
        """
        return self._paginate(
            "customers",
            _CUSTOMER_FIELDS,
            variables={
                "query": search_query,
                "sortKey": sort_key,
                "reverse": reverse,
            },
            variable_types={
                "query": "String",
                "sortKey": "CustomerSortKeys",
                "reverse": "Boolean",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_customer_payment_methods(
        self,
        customer_id: str,
        show_revoked: bool = False,
    ) -> list[dict[str, Any]]:
        """List a customer's stored payment methods.

        Scope: ``read_customer_payment_methods``
        Query: customer { paymentMethods }

        Args:
            customer_id (str): Customer GID, e.g.
                "gid://shopify/Customer/1234567890".
            show_revoked (bool): Include revoked payment methods.

        Returns:
            list[dict]: Payment-method nodes.
        """
        query = """
        query GetCustomerPaymentMethods(
            $id: ID!
            $showRevoked: Boolean
            $first: Int!
        ) {
            customer(id: $id) {
                id
                displayName
                paymentMethods(showRevoked: $showRevoked, first: $first) {
                    nodes {
                        id
                        revokedAt
                        revokedReason
                        instrument {
                            __typename
                            ... on CustomerCreditCard {
                                brand
                                lastDigits
                                expiryMonth
                                expiryYear
                                name
                                expiresSoon
                            }
                            ... on CustomerPaypalBillingAgreement {
                                paypalAccountEmail
                                inactive
                            }
                            ... on CustomerShopPayAgreement {
                                lastDigits
                                expiryMonth
                                expiryYear
                                inactive
                            }
                        }
                    }
                }
            }
        }
        """
        data = self._execute(
            query,
            variables={
                "id": customer_id,
                "showRevoked": show_revoked,
                "first": self.__configuration.page_size,
            },
        )
        customer = data.get("customer") or {}
        return (customer.get("paymentMethods") or {}).get("nodes") or []

    def get_customer_events(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List customer-related events from the shop's event log.

        Scope: ``read_customer_events``
        Query: events

        Args:
            search_query (str, optional): Shopify event search syntax. Defaults
                to ``"subject_type:Customer"`` so only customer events are
                returned.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Event nodes.
        """
        return self._paginate(
            "events",
            _EVENT_FIELDS,
            variables={"query": search_query or "subject_type:Customer"},
            variable_types={"query": "String"},
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_customer_merge_preview(
        self,
        customer_one_id: str,
        customer_two_id: str,
    ) -> dict[str, Any]:
        """Preview the result of merging two customers.

        Scope: ``read_customer_merge``
        Query: customerMergePreview

        Args:
            customer_one_id (str): GID of the first customer.
            customer_two_id (str): GID of the second customer.

        Returns:
            dict: The ``customerMergePreview`` object, including any blocking
            fields that prevent the merge.
        """
        query = """
        query CustomerMergePreview($one: ID!, $two: ID!) {
            customerMergePreview(customerOneId: $one, customerTwoId: $two) {
                resultingCustomerId
                alternateFields {
                    firstName
                    lastName
                    email { emailAddress }
                    phoneNumber { phoneNumber }
                }
                blockingFields {
                    note
                    tags
                }
                defaultFields {
                    displayName
                    firstName
                    lastName
                    note
                    tags
                    email { emailAddress }
                    phoneNumber { phoneNumber }
                    orderCount
                    draftOrderCount
                    giftCardCount
                    discountNodeCount
                    metafieldCount
                }
                customerMergeErrors {
                    message
                    errorFields
                }
            }
        }
        """
        return self._execute(
            query,
            variables={"one": customer_one_id, "two": customer_two_id},
        )["customerMergePreview"]

    def get_customer_merge_job_status(self, job_id: str) -> dict[str, Any]:
        """Get the status of a customer-merge job.

        Scope: ``read_customer_merge``
        Query: customerMergeJobStatus

        Args:
            job_id (str): GID of the merge job.

        Returns:
            dict: The ``customerMergeJobStatus`` object.
        """
        query = """
        query CustomerMergeJobStatus($jobId: ID!) {
            customerMergeJobStatus(jobId: $jobId) {
                jobId
                status
                resultingCustomerId
            }
        }
        """
        return self._execute(query, variables={"jobId": job_id})[
            "customerMergeJobStatus"
        ]

    # ----------------------------------------------------------------- orders

    def get_orders(
        self,
        search_query: str | None = None,
        sort_key: str | None = "CREATED_AT",
        reverse: bool = True,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List orders with their line items and money totals.

        Scope: ``read_orders``
        Query: orders

        Without ``read_all_orders`` this only reaches orders from the last 60
        days. Use :meth:`get_all_orders` for the full history.

        Args:
            search_query (str, optional): Shopify search syntax, e.g.
                "financial_status:paid AND fulfillment_status:unfulfilled",
                "created_at:>=2026-07-01".
            sort_key (str, optional): An ``OrderSortKeys`` value. Defaults to
                "CREATED_AT".
            reverse (bool): Newest first when True (the default).
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Order nodes.
        """
        return self._paginate(
            "orders",
            _ORDER_FIELDS,
            variables={
                "query": search_query,
                "sortKey": sort_key,
                "reverse": reverse,
            },
            variable_types={
                "query": "String",
                "sortKey": "OrderSortKeys",
                "reverse": "Boolean",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_order(self, order: str) -> dict[str, Any] | None:
        """Get a single order by GID or by order name.

        Scope: ``read_orders``
        Query: order / orders(query: "name:…")

        Accepts either form the merchant has to hand — the GID from a previous
        read, or the order number shown in the admin:

            "gid://shopify/Order/13872620372024"
            "#1429"
            "1429"

        The returned order carries ``customAttributes`` both on the order and
        on every line item; for personalized products the line-item attributes
        hold the buyer's input (engraving text, per-side messages, chosen
        model) under merchant-defined, per-language keys.

        Args:
            order (str): Order GID, or order name with or without the leading
                "#".

        Returns:
            dict | None: The order, or ``None`` when no order matches.
        """
        if order.startswith("gid://"):
            query = f"""
            query GetOrder($id: ID!) {{
                order(id: $id) {{ {_ORDER_FIELDS} }}
            }}
            """
            return self._execute(query, variables={"id": order})["order"]

        # Shopify indexes the order number without the leading "#", and
        # `name:` is an exact-match field on the orders connection.
        name = order.lstrip("#").strip()
        matches = self._paginate(
            "orders",
            _ORDER_FIELDS,
            variables={"query": f"name:{name}"},
            variable_types={"query": "String"},
            page_size=2,
            max_pages=1,
        )

        if not matches:
            return None

        if len(matches) > 1:
            logger.warning(
                "Order name %r matched %d orders; returning the first",
                order,
                len(matches),
            )

        return matches[0]

    def get_all_orders(
        self,
        search_query: str | None = None,
        sort_key: str | None = "CREATED_AT",
        reverse: bool = True,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List orders across the shop's full history, not just the last 60 days.

        Scope: ``read_all_orders`` (in addition to ``read_orders``)
        Query: orders

        ``read_all_orders`` is a protected scope granted by Shopify on request.
        It lifts the 60-day window that otherwise applies to :meth:`get_orders`;
        the query itself is identical, so the two differ only in reach.

        Args:
            search_query (str, optional): Shopify search syntax.
            sort_key (str, optional): An ``OrderSortKeys`` value.
            reverse (bool): Newest first when True (the default).
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Order nodes.
        """
        return self.get_orders(
            search_query=search_query,
            sort_key=sort_key,
            reverse=reverse,
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_draft_orders(
        self,
        search_query: str | None = None,
        sort_key: str | None = None,
        reverse: bool = True,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List draft orders (quotes and invoices not yet completed).

        Scope: ``read_draft_orders``
        Query: draftOrders

        Args:
            search_query (str, optional): Shopify search syntax, e.g.
                "status:open".
            sort_key (str, optional): A ``DraftOrderSortKeys`` value.
            reverse (bool): Newest first when True (the default).
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Draft-order nodes.
        """
        return self._paginate(
            "draftOrders",
            _DRAFT_ORDER_FIELDS,
            variables={
                "query": search_query,
                "sortKey": sort_key,
                "reverse": reverse,
            },
            variable_types={
                "query": "String",
                "sortKey": "DraftOrderSortKeys",
                "reverse": "Boolean",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_abandoned_checkouts(
        self,
        search_query: str | None = None,
        sort_key: str | None = None,
        reverse: bool = True,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List abandoned checkouts.

        Scope: ``read_checkouts``
        Query: abandonedCheckouts

        Args:
            search_query (str, optional): Shopify search syntax, e.g.
                "created_at:>=2026-07-01".
            sort_key (str, optional): An ``AbandonedCheckoutSortKeys`` value.
            reverse (bool): Newest first when True (the default).
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Abandoned-checkout nodes.
        """
        return self._paginate(
            "abandonedCheckouts",
            _ABANDONED_CHECKOUT_FIELDS,
            variables={
                "query": search_query,
                "sortKey": sort_key,
                "reverse": reverse,
            },
            variable_types={
                "query": "String",
                "sortKey": "AbandonedCheckoutSortKeys",
                "reverse": "Boolean",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_order_edit_session(self, order_edit_session_id: str) -> dict[str, Any]:
        """Get an order-edit session.

        Scope: ``read_order_edits``
        Query: orderEditSession

        ``OrderEditSession`` exposes only its ``id`` — the edits themselves are
        read from the edited order's ``events`` and line items via
        :meth:`get_orders`. The session is looked up here mainly to confirm it
        exists and that the app may read order edits.

        Args:
            order_edit_session_id (str): GID of the order-edit session, e.g.
                "gid://shopify/OrderEditSession/1234567890".

        Returns:
            dict: The ``orderEditSession`` object, or ``None`` if no session
            with that ID exists.
        """
        query = """
        query GetOrderEditSession($id: ID!) {
            orderEditSession(id: $id) {
                id
            }
        }
        """
        return self._execute(query, variables={"id": order_edit_session_id})[
            "orderEditSession"
        ]

    # ------------------------------------------------------------- fulfilment

    def get_assigned_fulfillment_orders(
        self,
        assignment_status: str | None = None,
        location_ids: list[str] | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List fulfillment orders assigned to this app's fulfillment service.

        Scope: ``read_assigned_fulfillment_orders``
        Query: assignedFulfillmentOrders

        Args:
            assignment_status (str, optional): A
                ``FulfillmentOrderAssignmentStatus`` value, e.g.
                "FULFILLMENT_REQUESTED", "CANCELLATION_REQUESTED".
            location_ids (list[str], optional): Restrict to these location GIDs.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Fulfillment-order nodes.
        """
        return self._paginate(
            "assignedFulfillmentOrders",
            _FULFILLMENT_ORDER_FIELDS,
            variables={
                "assignmentStatus": assignment_status,
                "locationIds": location_ids,
            },
            variable_types={
                "assignmentStatus": "FulfillmentOrderAssignmentStatus",
                "locationIds": "[ID!]",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_fulfillment_services(self) -> list[dict[str, Any]]:
        """List the shop's fulfillment services, including custom ones.

        Scope: ``read_custom_fulfillment_services``
        Query: shop { fulfillmentServices }

        Returns:
            list[dict]: Fulfillment-service objects. ``type`` is
            "MANUAL" for the shop's own locations and "THIRD_PARTY" for
            app-provided (custom) services.
        """
        query = """
        query GetFulfillmentServices {
            shop {
                fulfillmentServices {
                    id
                    handle
                    serviceName
                    type
                    callbackUrl
                    inventoryManagement
                    trackingSupport
                    requiresShippingMethod
                    location { id name isActive }
                }
            }
        }
        """
        return self._execute(query)["shop"]["fulfillmentServices"]

    def get_return_reason_definitions(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List the shop's return reason definitions.

        Scope: ``read_returns``
        Query: returnReasonDefinitions

        Individual returns are read through the ``returns`` connection on an
        order; this method returns the reason catalogue that classifies them.

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Return-reason-definition nodes.
        """
        selection = """
            id
            name
            handle
            deleted
        """
        return self._paginate(
            "returnReasonDefinitions",
            selection,
            variables={"query": search_query},
            variable_types={"query": "String"},
            page_size=page_size,
            max_pages=max_pages,
        )

    # -------------------------------------------------------------- inventory

    def get_locations(
        self,
        search_query: str | None = None,
        include_inactive: bool = True,
        include_legacy: bool = True,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List the shop's inventory locations.

        Scope: ``read_locations``
        Query: locations

        Args:
            search_query (str, optional): Shopify search syntax.
            include_inactive (bool): Include deactivated locations.
            include_legacy (bool): Include legacy locations.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Location nodes.
        """
        return self._paginate(
            "locations",
            _LOCATION_FIELDS,
            variables={
                "query": search_query,
                "includeInactive": include_inactive,
                "includeLegacy": include_legacy,
            },
            variable_types={
                "query": "String",
                "includeInactive": "Boolean",
                "includeLegacy": "Boolean",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_inventory_shipments(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List inventory shipments between locations.

        Scope: ``read_inventory_shipments``
        Query: inventoryShipments

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Inventory-shipment nodes.
        """
        return self._paginate(
            "inventoryShipments",
            _INVENTORY_SHIPMENT_FIELDS,
            variables={"query": search_query},
            variable_types={"query": "String"},
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_inventory_shipment_received_items(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List inventory shipments with their per-item received quantities.

        Scope: ``read_inventory_shipments_received_items`` (in addition to
        ``read_inventory_shipments``)
        Query: inventoryShipments { lineItems }

        The received/accepted/rejected quantities on each line item are the
        part gated by ``read_inventory_shipments_received_items``.

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Inventory-shipment nodes, each with ``lineItems``.
        """
        selection = f"""
            {_INVENTORY_SHIPMENT_FIELDS}
            lineItems(first: 100) {{
                nodes {{
                    id
                    quantity
                    acceptedQuantity
                    rejectedQuantity
                    inventoryItem {{ id sku }}
                }}
            }}
        """
        return self._paginate(
            "inventoryShipments",
            selection,
            variables={"query": search_query},
            variable_types={"query": "String"},
            page_size=page_size or 20,
            max_pages=max_pages,
        )

    # ------------------------------------------------------ pricing/discounts

    def get_discounts(
        self,
        search_query: str | None = None,
        sort_key: str | None = None,
        reverse: bool = True,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List automatic and code-based discounts.

        Scope: ``read_discounts``
        Query: discountNodes

        Args:
            search_query (str, optional): Shopify search syntax, e.g.
                "status:active", "discount_type:code".
            sort_key (str, optional): A ``DiscountSortKeys`` value.
            reverse (bool): Newest first when True (the default).
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Discount nodes.
        """
        return self._paginate(
            "discountNodes",
            _DISCOUNT_NODE_FIELDS,
            variables={
                "query": search_query,
                "sortKey": sort_key,
                "reverse": reverse,
            },
            variable_types={
                "query": "String",
                "sortKey": "DiscountSortKeys",
                "reverse": "Boolean",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_price_rules(
        self,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List code-based discounts — the GraphQL successor to price rules.

        Scope: ``read_price_rules``
        Query: discountNodes (query: "discount_type:code")

        The legacy REST ``PriceRule`` resource has no GraphQL equivalent; code
        discounts under ``discountNodes`` are what replaced it, so this filters
        :meth:`get_discounts` down to that subset.

        Args:
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Code-discount nodes.
        """
        return self.get_discounts(
            search_query="discount_type:code",
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_discount_allocator_functions(
        self,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List the shop's discount-allocator Shopify Functions.

        Scope: ``read_discounts_allocator_functions``
        Query: shopifyFunctions(apiType: "discounts_allocator")

        Args:
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Shopify Function nodes.
        """
        selection = """
            id
            title
            handle
            apiType
            apiVersion
            appKey
            description
        """
        return self._paginate(
            "shopifyFunctions",
            selection,
            variables={"apiType": "discounts_allocator"},
            variable_types={"apiType": "String"},
            page_size=page_size,
            max_pages=max_pages,
        )

    # ----------------------------------------------------------- b2b/channels

    def get_companies(
        self,
        search_query: str | None = None,
        sort_key: str | None = None,
        reverse: bool = True,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List B2B companies.

        Scope: ``read_companies``
        Query: companies

        Args:
            search_query (str, optional): Shopify search syntax.
            sort_key (str, optional): A ``CompanySortKeys`` value.
            reverse (bool): Newest first when True (the default).
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Company nodes.
        """
        return self._paginate(
            "companies",
            _COMPANY_FIELDS,
            variables={
                "query": search_query,
                "sortKey": sort_key,
                "reverse": reverse,
            },
            variable_types={
                "query": "String",
                "sortKey": "CompanySortKeys",
                "reverse": "Boolean",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_channels(
        self,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List the shop's sales channels.

        Scope: ``read_channels``
        Query: channels

        Args:
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Channel nodes.
        """
        selection = """
            id
            name
            handle
            accountId
            accountName
            supportsFuturePublishing
            app { id title handle }
        """
        return self._paginate(
            "channels",
            selection,
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_publications(
        self,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List publications — the catalogues behind each sales channel.

        Scope: ``read_publications``
        Query: publications

        Args:
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Publication nodes.
        """
        selection = """
            id
            autoPublish
            supportsFuturePublishing
            catalog { id title status }
        """
        return self._paginate(
            "publications",
            selection,
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_app_installations(
        self,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List the apps installed on the shop.

        Scope: ``read_apps``
        Query: appInstallations

        Args:
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: App-installation nodes.
        """
        selection = """
            id
            launchUrl
            accessScopes { handle description }
            app { id title handle apiKey description embedded }
        """
        return self._paginate(
            "appInstallations",
            selection,
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_shop_locales(self, published: bool | None = None) -> list[dict[str, Any]]:
        """List the shop's languages.

        Scope: ``read_locales``
        Query: shopLocales

        Args:
            published (bool, optional): Restrict to published locales only.

        Returns:
            list[dict]: Shop-locale objects.
        """
        query = """
        query GetShopLocales($published: Boolean) {
            shopLocales(published: $published) {
                locale
                name
                primary
                published
            }
        }
        """
        return self._execute(query, variables={"published": published})["shopLocales"]

    # -------------------------------------------------------------- shipping

    def get_delivery_profiles(
        self,
        merchant_owned_only: bool | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List shipping (delivery) profiles and their zones and rates.

        Scope: ``read_shipping``
        Query: deliveryProfiles

        Args:
            merchant_owned_only (bool, optional): Exclude app-owned profiles.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Delivery-profile nodes.
        """
        selection = """
            id
            name
            default
            coversAllItems
            activeMethodDefinitionsCount
            locationsWithoutRatesCount
            originLocationCount
            zoneCountryCount
            profileLocationGroups {
                locationGroup { id locationsCount { count } }
            }
        """
        return self._paginate(
            "deliveryProfiles",
            selection,
            variables={"merchantOwnedOnly": merchant_owned_only},
            variable_types={"merchantOwnedOnly": "Boolean"},
            page_size=page_size or 10,
            max_pages=max_pages,
        )

    # -------------------------------------------------------- customizations

    def get_cart_transforms(
        self,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List the cart transforms owned by this app.

        Scope: ``read_cart_transforms``
        Query: cartTransforms

        Args:
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Cart-transform nodes.
        """
        selection = """
            id
            functionId
            blockOnFailure
        """
        return self._paginate(
            "cartTransforms",
            selection,
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_all_cart_transforms(
        self,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List every cart transform on the shop, including other apps'.

        Scope: ``read_all_cart_transforms`` (in addition to
        ``read_cart_transforms``)
        Query: cartTransforms

        The query is the same as :meth:`get_cart_transforms`; the wider scope is
        what makes Shopify return transforms owned by other apps rather than
        only this app's own.

        Args:
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Cart-transform nodes.
        """
        return self.get_cart_transforms(page_size=page_size, max_pages=max_pages)

    def get_delivery_customizations(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List delivery customizations (checkout shipping-option functions).

        Scope: ``read_delivery_customizations``
        Query: deliveryCustomizations

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Delivery-customization nodes.
        """
        selection = """
            id
            title
            enabled
            functionId
        """
        return self._paginate(
            "deliveryCustomizations",
            selection,
            variables={"query": search_query},
            variable_types={"query": "String"},
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_payment_customizations(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List payment customizations (checkout payment-option functions).

        Scope: ``read_payment_customizations``
        Query: paymentCustomizations

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Payment-customization nodes.
        """
        selection = """
            id
            title
            enabled
            functionId
        """
        return self._paginate(
            "paymentCustomizations",
            selection,
            variables={"query": search_query},
            variable_types={"query": "String"},
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_validations(
        self,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List cart and checkout validations.

        Scope: ``read_validations``
        Query: validations

        Args:
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Validation nodes.
        """
        selection = """
            id
            title
            enabled
            blockOnFailure
            shopifyFunction { id title apiType appKey }
        """
        return self._paginate(
            "validations",
            selection,
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_checkout_and_accounts_configurations(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List the shop's checkout and customer-accounts configurations.

        Scope: ``read_checkout_and_accounts_configurations``
        Query: checkoutAndAccountsConfigurations

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Configuration nodes.
        """
        selection = """
            id
            name
            isPublished
            createdAt
            updatedAt
            editedAt
        """
        return self._paginate(
            "checkoutAndAccountsConfigurations",
            selection,
            variables={"query": search_query},
            variable_types={"query": "String"},
            page_size=page_size,
            max_pages=max_pages,
        )

    # ----------------------------------------------------------- point of sale

    def get_cash_tracking_sessions(
        self,
        search_query: str | None = None,
        sort_key: str | None = None,
        reverse: bool = True,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List Point of Sale cash-tracking sessions.

        Scope: ``read_cash_tracking``
        Query: cashTrackingSessions

        Args:
            search_query (str, optional): Shopify search syntax.
            sort_key (str, optional): A ``CashTrackingSessionsSortKeys`` value.
            reverse (bool): Newest first when True (the default).
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Cash-tracking-session nodes.
        """
        selection = """
            id
            registerName
            openingTime
            closingTime
            openingNote
            closingNote
            cashTrackingEnabled
            location { id name }
            totalDiscrepancy { amount currencyCode }
            expectedClosingBalance { amount currencyCode }
            netCashSales { amount currencyCode }
        """
        return self._paginate(
            "cashTrackingSessions",
            selection,
            variables={
                "query": search_query,
                "sortKey": sort_key,
                "reverse": reverse,
            },
            variable_types={
                "query": "String",
                "sortKey": "CashTrackingSessionsSortKeys",
                "reverse": "Boolean",
            },
            page_size=page_size,
            max_pages=max_pages,
        )

    # -------------------------------------------------------- shopify payments

    def get_shopify_payments_account(self) -> dict[str, Any]:
        """Get the Shopify Payments account, its settings and current balance.

        Scope: ``read_shopify_payments_accounts``
        Query: shopifyPaymentsAccount

        ``chargeStatementDescriptors`` and ``payoutSchedule`` are deliberately
        not selected: the first needs the wider ``read_shopify_payments`` scope
        and the second is unavailable on accounts without a configured payout
        schedule, and either one makes the whole query fail.

        Returns:
            dict: The ``shopifyPaymentsAccount`` object, or ``None`` when
            Shopify Payments is not enabled on the shop.
        """
        query = """
        query GetShopifyPaymentsAccount {
            shopifyPaymentsAccount {
                id
                activated
                country
                defaultCurrency
                onboardable
                payoutStatementDescriptor
                balance { amount currencyCode }
            }
        }
        """
        return self._execute(query)["shopifyPaymentsAccount"]

    def get_shopify_payments_bank_accounts(
        self,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        """List the bank accounts attached to Shopify Payments.

        Scope: ``read_shopify_payments_bank_accounts``
        Query: shopifyPaymentsAccount { bankAccounts }

        Args:
            page_size (int, optional): Nodes per page.

        Returns:
            list[dict]: Bank-account nodes.
        """
        query = """
        query GetShopifyPaymentsBankAccounts($first: Int!) {
            shopifyPaymentsAccount {
                bankAccounts(first: $first) {
                    nodes {
                        id
                        bankName
                        accountNumberLastDigits
                        country
                        currency
                        status
                        createdAt
                    }
                }
            }
        }
        """
        data = self._execute(
            query,
            variables={"first": page_size or self.__configuration.page_size},
        )
        account = data.get("shopifyPaymentsAccount") or {}
        return (account.get("bankAccounts") or {}).get("nodes") or []

    def get_shopify_payments_payouts(
        self,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        """List Shopify Payments payouts.

        Scope: ``read_shopify_payments_payouts``
        Query: shopifyPaymentsAccount { payouts }

        Args:
            page_size (int, optional): Nodes per page.

        Returns:
            list[dict]: Payout nodes.
        """
        query = f"""
        query GetShopifyPaymentsPayouts($first: Int!) {{
            shopifyPaymentsAccount {{
                payouts(first: $first) {{
                    nodes {{ {_PAYOUT_FIELDS} }}
                }}
            }}
        }}
        """
        data = self._execute(
            query,
            variables={"first": page_size or self.__configuration.page_size},
        )
        account = data.get("shopifyPaymentsAccount") or {}
        return (account.get("payouts") or {}).get("nodes") or []

    def get_shopify_payments_disputes(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List Shopify Payments disputes (chargebacks and inquiries).

        Scope: ``read_shopify_payments_disputes``
        Query: disputes

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Dispute nodes.
        """
        return self._paginate(
            "disputes",
            _DISPUTE_FIELDS,
            variables={"query": search_query},
            variable_types={"query": "String"},
            page_size=page_size,
            max_pages=max_pages,
        )

    # -------------------------------------------------------------- analytics

    def run_shopifyql_query(self, shopifyql: str) -> dict[str, Any]:
        """Run a ShopifyQL analytics query.

        Scope: ``read_analytics``
        Query: shopifyqlQuery

        Args:
            shopifyql (str): A ShopifyQL statement, e.g.
                "FROM sales SHOW total_sales GROUP BY day SINCE -30d UNTIL today".

        Returns:
            dict: The ``shopifyqlQuery`` response — ``tableData.rows`` holds the
            result rows and ``parseErrors`` is non-null when the statement is
            invalid.
        """
        query = """
        query RunShopifyqlQuery($query: String!) {
            shopifyqlQuery(query: $query) {
                parseErrors
                tableData {
                    rows
                    columns {
                        name
                        displayName
                        shortDisplayName
                        dataType
                        columnOrigin
                    }
                }
            }
        }
        """
        return self._execute(query, variables={"query": shopifyql})["shopifyqlQuery"]

    # ------------------------------------------------- customer account api

    def get_customer_account_customers(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List customers — Admin-API view of the ``customer_read_customers`` scope.

        Scope: ``customer_read_customers``
        Query: customers

        ``customer_read_customers`` is a **Customer Account API** scope: it lets
        a logged-in customer read their own profile through
        ``https://shopify.com/{shop_id}/account/customer/api/{version}/graphql``.
        The Admin API has no per-customer-session equivalent, so this returns
        the merchant-side customer list. Reading it also requires the Admin
        ``read_customers`` scope.

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Customer nodes.
        """
        return self.get_customers(
            search_query=search_query,
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_customer_account_orders(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List orders — Admin-API view of the ``customer_read_orders`` scope.

        Scope: ``customer_read_orders``
        Query: orders

        ``customer_read_orders`` is a **Customer Account API** scope granting a
        logged-in customer access to their own order history. On the Admin API
        the closest equivalent is the shop-wide order list, which also requires
        the Admin ``read_orders`` scope. Pass ``search_query="customer_id:…"``
        to narrow it to a single customer.

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Order nodes.
        """
        return self.get_orders(
            search_query=search_query,
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_customer_account_companies(
        self,
        search_query: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List company locations — Admin view of ``customer_read_companies``.

        Scope: ``customer_read_companies``
        Query: companyLocations

        ``customer_read_companies`` is a **Customer Account API** scope letting
        a logged-in B2B customer read the companies and company locations they
        are attached to. This returns the merchant-side company-location list,
        which also requires the Admin ``read_companies`` scope.

        Args:
            search_query (str, optional): Shopify search syntax.
            page_size (int, optional): Nodes per page.
            max_pages (int, optional): Stop after this many pages.

        Returns:
            list[dict]: Company-location nodes.
        """
        return self._paginate(
            "companyLocations",
            _COMPANY_LOCATION_FIELDS,
            variables={"query": search_query},
            variable_types={"query": "String"},
            page_size=page_size,
            max_pages=max_pages,
        )

    # ------------------------------------- scopes without an Admin GraphQL read
    #
    # These scopes are granted to the app but gate data that the Admin GraphQL
    # API does not expose through a query root field. Each is kept as a method
    # so the scope-to-method mapping stays complete, and each raises with the
    # surface that actually serves the data.

    def get_analytics_annotations(self) -> list[dict[str, Any]]:
        """Analytics annotations.

        Scope: ``read_analytics_annotations``

        Raises:
            NotImplementedError: The Admin GraphQL API exposes no query root
                field for analytics annotations. They are written via the
                Marketing Activities API and read back through the analytics
                reports UI; use :meth:`run_shopifyql_query` for the underlying
                metrics.
        """
        raise NotImplementedError(
            "read_analytics_annotations has no Admin GraphQL query root field. "
            "Use run_shopifyql_query() for analytics metrics."
        )

    def get_app_proxy(self) -> dict[str, Any]:
        """App Proxy configuration.

        Scope: ``read_app_proxy``

        Raises:
            NotImplementedError: ``read_app_proxy`` grants the app read access
                to Online Store page content served on its proxied path — it is
                exercised by handling requests Shopify forwards to the app's
                proxy URL, not by an Admin GraphQL query.
        """
        raise NotImplementedError(
            "read_app_proxy grants access to proxied Online Store requests, "
            "not to an Admin GraphQL query. Handle the proxied HTTP request "
            "on the app's configured proxy URL instead."
        )

    def get_audit_events(self) -> list[dict[str, Any]]:
        """Shop audit events.

        Scope: ``read_audit_events``

        Raises:
            NotImplementedError: Audit events are a Shopify Plus feature exposed
                through the organization-level Audit Log, not the Admin GraphQL
                API. Use :meth:`get_customer_events` for the shop event log.
        """
        raise NotImplementedError(
            "read_audit_events has no Admin GraphQL query root field. Audit "
            "logs are read from the Shopify Plus organization admin. Use "
            "get_customer_events() for the shop's own event log."
        )

    def get_checkout_branding_settings(self) -> dict[str, Any]:
        """Checkout branding settings.

        Scope: ``read_checkout_branding_settings``

        Raises:
            NotImplementedError: This API version exposes no ``checkoutBranding``
                query root field — only the ``checkoutBrandingUpsert`` mutation.
                Use :meth:`get_checkout_and_accounts_configurations` for the
                checkout configurations themselves.
        """
        raise NotImplementedError(
            "read_checkout_branding_settings has no query root field in this "
            "API version (only the checkoutBrandingUpsert mutation). Use "
            "get_checkout_and_accounts_configurations() instead."
        )

    def get_checkout_kit_enhanced_buyer_events(self) -> list[dict[str, Any]]:
        """Checkout Kit enhanced buyer events.

        Scope: ``read_checkout_kit_enhanced_buyer_events``

        Raises:
            NotImplementedError: These events are delivered to the app's
                Checkout Kit / Web Pixel extension at runtime; the Admin
                GraphQL API exposes no query root field for them.
        """
        raise NotImplementedError(
            "read_checkout_kit_enhanced_buyer_events has no Admin GraphQL "
            "query root field. The events are delivered to the app's Checkout "
            "Kit / Web Pixel extension at runtime."
        )

    def get_custom_pixels(self) -> list[dict[str, Any]]:
        """Custom pixels.

        Scope: ``read_custom_pixels``

        Raises:
            NotImplementedError: Custom pixels are merchant-authored and only
                managed from the admin UI. The Admin GraphQL API exposes
                app-owned pixels through ``webPixel``, not custom ones.
        """
        raise NotImplementedError(
            "read_custom_pixels has no Admin GraphQL query root field. Custom "
            "pixels are merchant-authored and managed from the admin UI; only "
            "app-owned pixels are queryable, via webPixel."
        )

    def get_customer_data_erasure(self) -> list[dict[str, Any]]:
        """Customer data-erasure requests.

        Scope: ``read_customer_data_erasure``

        Raises:
            NotImplementedError: The Admin GraphQL API exposes only the
                ``customerRequestDataErasure`` and ``customerCancelDataErasure``
                mutations; erasure state is read from the customer's
                ``dataSaleOptOut`` / redaction fields, not a dedicated query.
        """
        raise NotImplementedError(
            "read_customer_data_erasure has no Admin GraphQL query root field. "
            "Only the customerRequestDataErasure / customerCancelDataErasure "
            "mutations are exposed."
        )

    def get_discovery(self) -> dict[str, Any]:
        """Search & Discovery configuration.

        Scope: ``read_discovery``

        Raises:
            NotImplementedError: Search & Discovery settings (filters, product
                boosts, synonyms) are owned by Shopify's Search & Discovery app
                and are not exposed on the Admin GraphQL query root.
        """
        raise NotImplementedError(
            "read_discovery has no Admin GraphQL query root field. Search & "
            "Discovery settings are owned by Shopify's Search & Discovery app."
        )

    def get_reports(self) -> list[dict[str, Any]]:
        """Saved analytics reports.

        Scope: ``read_reports``

        Raises:
            NotImplementedError: The saved-report resource was removed from the
                Admin API. ``read_reports`` now serves as an alternative
                authorization for ShopifyQL — use :meth:`run_shopifyql_query`.
        """
        raise NotImplementedError(
            "read_reports has no Admin GraphQL query root field — the saved "
            "report resource was removed from the Admin API. Use "
            "run_shopifyql_query() to run analytics queries."
        )


def as_tools(configuration: ShopifyIntegrationConfiguration):
    """Expose the Shopify integration as LangChain tools for agent use."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = ShopifyIntegration(configuration)

    class NoArgsSchema(BaseModel):
        pass

    class PaginationSchema(BaseModel):
        page_size: int | None = Field(None, description="Nodes fetched per page")
        max_pages: int | None = Field(
            None, description="Stop after this many pages (None to exhaust)"
        )

    class SearchSchema(PaginationSchema):
        search_query: str | None = Field(
            None,
            description=(
                "Shopify search syntax filter, e.g. 'status:active' or "
                "'created_at:>=2026-07-01'"
            ),
        )

    class SortedSearchSchema(SearchSchema):
        sort_key: str | None = Field(
            None, description="Sort key enum value for this connection"
        )
        reverse: bool = Field(True, description="Reverse the sort order")

    class CustomerIdSchema(BaseModel):
        customer_id: str = Field(
            ..., description="Customer GID, e.g. 'gid://shopify/Customer/123'"
        )
        show_revoked: bool = Field(False, description="Include revoked payment methods")

    class CustomerMergePreviewSchema(BaseModel):
        customer_one_id: str = Field(..., description="GID of the first customer")
        customer_two_id: str = Field(..., description="GID of the second customer")

    class JobIdSchema(BaseModel):
        job_id: str = Field(..., description="GID of the customer-merge job")

    class GetOrderSchema(BaseModel):
        order: str = Field(
            ...,
            description=(
                "Order GID (gid://shopify/Order/123) or order name ('#1429' or '1429')"
            ),
        )

    class OrderEditSessionSchema(BaseModel):
        order_edit_session_id: str = Field(
            ..., description="GID of the order-edit session"
        )

    class AssignedFulfillmentOrdersSchema(PaginationSchema):
        assignment_status: str | None = Field(
            None,
            description=(
                "FulfillmentOrderAssignmentStatus value, e.g. 'FULFILLMENT_REQUESTED'"
            ),
        )
        location_ids: list[str] | None = Field(
            None, description="Restrict to these location GIDs"
        )

    class LocationsSchema(SearchSchema):
        include_inactive: bool = Field(True, description="Include inactive locations")
        include_legacy: bool = Field(True, description="Include legacy locations")

    class ShopLocalesSchema(BaseModel):
        published: bool | None = Field(
            None, description="Restrict to published locales only"
        )

    class DeliveryProfilesSchema(PaginationSchema):
        merchant_owned_only: bool | None = Field(
            None, description="Exclude app-owned delivery profiles"
        )

    class ShopifyqlSchema(BaseModel):
        shopifyql: str = Field(
            ...,
            description=(
                "ShopifyQL statement, e.g. 'FROM sales SHOW total_sales "
                "GROUP BY day SINCE -30d UNTIL today'"
            ),
        )

    class PageSizeSchema(BaseModel):
        page_size: int | None = Field(None, description="Nodes fetched per page")

    return [
        # ----- permissions / identity
        StructuredTool(
            name="shopify_get_access_scopes",
            description=(
                "List the Shopify access scopes (permissions) granted to this "
                "app on the shop. Call this first to know which other Shopify "
                "tools are usable."
            ),
            func=lambda: integration.get_access_scopes(),
            args_schema=NoArgsSchema,
        ),
        StructuredTool(
            name="shopify_get_app_installation",
            description=(
                "Get the current Shopify app installation: app identity plus "
                "its granted access scopes with descriptions."
            ),
            func=lambda: integration.get_app_installation(),
            args_schema=NoArgsSchema,
        ),
        StructuredTool(
            name="shopify_get_shop",
            description=(
                "Get the Shopify shop profile: name, domain, plan, currency, "
                "timezone and billing address."
            ),
            func=lambda: integration.get_shop(),
            args_schema=NoArgsSchema,
        ),
        # ----- catalogue
        StructuredTool(
            name="shopify_get_products",
            description=(
                "List Shopify products with their variants, prices and "
                "inventory. Requires the read_products scope."
            ),
            func=lambda search_query=None, sort_key=None, reverse=True, page_size=None, max_pages=None: (
                integration.get_products(
                    search_query=search_query,
                    sort_key=sort_key,
                    reverse=reverse,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SortedSearchSchema,
        ),
        StructuredTool(
            name="shopify_get_product_listings",
            description=(
                "List which products are published to which sales channel. "
                "Requires the read_product_listings scope."
            ),
            func=lambda page_size=None, max_pages=None: (
                integration.get_product_listings(
                    page_size=page_size, max_pages=max_pages
                )
            ),
            args_schema=PaginationSchema,
        ),
        # ----- customers
        StructuredTool(
            name="shopify_get_customers",
            description=(
                "List Shopify customers with lifetime spend and order counts. "
                "Requires the read_customers scope."
            ),
            func=lambda search_query=None, sort_key=None, reverse=True, page_size=None, max_pages=None: (
                integration.get_customers(
                    search_query=search_query,
                    sort_key=sort_key,
                    reverse=reverse,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SortedSearchSchema,
        ),
        StructuredTool(
            name="shopify_get_customer_payment_methods",
            description=(
                "List a customer's stored payment methods. Requires the "
                "read_customer_payment_methods scope."
            ),
            func=lambda customer_id, show_revoked=False: (
                integration.get_customer_payment_methods(
                    customer_id, show_revoked=show_revoked
                )
            ),
            args_schema=CustomerIdSchema,
        ),
        StructuredTool(
            name="shopify_get_customer_events",
            description=(
                "List customer-related events from the shop event log. "
                "Requires the read_customer_events scope."
            ),
            func=lambda search_query=None, page_size=None, max_pages=None: (
                integration.get_customer_events(
                    search_query=search_query,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchSchema,
        ),
        StructuredTool(
            name="shopify_get_customer_merge_preview",
            description=(
                "Preview the result of merging two Shopify customers. Requires "
                "the read_customer_merge scope."
            ),
            func=lambda customer_one_id, customer_two_id: (
                integration.get_customer_merge_preview(customer_one_id, customer_two_id)
            ),
            args_schema=CustomerMergePreviewSchema,
        ),
        StructuredTool(
            name="shopify_get_customer_merge_job_status",
            description=(
                "Get the status of a Shopify customer-merge job. Requires the "
                "read_customer_merge scope."
            ),
            func=lambda job_id: integration.get_customer_merge_job_status(job_id),
            args_schema=JobIdSchema,
        ),
        # ----- orders
        StructuredTool(
            name="shopify_get_order",
            description=(
                "Get one Shopify order in full by GID or order number "
                "('#1429'), including the buyer's personalization input in "
                "each line item's customAttributes (engraving text, chosen "
                "model). Requires the read_orders scope."
            ),
            func=lambda order: integration.get_order(order),
            args_schema=GetOrderSchema,
        ),
        StructuredTool(
            name="shopify_get_orders",
            description=(
                "List Shopify orders with line items and money totals (last 60 "
                "days without read_all_orders). Requires the read_orders scope."
            ),
            func=lambda search_query=None, sort_key="CREATED_AT", reverse=True, page_size=None, max_pages=None: (
                integration.get_orders(
                    search_query=search_query,
                    sort_key=sort_key,
                    reverse=reverse,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SortedSearchSchema,
        ),
        StructuredTool(
            name="shopify_get_all_orders",
            description=(
                "List Shopify orders across the shop's full history, past the "
                "60-day window. Requires the read_all_orders scope."
            ),
            func=lambda search_query=None, sort_key="CREATED_AT", reverse=True, page_size=None, max_pages=None: (
                integration.get_all_orders(
                    search_query=search_query,
                    sort_key=sort_key,
                    reverse=reverse,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SortedSearchSchema,
        ),
        StructuredTool(
            name="shopify_get_draft_orders",
            description=(
                "List Shopify draft orders (quotes and invoices). Requires the "
                "read_draft_orders scope."
            ),
            func=lambda search_query=None, sort_key=None, reverse=True, page_size=None, max_pages=None: (
                integration.get_draft_orders(
                    search_query=search_query,
                    sort_key=sort_key,
                    reverse=reverse,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SortedSearchSchema,
        ),
        StructuredTool(
            name="shopify_get_abandoned_checkouts",
            description=(
                "List abandoned Shopify checkouts. Requires the read_checkouts scope."
            ),
            func=lambda search_query=None, sort_key=None, reverse=True, page_size=None, max_pages=None: (
                integration.get_abandoned_checkouts(
                    search_query=search_query,
                    sort_key=sort_key,
                    reverse=reverse,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SortedSearchSchema,
        ),
        StructuredTool(
            name="shopify_get_order_edit_session",
            description=(
                "Get a Shopify order-edit session by ID. Requires the "
                "read_order_edits scope."
            ),
            func=lambda order_edit_session_id: integration.get_order_edit_session(
                order_edit_session_id
            ),
            args_schema=OrderEditSessionSchema,
        ),
        # ----- fulfilment
        StructuredTool(
            name="shopify_get_assigned_fulfillment_orders",
            description=(
                "List fulfillment orders assigned to this app's fulfillment "
                "service. Requires the read_assigned_fulfillment_orders scope."
            ),
            func=lambda assignment_status=None, location_ids=None, page_size=None, max_pages=None: (
                integration.get_assigned_fulfillment_orders(
                    assignment_status=assignment_status,
                    location_ids=location_ids,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=AssignedFulfillmentOrdersSchema,
        ),
        StructuredTool(
            name="shopify_get_fulfillment_services",
            description=(
                "List the shop's fulfillment services, including custom "
                "third-party ones. Requires the "
                "read_custom_fulfillment_services scope."
            ),
            func=lambda: integration.get_fulfillment_services(),
            args_schema=NoArgsSchema,
        ),
        StructuredTool(
            name="shopify_get_return_reason_definitions",
            description=(
                "List the shop's return reason definitions. Requires the "
                "read_returns scope."
            ),
            func=lambda search_query=None, page_size=None, max_pages=None: (
                integration.get_return_reason_definitions(
                    search_query=search_query,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchSchema,
        ),
        # ----- inventory
        StructuredTool(
            name="shopify_get_locations",
            description=(
                "List the shop's inventory locations. Requires the "
                "read_locations scope."
            ),
            func=lambda search_query=None, include_inactive=True, include_legacy=True, page_size=None, max_pages=None: (
                integration.get_locations(
                    search_query=search_query,
                    include_inactive=include_inactive,
                    include_legacy=include_legacy,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=LocationsSchema,
        ),
        StructuredTool(
            name="shopify_get_inventory_shipments",
            description=(
                "List inventory shipments between locations. Requires the "
                "read_inventory_shipments scope."
            ),
            func=lambda search_query=None, page_size=None, max_pages=None: (
                integration.get_inventory_shipments(
                    search_query=search_query,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchSchema,
        ),
        StructuredTool(
            name="shopify_get_inventory_shipment_received_items",
            description=(
                "List inventory shipments with per-item accepted/rejected "
                "received quantities. Requires the "
                "read_inventory_shipments_received_items scope."
            ),
            func=lambda search_query=None, page_size=None, max_pages=None: (
                integration.get_inventory_shipment_received_items(
                    search_query=search_query,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchSchema,
        ),
        # ----- pricing / discounts
        StructuredTool(
            name="shopify_get_discounts",
            description=(
                "List automatic and code-based Shopify discounts. Requires the "
                "read_discounts scope."
            ),
            func=lambda search_query=None, sort_key=None, reverse=True, page_size=None, max_pages=None: (
                integration.get_discounts(
                    search_query=search_query,
                    sort_key=sort_key,
                    reverse=reverse,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SortedSearchSchema,
        ),
        StructuredTool(
            name="shopify_get_price_rules",
            description=(
                "List code-based discounts — the GraphQL successor to the "
                "legacy price-rule resource. Requires the read_price_rules "
                "scope."
            ),
            func=lambda page_size=None, max_pages=None: integration.get_price_rules(
                page_size=page_size, max_pages=max_pages
            ),
            args_schema=PaginationSchema,
        ),
        StructuredTool(
            name="shopify_get_discount_allocator_functions",
            description=(
                "List the shop's discount-allocator Shopify Functions. "
                "Requires the read_discounts_allocator_functions scope."
            ),
            func=lambda page_size=None, max_pages=None: (
                integration.get_discount_allocator_functions(
                    page_size=page_size, max_pages=max_pages
                )
            ),
            args_schema=PaginationSchema,
        ),
        # ----- b2b / channels
        StructuredTool(
            name="shopify_get_companies",
            description=(
                "List B2B companies on the shop. Requires the read_companies scope."
            ),
            func=lambda search_query=None, sort_key=None, reverse=True, page_size=None, max_pages=None: (
                integration.get_companies(
                    search_query=search_query,
                    sort_key=sort_key,
                    reverse=reverse,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SortedSearchSchema,
        ),
        StructuredTool(
            name="shopify_get_channels",
            description=(
                "List the shop's sales channels. Requires the read_channels scope."
            ),
            func=lambda page_size=None, max_pages=None: integration.get_channels(
                page_size=page_size, max_pages=max_pages
            ),
            args_schema=PaginationSchema,
        ),
        StructuredTool(
            name="shopify_get_publications",
            description=(
                "List publications — the catalogues behind each sales channel. "
                "Requires the read_publications scope."
            ),
            func=lambda page_size=None, max_pages=None: integration.get_publications(
                page_size=page_size, max_pages=max_pages
            ),
            args_schema=PaginationSchema,
        ),
        StructuredTool(
            name="shopify_get_app_installations",
            description=(
                "List the apps installed on the shop and their scopes. "
                "Requires the read_apps scope."
            ),
            func=lambda page_size=None, max_pages=None: (
                integration.get_app_installations(
                    page_size=page_size, max_pages=max_pages
                )
            ),
            args_schema=PaginationSchema,
        ),
        StructuredTool(
            name="shopify_get_shop_locales",
            description=("List the shop's languages. Requires the read_locales scope."),
            func=lambda published=None: integration.get_shop_locales(published),
            args_schema=ShopLocalesSchema,
        ),
        # ----- shipping
        StructuredTool(
            name="shopify_get_delivery_profiles",
            description=(
                "List shipping (delivery) profiles, zones and rate counts. "
                "Requires the read_shipping scope."
            ),
            func=lambda merchant_owned_only=None, page_size=None, max_pages=None: (
                integration.get_delivery_profiles(
                    merchant_owned_only=merchant_owned_only,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=DeliveryProfilesSchema,
        ),
        # ----- customizations
        StructuredTool(
            name="shopify_get_cart_transforms",
            description=(
                "List this app's cart transforms. Requires the "
                "read_cart_transforms scope."
            ),
            func=lambda page_size=None, max_pages=None: integration.get_cart_transforms(
                page_size=page_size, max_pages=max_pages
            ),
            args_schema=PaginationSchema,
        ),
        StructuredTool(
            name="shopify_get_all_cart_transforms",
            description=(
                "List every cart transform on the shop, including other apps'. "
                "Requires the read_all_cart_transforms scope."
            ),
            func=lambda page_size=None, max_pages=None: (
                integration.get_all_cart_transforms(
                    page_size=page_size, max_pages=max_pages
                )
            ),
            args_schema=PaginationSchema,
        ),
        StructuredTool(
            name="shopify_get_delivery_customizations",
            description=(
                "List checkout delivery customizations. Requires the "
                "read_delivery_customizations scope."
            ),
            func=lambda search_query=None, page_size=None, max_pages=None: (
                integration.get_delivery_customizations(
                    search_query=search_query,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchSchema,
        ),
        StructuredTool(
            name="shopify_get_payment_customizations",
            description=(
                "List checkout payment customizations. Requires the "
                "read_payment_customizations scope."
            ),
            func=lambda search_query=None, page_size=None, max_pages=None: (
                integration.get_payment_customizations(
                    search_query=search_query,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchSchema,
        ),
        StructuredTool(
            name="shopify_get_validations",
            description=(
                "List cart and checkout validations. Requires the "
                "read_validations scope."
            ),
            func=lambda page_size=None, max_pages=None: integration.get_validations(
                page_size=page_size, max_pages=max_pages
            ),
            args_schema=PaginationSchema,
        ),
        StructuredTool(
            name="shopify_get_checkout_and_accounts_configurations",
            description=(
                "List the shop's checkout and customer-accounts "
                "configurations. Requires the "
                "read_checkout_and_accounts_configurations scope."
            ),
            func=lambda search_query=None, page_size=None, max_pages=None: (
                integration.get_checkout_and_accounts_configurations(
                    search_query=search_query,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchSchema,
        ),
        # ----- point of sale
        StructuredTool(
            name="shopify_get_cash_tracking_sessions",
            description=(
                "List Point of Sale cash-tracking sessions and their "
                "discrepancies. Requires the read_cash_tracking scope."
            ),
            func=lambda search_query=None, sort_key=None, reverse=True, page_size=None, max_pages=None: (
                integration.get_cash_tracking_sessions(
                    search_query=search_query,
                    sort_key=sort_key,
                    reverse=reverse,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SortedSearchSchema,
        ),
        # ----- shopify payments
        StructuredTool(
            name="shopify_get_shopify_payments_account",
            description=(
                "Get the Shopify Payments account, settings and current "
                "balance. Requires the read_shopify_payments_accounts scope."
            ),
            func=lambda: integration.get_shopify_payments_account(),
            args_schema=NoArgsSchema,
        ),
        StructuredTool(
            name="shopify_get_shopify_payments_bank_accounts",
            description=(
                "List bank accounts attached to Shopify Payments. Requires the "
                "read_shopify_payments_bank_accounts scope."
            ),
            func=lambda page_size=None: integration.get_shopify_payments_bank_accounts(
                page_size=page_size
            ),
            args_schema=PageSizeSchema,
        ),
        StructuredTool(
            name="shopify_get_shopify_payments_payouts",
            description=(
                "List Shopify Payments payouts with gross/net amounts. "
                "Requires the read_shopify_payments_payouts scope."
            ),
            func=lambda page_size=None: integration.get_shopify_payments_payouts(
                page_size=page_size
            ),
            args_schema=PageSizeSchema,
        ),
        StructuredTool(
            name="shopify_get_shopify_payments_disputes",
            description=(
                "List Shopify Payments disputes and chargebacks. Requires the "
                "read_shopify_payments_disputes scope."
            ),
            func=lambda search_query=None, page_size=None, max_pages=None: (
                integration.get_shopify_payments_disputes(
                    search_query=search_query,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchSchema,
        ),
        # ----- analytics
        StructuredTool(
            name="shopify_run_shopifyql_query",
            description=(
                "Run a ShopifyQL analytics query, e.g. 'FROM sales SHOW "
                "total_sales GROUP BY day SINCE -30d UNTIL today'. Requires "
                "the read_analytics scope."
            ),
            func=lambda shopifyql: integration.run_shopifyql_query(shopifyql),
            args_schema=ShopifyqlSchema,
        ),
        # ----- customer account api equivalents
        StructuredTool(
            name="shopify_get_customer_account_companies",
            description=(
                "List B2B company locations — the Admin-API view of the "
                "customer_read_companies Customer Account API scope."
            ),
            func=lambda search_query=None, page_size=None, max_pages=None: (
                integration.get_customer_account_companies(
                    search_query=search_query,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchSchema,
        ),
    ]
