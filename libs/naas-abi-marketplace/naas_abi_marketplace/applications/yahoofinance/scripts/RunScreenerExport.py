#!/usr/bin/env python3
"""CLI entrypoint for the Yahoo Finance screener integration."""

from __future__ import annotations

from naas_abi_marketplace.applications.yahoofinance.integrations.YahooFinanceScreenerIntegration import (
    YahooFinanceScreenerIntegration,
    YahooFinanceScreenerIntegrationConfiguration,
    parse_args,
)


def main() -> None:
    args = parse_args()
    integration = YahooFinanceScreenerIntegration(
        YahooFinanceScreenerIntegrationConfiguration()
    )
    integration.run_export(args)


if __name__ == "__main__":
    main()
